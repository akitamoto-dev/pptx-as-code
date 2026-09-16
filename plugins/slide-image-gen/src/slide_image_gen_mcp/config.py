"""接続先などの利用者固有値を env ファイルから読み込む。

MCP の起動定義（プラグインやクライアントの設定ファイル）に利用者固有の値を書かずに済むよう、
サーバー自身が起動時に ``KEY=VALUE`` 形式のファイルを読み、環境変数へ取り込む。
既に設定されている環境変数は上書きしない（環境変数が優先）。

探索順（最初に見つかった 1 ファイルだけを読む）:

1. 環境変数 ``SLIDE_IMAGE_GEN_ENV_FILE`` が指すファイル
2. カレントディレクトリの ``.slide-image-gen.env``
3. ``~/.config/slide-image-gen/env``（Windows は ``%APPDATA%\\slide-image-gen\\env``）

形式は 1 行 1 組の ``KEY=VALUE``。``#`` で始まる行はコメント、空行は無視、
値の前後の引用符（``"`` / ``'``）は外す。

stdout は MCP の通信に使うため、ここからの通知はすべて stderr に出す。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 明示的に env ファイルの場所を指定する環境変数
ENV_FILE_VAR = "SLIDE_IMAGE_GEN_ENV_FILE"

# カレントディレクトリに置く env ファイル名（案件ごとに接続先を変えるとき）
LOCAL_ENV_FILE = ".slide-image-gen.env"


def user_env_file() -> Path:
    """利用者ごとの既定の env ファイルのパスを返す。"""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "slide-image-gen" / "env"
    return Path.home() / ".config" / "slide-image-gen" / "env"


def candidate_paths() -> list[Path]:
    """探索順に候補パスを返す。"""
    candidates: list[Path] = []
    explicit = os.environ.get(ENV_FILE_VAR)
    if explicit and explicit.strip():
        candidates.append(Path(explicit.strip()).expanduser())
    candidates.append(Path.cwd() / LOCAL_ENV_FILE)
    candidates.append(user_env_file())
    return candidates


def find_env_file() -> Path | None:
    """探索順で最初に見つかった env ファイルのパスを返す。無ければ None。"""
    for path in candidate_paths():
        if path.is_file():
            return path
    return None


def parse_env_file(text: str) -> dict[str, str]:
    """``KEY=VALUE`` 形式のテキストを辞書にする。

    ``#`` で始まる行と空行は無視する。値の前後の空白と、対になった引用符は外す。
    ``=`` を含まない行は読み飛ばす。同じキーが複数あれば後の行が勝つ。
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_env_file() -> Path | None:
    """env ファイルを 1 つ読み、未設定の環境変数だけを設定する。

    読み込んだファイルのパスを返す（見つからなければ None）。
    """
    explicit = os.environ.get(ENV_FILE_VAR)
    if explicit and explicit.strip() and not Path(explicit.strip()).expanduser().is_file():
        print(
            f"[slide-image-gen] {ENV_FILE_VAR} が指すファイルが見つかりません: {explicit.strip()}",
            file=sys.stderr,
        )

    path = find_env_file()
    if path is None:
        return None

    try:
        # utf-8-sig は先頭の BOM（Windows のエディタが付けることがある）を読み飛ばす
        values = parse_env_file(path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        print(f"[slide-image-gen] env ファイルを読めません: {path} ({error})", file=sys.stderr)
        return None

    applied = 0
    for key, value in values.items():
        if key not in os.environ:
            os.environ[key] = value
            applied += 1

    print(f"[slide-image-gen] env ファイルを読み込みました: {path}（{applied} 件を設定）", file=sys.stderr)
    return path
