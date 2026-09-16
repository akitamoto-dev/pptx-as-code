"""Microsoft Foundry の画像生成モデルを複数リージョンで呼び出すクライアント。

Foundry の v1 エンドポイント（``/openai/v1``）は OpenAI 互換のため OpenAI クライアントを
使用する。Entra ID 認証は DefaultAzureCredential で取得した Bearer トークンを
``api_key`` パラメータに渡す方式で、API キーは扱わない。

エンドポイントは [endpoint_pool.EndpointPool] が管理し、ラウンドロビンで順に選ぶ。
429 や一時エラーが起きたら、そのリージョンをクールダウンさせて次のリージョンへ
自動フェイルオーバーする。これにより連続生成でもレート制限で失敗しにくくする。
"""

from __future__ import annotations

import base64
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from azure.identity import DefaultAzureCredential
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from .endpoint_pool import AllEndpointsCoolingDown, Endpoint, EndpointPool

# スライド用途を想定した 16:9 サイズ（PowerPoint ワイドスクリーンと同じ比率）。
# gpt-image-2 は両辺が 16 の倍数で任意解像度をサポートするため、
# 16:9 に完全一致する 1792x1008 を選択。
# (16 の倍数: 1792/16=112, 1008/16=63 / 比率: 1792/1008=1.7778 = 16:9)
_IMAGE_SIZE = "1792x1008"

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

# 全リージョンがクールダウン中のとき、この秒数までなら待ってから再試行する。
# これを超える待ちなら諦めてレート制限エラーを返す（無限リトライはしない）。
_MAX_WAIT_SECONDS = 30.0


@dataclass
class GeneratedImage:
    png_bytes: bytes
    size: str
    model: str
    endpoint: str


class _RetriableError(Exception):
    """別リージョンへフェイルオーバーすべき一時的エラー。"""

    def __init__(self, original: Exception, retry_after: float | None) -> None:
        self.original = original
        self.retry_after = retry_after
        super().__init__(str(original))


# --- 環境変数の解決 ---------------------------------------------------------


def _resolve_endpoints() -> list[str]:
    """FOUNDRY_ENDPOINTS（複数）と FOUNDRY_ENDPOINT（単数・後方互換）を統合する。"""
    items: list[str] = []
    multi = os.environ.get("FOUNDRY_ENDPOINTS")
    if multi:
        items.extend(re.split(r"[,\n]", multi))
    single = os.environ.get("FOUNDRY_ENDPOINT")
    if single:
        items.append(single)
    items = [s.strip() for s in items if s.strip()]
    if not items:
        raise RuntimeError(
            "Foundry のエンドポイントが未設定です。FOUNDRY_ENDPOINTS（複数可・カンマ区切り）"
            "または FOUNDRY_ENDPOINT を、環境変数か env ファイル（~/.config/slide-image-gen/env）で"
            "設定してください。"
        )
    return items


def _resolve_deployment() -> str:
    deployment = os.environ.get("IMAGE_DEPLOYMENT_NAME")
    if not deployment:
        raise RuntimeError(
            "IMAGE_DEPLOYMENT_NAME が未設定です。Foundry のデプロイ名を、環境変数か env ファイル"
            "（~/.config/slide-image-gen/env）で設定してください。"
        )
    return deployment


def _resolve_cooldown_seconds() -> float:
    raw = os.environ.get("LB_COOLDOWN_SECONDS")
    if not raw:
        return 60.0
    try:
        return float(raw)
    except ValueError:
        return 60.0


def _resolve_tenant_id() -> str | None:
    """FOUNDRY_TENANT_ID（任意）を解決する。

    Foundry が属する Entra テナントを固定する。未設定なら None を返し、
    DefaultAzureCredential の既定挙動（ログイン中のテナント）に任せる。
    すべての Foundry リソースは同一テナント前提のため単一 ID とする。
    """
    raw = os.environ.get("FOUNDRY_TENANT_ID")
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


# --- プールとトークンの遅延初期化（プロセス内で使い回す） -------------------

_pool: EndpointPool | None = None
_credential: DefaultAzureCredential | None = None
_tenant_id: str | None = None
_token_value: str | None = None
_token_expires_on: float = 0.0


def _get_pool() -> EndpointPool:
    global _pool
    if _pool is None:
        _pool = EndpointPool(_resolve_endpoints(), _resolve_cooldown_seconds())
    return _pool


