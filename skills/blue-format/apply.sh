#!/usr/bin/env bash
# blue-format の書式とアイコンを作業ディレクトリへ適用する。
# 使い方: bash <このスキル>/apply.sh <作業ディレクトリ>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${1:-.}"

if [ ! -d "$WORK/deck-src" ]; then
  echo "エラー: $WORK に deck-src がありません。" >&2
  echo "先に共通の雛形をコピーしてください: cp -r <プラグイン>/template/. $WORK/" >&2
  exit 1
fi

cp "$HERE/theme.json" "$WORK/deck-src/theme.json"
mkdir -p "$WORK/assets/icons"
cp "$HERE/icons/icons.json" "$HERE/icons/"*.png "$WORK/assets/icons/"

echo "書式を適用しました: $WORK/deck-src/theme.json（青基調）"
echo "アイコンを配置しました: $WORK/assets/icons/（$(ls "$HERE/icons/"*.png | wc -l) 個）"
echo
echo "見本から始める場合は次を実行してください。"
echo "  cp $HERE/samples/sample.js $WORK/deck-src/"
echo "  そのうえで $WORK/deck.json の parts を [\"sample\"] にしてください。"
