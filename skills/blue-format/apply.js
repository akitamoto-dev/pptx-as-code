#!/usr/bin/env node
// blue-format の書式とアイコンを作業ディレクトリへ適用する。
// 使い方: node <このスキル>/apply.js <作業ディレクトリ>
//
// シェルではなく Node で書いてあるのは、Windows でも同じ 1 行で実行できるようにするため。
const fs = require("fs");
const path = require("path");

const HERE = __dirname;
const WORK = process.argv[2] || ".";
const WIN = process.platform === "win32";

if (!fs.existsSync(path.join(WORK, "deck-src"))) {
  const copy = WIN
    ? `Copy-Item -Path "<プラグイン>\\template\\*" -Destination "${WORK}" -Recurse -Force`
    : `cp -r <プラグイン>/template/. ${WORK}/`;
  console.error(`エラー: ${WORK} に deck-src がありません。`);
  console.error(`先に共通の雛形をコピーしてください: ${copy}`);
  process.exit(1);
}

fs.copyFileSync(path.join(HERE, "theme.json"), path.join(WORK, "deck-src", "theme.json"));

const iconsSrc = path.join(HERE, "icons");
const iconsDst = path.join(WORK, "assets", "icons");
fs.mkdirSync(iconsDst, { recursive: true });
const icons = fs.readdirSync(iconsSrc).filter((f) => f === "icons.json" || f.endsWith(".png"));
for (const f of icons) fs.copyFileSync(path.join(iconsSrc, f), path.join(iconsDst, f));

console.log(`書式を適用しました: ${path.join(WORK, "deck-src", "theme.json")}（青基調）`);
console.log(`アイコンを配置しました: ${iconsDst}/（${icons.filter((f) => f.endsWith(".png")).length} 個）`);
console.log();
console.log("見本から始める場合は、次のファイルをコピーしてください。");
console.log(`  ${path.join(HERE, "samples", "sample.js")}`);
console.log(`  → ${path.join(WORK, "deck-src", "sample.js")}`);
console.log(`そのうえで ${path.join(WORK, "deck.json")} の parts を ["sample"] にしてください。`);
