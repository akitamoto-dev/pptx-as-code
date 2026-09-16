"""MCP サーバー本体。FastMCP でツールを 1 つだけ公開する。

内部で複数リージョンの Foundry エンドポイントをラウンドロビンし、レート制限（429）時は
別リージョンへ自動フェイルオーバーする（endpoint_pool / foundry_client）。
ツールの戻り値には、実際に生成したリージョンのエンドポイントを含める。
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from . import foundry_client


SERVER_INSTRUCTIONS = """\
Microsoft Foundry の画像生成モデルでスライド用 PNG を 1 枚生成してローカルに保存する。

## 呼び出し時のポイント
- ユーザーが「スライドを画像で作って」「資料を 1 枚絵にして」等と求めた時に呼ぶ。
- `prompt` は直近 1 発話だけでなく **会話履歴を統合** し、ユーザーの意図に沿った
  詳細な指示文を組み立てる。曖昧な指示でも聞き返さず、モデルに裁量を渡して
  1 枚作って結果を見せた方が早い。
- 参考画像を踏襲したい時は `reference_image_path` に **作業ディレクトリ配下のファイルパス**
  （相対または絶対）を渡す。チャットに直接添付された画像はファイルとしては渡せないため、
  その場合はユーザーにファイル保存を依頼するか、画像の内容を言語化して `prompt` に書き起こす。
- `reference_image_path` と `output_dir` は作業ディレクトリ（サーバーのカレントディレクトリ）
  配下に限る。外を指すとエラーになる。

## 複数ページの一括作成
- 複数枚をまとめて作る場合も、このツールを **1 枚ずつ順番に呼べばよい**。
  サーバー側が呼び出しごとに別リージョンへ自動分散し、レート制限（429）が起きた
  リージョンは一時的に避けて別リージョンで再試行する。失敗を気にせず連続で呼んでよい。

## 出力
画像は 16:9 (1792x1008) で生成される。PowerPoint ワイドスクリーンと同じ比率。
"""


mcp = FastMCP(name="slide-image-gen", instructions=SERVER_INSTRUCTIONS)


def _slugify(text: str) -> str:
    """ファイル名用の slug に変換する（ASCII 英数字とハイフンのみ）。"""
    slug = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]+", "", slug)
    return slug[:40] or "slide"


def _resolve_unique_path(directory: Path, base_name: str) -> Path:
    """衝突しないファイル名を決定する。"""
    candidate = directory / f"{base_name}.png"
    n = 2
    while candidate.exists():
        candidate = directory / f"{base_name}_{n}.png"
        n += 1
    return candidate


def _allow_any_path() -> bool:
    """環境変数 SLIDE_IMAGE_GEN_ALLOW_ANY_PATH=1 のときだけ、作業ディレクトリ配下に限る制限を外す。"""
    return os.environ.get("SLIDE_IMAGE_GEN_ALLOW_ANY_PATH", "").strip() == "1"


def _resolve_within_cwd(raw: str, label: str) -> Path:
    """パスを絶対パスに解決し、作業ディレクトリ配下でなければ ToolError を投げる。

    相対パスは作業ディレクトリ（サーバーのカレントディレクトリ）基準で解決する。
    配布物としての最低限の防御で、シンボリックリンクは解決してから判定する。
    """
    cwd = Path.cwd().resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = cwd / path
    path = path.resolve()
    if _allow_any_path() or path == cwd or cwd in path.parents:
        return path
    raise ToolError(
        f"{label} には作業ディレクトリ（{cwd}）配下のパスだけを指定できます: {path}。"
        "制限を外すには環境変数 SLIDE_IMAGE_GEN_ALLOW_ANY_PATH=1 を設定してください。"
    )


@mcp.tool
def generate_slide_image(
    prompt: Annotated[
        str,
        Field(
            description=(
                "画像モデルに渡す最終指示文。会話履歴を統合し、ユーザーの意図に沿った"
                "詳細な指示にする。日本語可。"
            ),
            min_length=1,
        ),
    ],
    quality: Annotated[
        Literal["low", "medium", "high"],
        Field(description="生成品質。high は時間とコストが増えるが日本語の崩れが少ない。"),
    ] = "medium",
    reference_image_path: Annotated[
        str | None,
        Field(
            description=(
                "参考画像のファイルパス（作業ディレクトリ配下。相対または絶対）。指定すると "
                "images.edit API を使い、その画像を入力として生成する。チャットに直接添付された"
                "画像はファイルとして渡せないため、保存してからパスを渡す。"
            )
        ),
    ] = None,
    output_dir: Annotated[
        str | None,
        Field(
            description=(
                "保存先ディレクトリ（作業ディレクトリ配下）。省略時は環境変数 DEFAULT_OUTPUT_DIR "
                "（既定 ./output）を作業ディレクトリ基準で解決する。"
            )
        ),
    ] = None,
    filename_hint: Annotated[
        str | None,
        Field(description="ファイル名ヒント。英数字とハイフンに正規化される（最大 40 文字）。"),
    ] = None,
) -> dict:
    """Microsoft Foundry の画像モデルで 16:9 スライド画像を 1 枚生成して保存する。

    画像サイズは PowerPoint ワイドスクリーンと同比率の 1792x1008 で固定。
    複数リージョンへ自動分散し、レート制限時は別リージョンへフェイルオーバーする。
    reference_image_path と output_dir は作業ディレクトリ配下に限る。

    戻り値:
        - saved_path: 保存した PNG の絶対パス
        - size: 生成サイズ
        - model: 使用したデプロイ名
        - endpoint: 実際に生成したリージョンのエンドポイント
        - bytes: ファイルサイズ
    """
    ref_path: Path | None = None
    if reference_image_path is not None:
        ref_path = _resolve_within_cwd(reference_image_path, "reference_image_path")
        if not ref_path.is_file():
            raise FileNotFoundError(f"reference_image_path が見つかりません: {ref_path}")

    # 既定の保存先も作業ディレクトリ基準で解決し、起動方法によって保存先が変わらないようにする
    target_dir = _resolve_within_cwd(
        output_dir or os.environ.get("DEFAULT_OUTPUT_DIR") or "./output", "output_dir"
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = _resolve_unique_path(target_dir, f"{timestamp}_{_slugify(filename_hint or 'slide')}")

    result = foundry_client.generate(
        prompt=prompt,
        quality=quality,
        reference_image_path=str(ref_path) if ref_path is not None else None,
    )
    save_path.write_bytes(result.png_bytes)

    return {
        "saved_path": str(save_path),
        "size": result.size,
        "model": result.model,
        "endpoint": result.endpoint,
        "bytes": len(result.png_bytes),
    }
