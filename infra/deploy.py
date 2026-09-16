#!/usr/bin/env python3
"""画像生成 MCP（slide-image-gen）が使う Microsoft Foundry を、リージョンごとにデプロイする。

GPT-Image-2 に対応するリージョンを 1 つずつ調べ、デプロイできるリージョンにだけ作成する。
モデルが提供されていない、クォータに空きがない、名前が使えない、デプロイに失敗した
リージョンは飛ばして残りを続け、使えるリージョンの接続先を env ファイルに書き込む。

    python3 infra/deploy.py --check   調べるだけ（Azure にも env ファイルにも書き込まない）
    python3 infra/deploy.py           デプロイし、env ファイルを書き込む

何度実行してもよい。作成済みのリージョンはそのまま使い、足りないリージョンだけを作成する。
標準ライブラリと Azure CLI（az）だけで動く。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

# GPT-Image-2 を GlobalStandard で提供するリージョン（2026-09 時点）。
# 提供状況はモデルの更新で変わるため、実行時にもリージョンごとに確かめる。
REGIONS = ["eastus2", "westus3", "swedencentral", "polandcentral", "uaenorth"]

RESOURCE_GROUP = "rg-slide-image-gen-mcp"
MODEL_NAME = "gpt-image-2"
MODEL_VERSION = "2026-04-21"
SKU_NAME = "GlobalStandard"
DEPLOYMENT_NAME = MODEL_NAME

# リージョンあたりの capacity の上限。無申請のクォータは 2 で、空きが少なければ空きの分だけ割り当てる
CAPACITY = 2

# 付与するロール。Cognitive Services User はデータプレーンの操作（Microsoft.CognitiveServices/*）を許可し、
# 画像の生成と編集の両方を呼べる
ROLE_ID = "a97b65f3-24c7-4388-baec-2e87135dc908"

# 画像の生成と編集を含む、OpenAI のデータプレーン操作をすべて許可する組み込みロール（2026-09 時点）。
# どれかが付与されていれば、ロールを新たに付与しない
CALLER_ROLE_IDS = {
    "a97b65f3-24c7-4388-baec-2e87135dc908",  # Cognitive Services User
    "a001fd3d-188f-4b5d-821b-7da978bf7442",  # Cognitive Services OpenAI Contributor
    "19c28022-e58e-450d-a464-0b2a53034789",  # Cognitive Services Data Contributor (Preview)
    "53ca6127-db72-4b80-b1b0-d745d6d5456d",  # Foundry User
    "c883944f-8b7b-4483-af10-35834be79c4a",  # Foundry Owner
    "eadc314b-1a2d-4efa-be10-5d325db5065e",  # Foundry Project Manager
    "64702f94-c441-49e6-a78b-ef80e0188fee",  # Azure AI Developer
}

TAGS = {"managed-by": "pptx-as-code", "component": "slide-image-gen"}
TEMPLATE = Path(__file__).resolve().with_name("foundry-image.bicep")

# MCP サーバーが env ファイルの場所として最初に見る環境変数
ENV_FILE_VAR = "SLIDE_IMAGE_GEN_ENV_FILE"

# カスタムサブドメインの規則（英数字とハイフン、2〜64 文字、先頭と末尾は英数字）
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")

# 表示用の説明。ここに無いエラーコードは Azure のメッセージを示す
ERROR_HINTS = {
    "InsufficientQuota": "クォータの空きがありません",
    "CustomDomainInUse": "アカウント名が使用済みです",
    "RequestDisallowedByPolicy": "Azure Policy で禁止されています",
    "AuthorizationFailed": "権限が足りません",
    "LinkedAuthorizationFailed": "権限が足りません",
    "LocationNotAvailableForResourceType": "このリージョンでは作成できません",
    "MissingSubscriptionRegistration": "リソースプロバイダー Microsoft.CognitiveServices が未登録です",
}

# 個別の原因を包むだけのコード。より具体的なコードがあればそちらを示す
WRAPPER_CODES = {"DeploymentFailed", "ResourceDeploymentFailure", "InvalidTemplateDeployment"}

AZ = shutil.which("az")


# --- az の実行 ---------------------------------------------------------------


class AzError(Exception):
    """az コマンドの失敗。出力からエラーコードを取り出して要約する。"""

    def __init__(self, output: str) -> None:
        self.output = output
        self.codes = _error_codes(output)
        super().__init__(self.summary())

    def has(self, *codes: str) -> bool:
        return any(code in self.codes for code in codes)

    def summary(self) -> str:
        codes = [code for code in self.codes if code not in WRAPPER_CODES] or self.codes
        if not codes:
            line = next((line.strip() for line in self.output.splitlines() if line.strip()), "")
            return _shorten(line.removeprefix("ERROR:").strip()) or "az コマンドが失敗しました"
        code = codes[0]
        if code in ERROR_HINTS:
            return f"{code}（{ERROR_HINTS[code]}）"
        message = _message_for(self.output, code)
        return f"{code}: {message}" if message else code


def _error_codes(text: str) -> list[str]:
    """az の出力に含まれるエラーコードを、出現順に重複なく返す。"""
    found = re.findall(r'"code"\s*:\s*"([^"]+)"', text)
    found += re.findall(r"^(?:ERROR:\s*)?\(([A-Za-z]+)\)", text, flags=re.MULTILINE)
    found += re.findall(r"^Code:\s*(\S+)", text, flags=re.MULTILINE)
    # デプロイの事前検証の失敗は「コード - メッセージ」の形で 1 行ずつ出る
    found += re.findall(r"^(?:ERROR:\s*)?([A-Z][A-Za-z]+) - ", text, flags=re.MULTILINE)
    codes: list[str] = []
    for code in found:
        if code not in codes:
            codes.append(code)
    return codes


def _message_for(text: str, code: str) -> str:
    """エラーコードに対応するメッセージを取り出す。"""
    index = text.find(f'"{code}"')
    if index >= 0:
        match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', text[index : index + 1000])
        if match:
            return _shorten(match.group(1).replace('\\"', '"'))
    match = re.search(rf"^(?:ERROR:\s*)?{re.escape(code)} - (.+)$", text, flags=re.MULTILINE)
    if match:
        return _shorten(match.group(1))
    match = re.search(r"^Message:\s*(.+)$", text, flags=re.MULTILINE)
    return _shorten(match.group(1)) if match else ""


def _shorten(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def az(*args: str, timeout: int = 180):
    """az を実行して JSON の出力を返す。失敗したら AzError を投げる。"""
    try:
        proc = subprocess.run(
            [AZ, *args, "--only-show-errors", "-o", "json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise AzError(f"ERROR: az {' '.join(args[:3])} が {timeout} 秒以内に終わりませんでした") from None
    if proc.returncode != 0:
        raise AzError(proc.stderr.strip() or proc.stdout.strip())
    output = proc.stdout.strip()
    return json.loads(output) if output else None


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(2)


# --- 実行環境の把握 -----------------------------------------------------------


@dataclass
class Region:
    name: str
    account: str
    account_id: str
    action: str = "skip"  # use: 作成済みを使う / create: 作成する / skip: 飛ばす / failed: 作成に失敗
    capacity: int = 0
    detail: str = ""
    endpoint: str = ""
    role: str = ""  # ok: 付与済み / assign: 付与する / failed: 付与できない / off: 付与しない / unknown: 付与先が不明


@dataclass
class Context:
    subscription_id: str
    subscription_name: str
    tenant_id: str
    resource_group: str
    group_location: str | None  # 既存のリソースグループの場所。無ければ None
    principal_id: str | None
    principal_type: str
    principal_label: str
    no_role: bool
    accounts: dict  # アカウント名（小文字） -> サブスクリプション内の既存アカウント
    deleted: dict  # アカウント名（小文字） -> 論理削除中のアカウント


def prepare(args: argparse.Namespace) -> Context:
    """サインイン、リソースプロバイダー、ロールの付与先、既存のリソースを確かめる。"""
    if AZ is None:
        fail("Azure CLI（az）が見つかりません。導入してから、もう一度実行してください: https://learn.microsoft.com/cli/azure/install-azure-cli")
    try:
        account = az("account", "show")
    except AzError:
        fail("Azure にサインインしていません。az login を実行してから、もう一度実行してください。")

    state = az("provider", "show", "-n", "Microsoft.CognitiveServices", "--query", "registrationState")
    if state != "Registered":
        if args.check:
            print(f"リソースプロバイダー Microsoft.CognitiveServices が未登録です（{state}）。本実行で登録します。", file=sys.stderr)
        else:
            print("リソースプロバイダー Microsoft.CognitiveServices を登録しています...", file=sys.stderr)
            az("provider", "register", "-n", "Microsoft.CognitiveServices", "--wait", timeout=900)

    principal_id, principal_type, label = resolve_principal(account, args.no_role)
    group = get_group(args.resource_group)
    return Context(
        subscription_id=account["id"],
        subscription_name=account.get("name", ""),
        tenant_id=account.get("tenantId", ""),
        resource_group=args.resource_group,
        group_location=(group or {}).get("location"),
        principal_id=principal_id,
        principal_type=principal_type,
        principal_label=label,
        no_role=args.no_role,
        accounts=list_accounts(),
        deleted=list_deleted(),
    )


def resolve_principal(account: dict, no_role: bool) -> tuple[str | None, str, str]:
    """ロールを付与する principal（サインイン中のユーザーまたはサービスプリンシパル）を返す。"""
    if no_role:
        return None, "User", "付与しない（--no-role）"
    user = account.get("user") or {}
    try:
        if user.get("type") == "servicePrincipal":
            principal = az("ad", "sp", "show", "--id", user.get("name", ""))
            return principal["id"], "ServicePrincipal", f"{user.get('name')}（サービスプリンシパル）"
        principal = az("ad", "signed-in-user", "show")
        return principal["id"], "User", principal.get("userPrincipalName") or principal["id"]
    except AzError as error:
        return None, "User", f"特定できません（{error.summary()}）"


def get_group(name: str) -> dict | None:
    try:
        return az("group", "show", "-n", name)
    except AzError as error:
        if error.has("ResourceGroupNotFound"):
            return None
        raise


def list_accounts() -> dict:
    return {item["name"].lower(): item for item in az("cognitiveservices", "account", "list") or []}


def list_deleted() -> dict:
    try:
        items = az("cognitiveservices", "account", "list-deleted") or []
    except AzError:
        return {}
    return {item["name"].lower(): item for item in items}


def group_of(resource_id: str) -> str:
    match = re.search(r"/resourceGroups/([^/]+)", resource_id, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def default_prefix(subscription_id: str) -> str:
    """サブスクリプションごとに異なり、再実行しても変わらない接頭辞を返す。"""
    digest = hashlib.sha256(subscription_id.lower().encode()).hexdigest()[:6]
    return f"aif-slide-image-gen-{digest}"


# --- リージョンごとの判定 -----------------------------------------------------


def inspect(region: Region, ctx: Context, requested_capacity: int) -> Region:
    try:
        _inspect(region, ctx, requested_capacity)
    except AzError as error:
        region.action, region.detail = "skip", f"調べられませんでした: {error.summary()}"
    return region


def _inspect(region: Region, ctx: Context, requested_capacity: int) -> None:
    # モデルが提供されているか
    models = [item.get("model") or {} for item in az("cognitiveservices", "model", "list", "-l", region.name) or []]
    offered = any(
        model.get("name") == MODEL_NAME
        and model.get("version") == MODEL_VERSION
        and any(sku.get("name") == SKU_NAME for sku in model.get("skus") or [])
        for model in models
    )
    if not offered:
        versions = sorted({model.get("version", "") for model in models if model.get("name") == MODEL_NAME})
        region.detail = f"{MODEL_NAME} {MODEL_VERSION}（{SKU_NAME}）が提供されていません"
        if versions:
            region.detail += f"。提供中のバージョン: {', '.join(versions)}"
        return

    existing = ctx.accounts.get(region.account.lower())
    if existing:
        group = group_of(existing.get("id", ""))
        if group.lower() != ctx.resource_group.lower():
            region.detail = f"同じ名前のアカウントが別のリソースグループ（{group}）にあります。--resource-group で指定してください"
            return
        region.account_id = existing["id"]
        region.endpoint = (existing.get("properties") or {}).get("endpoint", "")
        deployment = get_deployment(ctx.resource_group, region.account)
        properties = (deployment or {}).get("properties") or {}
        if properties.get("provisioningState") == "Succeeded":
            region.action = "use"
            region.capacity = int(((deployment or {}).get("sku") or {}).get("capacity") or 0)
            region.detail = "作成済みのアカウントとデプロイを使います"
            version = (properties.get("model") or {}).get("version", "")
            if version and version != MODEL_VERSION:
                region.detail += f"（モデルのバージョン: {version}）"
            inspect_role(region, ctx)
            return
        # アカウントはあるがデプロイが無い、または失敗している。デプロイを作り直す
    else:
        deleted = ctx.deleted.get(region.account.lower())
        if deleted:
            region.detail = (
                "削除済みのアカウントが名前を保持しています（削除から 48 時間）。完全に削除してから再実行してください: "
                f"az cognitiveservices account purge -l {deleted.get('location', region.name)} "
                f"-g {group_of(deleted.get('id', ''))} -n {region.account}"
            )
            return
        if not subdomain_available(region.account):
            region.detail = f"アカウント名 {region.account} は使用済みです。--name-prefix で別の接頭辞を指定してください"
            return

    usage = quota(region.name)
    if usage is None:
        region.detail = f"クォータ（OpenAI.{SKU_NAME}.{MODEL_NAME}）の情報がありません"
        return
    limit, used = usage
    free = max(limit - used, 0)
    if free < 1:
        region.detail = f"クォータの空きがありません（上限 {limit}、使用中 {used}）"
        return
    region.action = "create"
    region.capacity = min(requested_capacity, free)
    region.detail = "作成します"
    if free < requested_capacity:
        region.detail += f"（クォータの空きが {free} のため capacity {region.capacity}）"
    region.role = "off" if ctx.no_role else ("assign" if ctx.principal_id else "unknown")


def get_deployment(group: str, account: str) -> dict | None:
    try:
        return az("cognitiveservices", "account", "deployment", "show", "-g", group, "-n", account, "--deployment-name", DEPLOYMENT_NAME)
    except AzError as error:
        if error.has("DeploymentNotFound", "ResourceNotFound", "NotFound"):
            return None
        raise


def subdomain_available(name: str) -> bool:
    body = json.dumps({"subdomainName": name, "type": "Microsoft.CognitiveServices/accounts", "kind": "AIServices"})
    url = "/subscriptions/{subscriptionId}/providers/Microsoft.CognitiveServices/checkDomainAvailability?api-version=2024-10-01"
    result = az("rest", "--method", "post", "--url", url, "--body", body) or {}
    return bool(result.get("isSubdomainAvailable"))


def quota(region: str) -> tuple[int, int] | None:
    """モデルのクォータの（上限, 使用中）を返す。項目が無ければ None。"""
    key = f"OpenAI.{SKU_NAME}.{MODEL_NAME}"
    for usage in az("cognitiveservices", "usage", "list", "-l", region) or []:
        if (usage.get("name") or {}).get("value") == key:
            return int(usage.get("limit") or 0), int(usage.get("currentValue") or 0)
    return None


def inspect_role(region: Region, ctx: Context) -> None:
    if ctx.no_role:
        region.role = "off"
        return
    if not ctx.principal_id:
        region.role = "unknown"
        return
    listing = [
        "role", "assignment", "list", "--scope", region.account_id, "--include-inherited",
        "--fill-principal-name", "false", "--fill-role-definition-name", "false",
    ]
    try:
        # グループ経由の割り当ても含めて調べる
        assignments = az(*listing, "--assignee", ctx.principal_id, "--include-groups") or []
    except AzError:
        # グループの解決には Microsoft Graph の権限が要る。取得できなければ本人への割り当てだけを見る
        assignments = [item for item in az(*listing) or [] if item.get("principalId") == ctx.principal_id]
    granted = any(str(item.get("roleDefinitionId", "")).rsplit("/", 1)[-1].lower() in CALLER_ROLE_IDS for item in assignments)
    region.role = "ok" if granted else "assign"


# --- 作成 -----------------------------------------------------------------------


def ensure_bicep() -> None:
    """Bicep CLI を 1 回だけ用意する。

    az は最初のデプロイで `~/.azure/bin/bicep` を自動で導入するため、リージョンを並列に
    デプロイすると同じファイルへの書き込みが衝突し、Text file busy で失敗する。
    """
    proc = subprocess.run([AZ, "bicep", "version", "--only-show-errors"], capture_output=True, text=True)
    if proc.returncode == 0:
        return
    print("Bicep CLI を導入しています...", file=sys.stderr)
    az("bicep", "install", timeout=600)


def deploy(region: Region, ctx: Context) -> Region:
    with_role = region.role == "assign"
    try:
        region.endpoint = _deploy(region, ctx, with_role)
        if with_role:
            region.role = "ok"
        region.detail = "作成しました"
    except AzError as error:
        # ロールを付与する権限だけが無い場合は、ロール割り当てを外して作り直す
        if with_role and error.has("AuthorizationFailed", "LinkedAuthorizationFailed") and "roleAssignments" in error.output:
            try:
                region.endpoint = _deploy(region, ctx, False)
                region.role = "failed"
                region.detail = "作成しました"
            except AzError as retry_error:
                region.action, region.detail = "failed", retry_error.summary()
        else:
            region.action, region.detail = "failed", error.summary()
    return region


def _deploy(region: Region, ctx: Context, with_role: bool) -> str:
    parameters = {
        "location": region.name,
        "accountName": region.account,
        "modelName": MODEL_NAME,
        "modelVersion": MODEL_VERSION,
        "deploymentName": DEPLOYMENT_NAME,
        "capacity": str(region.capacity),
        "tags": json.dumps(TAGS),
    }
    if with_role:
        parameters["principalId"] = ctx.principal_id or ""
        parameters["principalType"] = ctx.principal_type
    result = az(
        "deployment", "group", "create",
        "-g", ctx.resource_group,
        "-n", f"slide-image-gen-{region.name}",
        "--template-file", str(TEMPLATE),
        "--parameters", *[f"{key}={value}" for key, value in parameters.items()],
        timeout=1800,
    )
    outputs = ((result or {}).get("properties") or {}).get("outputs") or {}
    return (outputs.get("endpoint") or {}).get("value", "")


def assign_role(region: Region, ctx: Context) -> Region:
    """作成済みのアカウントに、実行したユーザーのロールを付与する。"""
    try:
        az(
            "role", "assignment", "create",
            "--assignee-object-id", ctx.principal_id or "",
            "--assignee-principal-type", ctx.principal_type,
            "--role", ROLE_ID,
            "--scope", region.account_id,
        )
        region.role = "ok"
    except AzError as error:
        region.role = "ok" if error.has("RoleAssignmentExists") else "failed"
    return region


# --- env ファイル ---------------------------------------------------------------


def env_target(explicit: str | None) -> Path:
    """書き込む env ファイル。MCP サーバーの探索順（環境変数 → 利用者ごとの既定）に合わせる。"""
    if explicit:
        return Path(explicit).expanduser()
    from_env = os.environ.get(ENV_FILE_VAR, "").strip()
    if from_env:
        return Path(from_env).expanduser()
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "slide-image-gen" / "env"
    return Path.home() / ".config" / "slide-image-gen" / "env"


def write_env(path: Path, endpoints: list[str], tenant_id: str) -> Path | None:
    """管理するキーだけを書き換え、ほかの行は残す。既存のファイルは .bak に退避し、そのパスを返す。"""
    managed = {
        "FOUNDRY_ENDPOINTS": ",".join(endpoints),
        "IMAGE_DEPLOYMENT_NAME": DEPLOYMENT_NAME,
        "FOUNDRY_TENANT_ID": tenant_id,
    }
    kept: list[str] = []
    backup = None
    if path.is_file():
        backup = path.with_name(path.name + ".bak")
        shutil.copy2(path, backup)
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
            # 単数形の FOUNDRY_ENDPOINT は複数形と和集合になるため、古い接続先が混ざらないよう消す
            if key in managed or key == "FOUNDRY_ENDPOINT":
                continue
            kept.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept + [f"{key}={value}" for key, value in managed.items()]) + "\n", encoding="utf-8")
    return backup


# --- 表示 -----------------------------------------------------------------------

PLAN_LABELS = {"use": "既存を使用", "create": "作成する", "skip": "スキップ"}
DONE_LABELS = {"use": "既存を使用", "create": "作成した", "skip": "スキップ", "failed": "失敗"}
ROLE_LABELS = {
    "ok": "ロール付与済み",
    "assign": "ロールを付与する",
    "failed": "ロールを付与できませんでした",
    "off": "ロールは付与しない",
    "unknown": "ロールの付与先が不明",
}


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - _width(text), 1)


def print_header(ctx: Context, prefix: str, env_path: Path) -> None:
    group = f"{ctx.resource_group}（既存、{ctx.group_location}）" if ctx.group_location else f"{ctx.resource_group}（未作成）"
    rows = [
        ("サブスクリプション", f"{ctx.subscription_name}（{ctx.subscription_id}）"),
        ("リソースグループ", group),
        ("アカウント名", f"{prefix}-<リージョン>"),
        ("モデル", f"{MODEL_NAME} {MODEL_VERSION}（{SKU_NAME}、デプロイ名 {DEPLOYMENT_NAME}）"),
        ("ロールの付与先", ctx.principal_label),
        ("env ファイル", str(env_path)),
    ]
    for label, value in rows:
        print(_pad(label, 20) + value)


def print_regions(regions: list[Region], labels: dict) -> None:
    print()
    print(_pad("リージョン", 16) + _pad("判定", 12) + _pad("容量", 6) + "内容")
    for region in regions:
        active = region.action in ("use", "create")
        detail = region.detail + (f"／{ROLE_LABELS[region.role]}" if active and region.role else "")
        print(_pad(region.name, 16) + _pad(labels[region.action], 12) + _pad(str(region.capacity) if active else "-", 6) + detail)
    print()


def print_role_request(regions: list[Region], ctx: Context) -> None:
    print("どのリージョンでもロールを付与できませんでした。管理者に次の付与を依頼してください。付与されれば、env ファイルはそのまま使えます。")
    assignee = ctx.principal_id or "<呼び出すユーザーの objectId>"
    for region in regions:
        print(
            f"  az role assignment create --assignee-object-id {assignee} --assignee-principal-type {ctx.principal_type} "
            f'--role "Cognitive Services User" --scope {region.account_id}'
        )


# --- 入口 -----------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="画像生成 MCP（slide-image-gen）が使う Microsoft Foundry を、リージョンごとにデプロイする。")
    parser.add_argument("--check", action="store_true", help="調べた結果だけを表示し、Azure にも env ファイルにも書き込まない")
    parser.add_argument("--regions", default=",".join(REGIONS), help=f"試すリージョン。カンマ区切り（既定: {','.join(REGIONS)}）")
    parser.add_argument("--resource-group", default=RESOURCE_GROUP, help=f"リソースグループ名（既定: {RESOURCE_GROUP}）")
    parser.add_argument("--capacity", type=int, default=CAPACITY, help=f"リージョンあたりの capacity の上限（既定: {CAPACITY}）")
    parser.add_argument("--name-prefix", help="アカウント名の接頭辞。末尾に -<リージョン> が付く（既定: aif-slide-image-gen-<サブスクリプション ID から作る 6 文字>）")
    parser.add_argument("--env-file", help="書き込む env ファイル（既定: ~/.config/slide-image-gen/env）")
    parser.add_argument("--no-role", action="store_true", help="ロール割り当てを作成しない")
    args = parser.parse_args()
    args.regions = list(dict.fromkeys(name.strip().lower() for name in args.regions.split(",") if name.strip()))
    if not args.regions:
        parser.error("--regions に 1 つ以上のリージョンを指定してください")
    if args.capacity < 1:
        parser.error("--capacity には 1 以上を指定してください")
    return args


def main() -> int:
    args = parse_args()
    ctx = prepare(args)
    prefix = (args.name_prefix or default_prefix(ctx.subscription_id)).lower()
    regions = [
        Region(
            name=name,
            account=f"{prefix}-{name}",
            account_id=f"/subscriptions/{ctx.subscription_id}/resourceGroups/{ctx.resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts/{prefix}-{name}",
        )
        for name in args.regions
    ]
    invalid = [region.account for region in regions if not NAME_PATTERN.match(region.account)]
    if invalid:
        fail(f"アカウント名の規則（英数字とハイフン、2〜64 文字）を満たしません: {', '.join(invalid)}。--name-prefix を見直してください。")
    env_path = env_target(args.env_file)

    print_header(ctx, prefix, env_path)
    print(f"\n{len(regions)} リージョンを調べています...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=min(len(regions), 5)) as pool:
        list(pool.map(lambda region: inspect(region, ctx, args.capacity), regions))

    usable = [region for region in regions if region.action in ("use", "create")]
    if args.check or not usable:
        print_regions(regions, PLAN_LABELS)
        if not usable:
            print("使えるリージョンがないため、何も作成しません。上の内容を確認してください。")
            return 1
        print("--check を外して実行すると、この内容で作成し、env ファイルを書き込みます。")
        return 0

    if ctx.group_location is None:
        try:
            az("group", "create", "-n", ctx.resource_group, "-l", usable[0].name, "--tags", *[f"{key}={value}" for key, value in TAGS.items()])
        except AzError as error:
            print(f"リソースグループ {ctx.resource_group} を作成できませんでした: {error.summary()}")
            return 1

    creates = [region for region in regions if region.action == "create"]
    needs_role = [region for region in regions if region.action == "use" and region.role == "assign"]
    if creates:
        ensure_bicep()
        print(f"{len(creates)} リージョンにデプロイしています（数分かかります）...", file=sys.stderr)
    if creates or needs_role:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(deploy, region, ctx) for region in creates]
            futures += [pool.submit(assign_role, region, ctx) for region in needs_role]
            for future in futures:
                future.result()

    ready = [region for region in regions if region.action in ("use", "create") and region.endpoint]
    callable_regions = [region for region in ready if region.role in ("ok", "off")]
    # 呼び出せるリージョンがあればそれだけを書く。MCP は 403 を別リージョンで再試行しないため混ぜない
    chosen = callable_regions or ready
    print_regions(regions, DONE_LABELS)
    if not chosen:
        print("使えるリージョンがありません。上の内容を確認してください。")
        return 1

    backup = write_env(env_path, [region.endpoint for region in chosen], ctx.tenant_id)
    print(f"env ファイルに {len(chosen)} リージョンの接続先を書き込みました: {env_path}")
    if backup:
        print(f"以前の内容は {backup} に退避しました。")
    excluded = [region.name for region in ready if region not in chosen]
    if excluded:
        print(f"ロールを付与できなかった {', '.join(excluded)} は、env ファイルに含めていません。")
    if not callable_regions:
        print_role_request(ready, ctx)
    if any(region.action in ("skip", "failed") for region in regions):
        print("スキップまたは失敗したリージョンは、原因を解消してからもう一度実行すると追加されます。")
    print("MCP クライアントを再起動すると反映されます。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n中断しました。作成済みのリソースは残ります。もう一度実行すると続きから再開します。", file=sys.stderr)
        sys.exit(130)