def _get_token() -> str:
    """有効な Bearer トークンを返す。期限が近ければ取得し直す。"""
    global _credential, _tenant_id, _token_value, _token_expires_on
    now = time.time()
    if _token_value is None or now >= _token_expires_on - 60:
        if _credential is None:
            _credential = DefaultAzureCredential()
            _tenant_id = _resolve_tenant_id()
        if _tenant_id:
            token = _credential.get_token(_TOKEN_SCOPE, tenant_id=_tenant_id)
        else:
            token = _credential.get_token(_TOKEN_SCOPE)
        _token_value = token.token
        _token_expires_on = float(token.expires_on)
    return _token_value


# --- 1 エンドポイントへの呼び出し -------------------------------------------


def _retry_after_seconds(error: Exception) -> float | None:
    """エラーから Retry-After ヘッダ（秒）を取り出す。無ければ None。"""
    response = getattr(error, "response", None)
    if response is None:
        return None
    try:
        value = response.headers.get("retry-after")
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _call_one(
    endpoint: Endpoint,
    deployment: str,
    *,
    prompt: str,
    quality: str,
    reference_image_path: str | None,
) -> GeneratedImage:
    """1 つのエンドポイントで画像生成を試みる。

    一時的エラーは _RetriableError に包んで投げ、恒久的エラー（認証・404・コンテンツ
    フィルタ等）はそのまま伝播する。
    """
    client = OpenAI(base_url=endpoint.base_url, api_key=_get_token())
    try:
        if reference_image_path:
            with Path(reference_image_path).expanduser().open("rb") as image_file:
                result = client.images.edit(
                    model=deployment,
                    image=image_file,
                    prompt=prompt,
                    size=_IMAGE_SIZE,
                    quality=quality,
                    n=1,
                )
        else:
            result = client.images.generate(
                model=deployment,
                prompt=prompt,
                size=_IMAGE_SIZE,
                quality=quality,
                n=1,
            )
    except RateLimitError as error:  # 429: 別リージョンへ
        raise _RetriableError(error, _retry_after_seconds(error)) from error
    except (APITimeoutError, APIConnectionError) as error:  # 接続・タイムアウト: 別リージョンへ
        raise _RetriableError(error, None) from error
    except InternalServerError as error:  # 5xx: 別リージョンへ
        raise _RetriableError(error, _retry_after_seconds(error)) from error
    except APIStatusError as error:  # それ以外の HTTP エラー
        if error.status_code >= 500:
            raise _RetriableError(error, _retry_after_seconds(error)) from error
        raise  # 400/401/403/404 等は恒久的。フェイルオーバーせず伝播

    b64 = result.data[0].b64_json
    if not b64:
        raise RuntimeError("Foundry からの応答に画像データが含まれていません。")
    return GeneratedImage(
        png_bytes=base64.b64decode(b64),
        size=_IMAGE_SIZE,
        model=deployment,
        endpoint=endpoint.base_url,
    )


# --- 公開 API ---------------------------------------------------------------


def generate(
    *,
    prompt: str,
    quality: str = "medium",
    reference_image_path: str | None = None,
) -> GeneratedImage:
    """画像を生成する。

    プールから順にエンドポイントを取得し、429 や一時エラーなら次のリージョンへ
    フェイルオーバーする。reference_image_path 指定時は images.edit を使う。
    """
    pool = _get_pool()
    deployment = _resolve_deployment()

    last_original: Exception | None = None
    waited = False
    api_attempts = 0

    # API を実際に叩く回数はプール数まで。フェイルオーバーで全リージョンを一巡する。
    while api_attempts < pool.size:
        try:
            endpoint = pool.acquire()
        except AllEndpointsCoolingDown as cooling:
            # 全リージョンがクールダウン中。短い待ちなら 1 回だけ待って再挑戦する。
            if not waited and cooling.wait_seconds <= _MAX_WAIT_SECONDS:
                time.sleep(cooling.wait_seconds + 0.5)
                waited = True
                continue
            raise

        api_attempts += 1
        try:
            image = _call_one(
                endpoint,
                deployment,
                prompt=prompt,
                quality=quality,
                reference_image_path=reference_image_path,
            )
        except _RetriableError as retriable:
            pool.report_failure(endpoint, retriable.retry_after)
            last_original = retriable.original
            continue

        pool.report_success(endpoint)
        return image

    if last_original is not None:
        raise last_original
    raise RuntimeError("すべてのリージョンで画像生成に失敗しました。")
