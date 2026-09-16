#!/usr/bin/env bash
# pptx-as-code の実行環境を点検する（読み取り専用。何も導入・変更しない）。
# 使い方: bash doctor.sh [作業ディレクトリ]   作業ディレクトリは node_modules の有無を見るために使う
# 終了コード: Node.js と pptxgenjs が揃っていれば 0、無ければ 1（pptx の生成ができるかの判定）
set -u
WORK="${1:-$PWD}"

have() { command -v "$1" >/dev/null 2>&1; }
row() { printf '%-16s %-6s %s\n' "$1" "$2" "$3"; }
first_line() { "$@" 2>/dev/null | head -1; }

os="$(uname -s)"
if [ -f /.dockerenv ]; then os="$os (コンテナ)"
elif [ -f /proc/version ] && grep -qi microsoft /proc/version; then os="$os (WSL)"; fi
echo "=== pptx-as-code 環境点検: $os ==="
row "項目" "状態" "詳細"
row "----------------" "------" "----------------------------------------"

# ---- Node.js と pptxgenjs（PowerPoint の生成）----
NODE=0; PPTX=0
if have node; then row "Node.js" OK "$(node --version)"; NODE=1; else row "Node.js" なし "https://nodejs.org/ の LTS を導入する"; fi
if have npm; then row "npm" OK "$(npm --version)"; else row "npm" なし "Node.js と一緒に入る"; fi
if [ -d "$WORK/node_modules/pptxgenjs" ]; then row "pptxgenjs" OK "作業ディレクトリ ($WORK)"; PPTX=1
elif have npm && npm ls -g pptxgenjs >/dev/null 2>&1; then row "pptxgenjs" OK "グローバル導入"; PPTX=1
else row "pptxgenjs" なし "作業ディレクトリで npm install を実行する"; fi

# ---- Python（規格検査）----
PY=""
for c in python3 python; do
  if have "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -n "$PY" ]; then row "Python 3" OK "$("$PY" --version 2>&1)"; else row "Python 3" なし "規格の正規化と検査（PowerPoint で開ける保証）に必要"; fi
if have uv; then row "uv" OK "$(first_line uv --version)"; else row "uv" なし "Python スクリプトの依存を自動解決する"; fi

# ---- PDF 変換 ----
SOFF=""
for c in "${SOFFICE:-}" soffice libreoffice /Applications/LibreOffice.app/Contents/MacOS/soffice /opt/libreoffice/program/soffice; do
  [ -z "$c" ] && continue
  if have "$c" || [ -x "$c" ]; then SOFF="$c"; break; fi
done
if [ -n "$SOFF" ]; then row "LibreOffice" OK "$(first_line "$SOFF" --version)"; else row "LibreOffice" なし "PDF 変換に必要（libreoffice-impress）"; fi

# ---- PDF → PNG ----
PNG=0
if [ -n "$PY" ] && { "$PY" -c 'import pymupdf' >/dev/null 2>&1 || "$PY" -c 'import fitz' >/dev/null 2>&1; }; then row "PyMuPDF" OK "PDF を PNG にする"; PNG=1
elif have pdftoppm; then row "pdftoppm" OK "$(pdftoppm -v 2>&1 | head -1)"; PNG=1
else row "PDF→PNG" なし "pip install pymupdf、または poppler-utils（uv があれば自動解決）"; fi

# ---- 日本語フォント ----
FONT=0
if have fc-list; then
  f="$(fc-list : family 2>/dev/null | grep -iE 'yu gothic|meiryo|noto sans cjk|noto sans jp|ipa' | head -1)"
  if [ -n "$f" ]; then row "日本語フォント" OK "$f"; FONT=1; else row "日本語フォント" なし "fonts-noto-cjk など（無いと PDF が文字化けする）"; fi
else
  row "日本語フォント" 不明 "fc-list が無いため判定できない"
fi

# ---- 画像生成と開発 ----
if have az; then row "Azure CLI" OK "$(az version --query '"azure-cli"' -o tsv 2>/dev/null)"; else row "Azure CLI" なし "画像生成 MCP のデプロイに必要"; fi
if have git; then row "git" OK "$(first_line git --version)"; else row "git" なし "clone に必要"; fi

echo
echo "--- 機能ごとの判定 ---"
if [ $NODE = 1 ] && [ $PPTX = 1 ]; then echo "PowerPoint の生成: 可"; else echo "PowerPoint の生成: 不可。Node.js を入れ、作業ディレクトリで npm install する"; fi
if [ -n "$PY" ]; then echo "規格の検査（PowerPoint で開ける保証）: 可"; else echo "規格の検査: 不可。Python 3 が必要"; fi
if [ -n "$SOFF" ] && [ $PNG = 1 ] && [ $FONT = 1 ]; then echo "PDF と画像への変換: 可"
elif [ -n "$SOFF" ]; then echo "PDF と画像への変換: 一部可（PDF は出る。PNG かフォントが不足）"
else echo "PDF と画像への変換: 不可。LibreOffice と日本語フォントが必要"; fi
if have uv; then echo "画像から PowerPoint への変換・アイコンの追加取得: 可"; else echo "画像から PowerPoint への変換・アイコンの追加取得: 不可。uv が必要"; fi
if have az; then echo "画像生成 MCP のデプロイ: 可（Azure サブスクリプションは別途確認）"; else echo "画像生成 MCP のデプロイ: 不可。Azure CLI が必要"; fi

[ $NODE = 1 ] && [ $PPTX = 1 ]
