"""エントリポイント。`uvx slide-image-gen-mcp` で stdio トランスポートとして起動する。"""

from . import config
from .server import mcp


def main() -> None:
    # 接続先などの利用者固有値を env ファイルから環境変数へ取り込む（既にある環境変数が優先）。
    # stdout は MCP 通信に使うため、ここから先も標準出力には何も書かない。
    config.load_env_file()

    # 既定は stdio トランスポート。MCP クライアントが子プロセスとして起動する想定
    mcp.run()


if __name__ == "__main__":
    main()
