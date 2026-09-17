#!/usr/bin/env node
// pptx-as-code の実行環境を点検する（読み取り専用。何も導入・変更しない）。
// 使い方: node doctor.js [作業ディレクトリ]   作業ディレクトリは node_modules の有無を見るために使う
// 終了コード: Node.js と pptxgenjs が揃っていれば 0、無ければ 1（pptx の生成ができるかの判定）
//
// シェルではなく Node で書いてあるのは、Windows でも同じ 1 行で実行できるようにするため。
// bash で書くと、Windows では PATH の bash.exe が WSL を起動し、点検結果が
// Windows ではなく WSL のものになる。エラーにならないぶん取り違えに気づけない。
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const WORK = process.argv[2] || process.cwd();
const WIN = process.platform === "win32";

// ---- 表示 ----
// 状態欄に「なし」「不明」が入るため、文字数ではなく表示幅で桁を合わせる
const width = (s) => [...s].reduce((n, c) => n + (/[\u1100-\u115f\u2e80-\ua4cf\ua960-\ua97f\uac00-\ud7a3\uf900-\ufaff\ufe10-\ufe19\ufe30-\ufe6f\uff00-\uff60\uffe0-\uffe6]/.test(c) ? 2 : 1), 0);
const pad = (s, n) => s + " ".repeat(Math.max(0, n - width(s)));
const row = (a, b, c) => console.log(`${pad(a, 16)} ${pad(b, 6)} ${c}`);

// ---- 外部コマンド ----
// シェルを通すと、Node は引数をエスケープせずに連結する。Windows では `import pymupdf` のような
// 空白や引用符を含む引数が壊れるため、シェルが要る .cmd / .bat（npm、az など）に限る
function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, { encoding: "utf8", timeout: 20000, shell: WIN && /\.(cmd|bat)$/i.test(cmd), ...opts });
}
function which(cmd) {
  const exts = WIN ? ["", ".com", ".exe", ".cmd", ".bat"] : [""];
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    for (const ext of exts) {
      const p = path.join(dir, cmd + ext);
      try { if (fs.statSync(p).isFile()) return p; } catch (_) { /* 次へ */ }
    }
  }
  return null;
}
const firstLine = (r) => ((r && (r.stdout || "") + (r.stderr || "")).split("\n")[0] || "").trim();
const readIfExists = (p) => { try { return fs.readFileSync(p, "utf8"); } catch (_) { return ""; } };

// ---- 環境 ----
// エージェントがどこで動いているかを見出しに出す。取得先が塞がれている環境の調べ先が
// これで決まる（SKILL.md の §3.1）ため、コンテナと WSL は明示する
function describeOS() {
  if (WIN) return "Windows";
  if (process.platform === "darwin") return "macOS";
  // コンテナの /proc/version はホストのカーネルを映す。microsoft を含めば
  // Docker Desktop on Windows（WSL2 バックエンド）と分かる
  const microsoft = /microsoft/i.test(readIfExists("/proc/version"));
  if (fs.existsSync("/.dockerenv")) {
    return microsoft ? "Linux (コンテナ / ホストは Windows)" : "Linux (コンテナ / ホストの OS は不明)";
  }
  return microsoft ? "Linux (WSL)" : "Linux";
}

console.log(`=== pptx-as-code 環境点検: ${describeOS()} ===`);
row("項目", "状態", "詳細");
row("----------------", "------", "----------------------------------------");

// ---- Node.js と pptxgenjs（PowerPoint の生成）----
row("Node.js", "OK", process.version); // このスクリプトが動いている時点で存在する
const NPM = WIN ? "npm.cmd" : "npm";
const HAS_NPM = !!which(NPM);
if (HAS_NPM) row("npm", "OK", firstLine(run(NPM, ["--version"])));
else row("npm", "なし", "Node.js と一緒に入る");

let PPTX = false;
if (fs.existsSync(path.join(WORK, "node_modules", "pptxgenjs"))) {
  row("pptxgenjs", "OK", `作業ディレクトリ (${WORK})`);
  PPTX = true;
} else {
  const r = HAS_NPM ? run(NPM, ["root", "-g"]) : null;
  const g = r && r.status === 0 && fs.existsSync(path.join(r.stdout.trim(), "pptxgenjs"));
  if (g) { row("pptxgenjs", "OK", "グローバル導入"); PPTX = true; }
  else row("pptxgenjs", "なし", "作業ディレクトリで npm install を実行する");
}

// ---- Python（規格検査）----
// Windows の python3 は Microsoft Store を開くだけのスタブであることがあるため、
// 名前の有無ではなく --version の出力で実体を確かめる
function findPython() {
  const cands = WIN ? [["python", []], ["py", ["-3"]], ["python3", []]] : [["python3", []], ["python", []]];
  for (const [cmd, pre] of cands) {
    const r = run(cmd, [...pre, "--version"]);
    if (r.status === 0 && /^Python 3/.test(firstLine(r))) return { argv: [cmd, ...pre], version: firstLine(r) };
  }
  return null;
}
const PY = findPython();
if (PY) row("Python 3", "OK", `${PY.version} (${PY.argv.join(" ")})`);
else row("Python 3", "なし", "規格の正規化と検査（PowerPoint で開ける保証）に必要");

const UV = which("uv");
if (UV) row("uv", "OK", firstLine(run("uv", ["--version"])));
else row("uv", "なし", "Python スクリプトの依存を自動解決する");

// ---- PDF 変換 ----
// LibreOffice は PATH に入らない導入のしかたが普通なので、既定の導入先も探す。
// 探索の順序と対象は template/build.js の findSoffice と揃えてある
function findSoffice() {
  if (process.env.SOFFICE && fs.existsSync(process.env.SOFFICE)) return process.env.SOFFICE;
  const names = WIN ? ["soffice.com", "soffice"] : ["soffice", "libreoffice"];
  for (const n of names) { const p = which(n); if (p) return p; }
  const fixed = WIN
    ? ["C:\\Program Files\\LibreOffice\\program\\soffice.com", "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.com"]
    : ["/Applications/LibreOffice.app/Contents/MacOS/soffice", "/opt/libreoffice/program/soffice"];
  for (const p of fixed) if (fs.existsSync(p)) return p;
  return null;
}
const SOFF = findSoffice();
if (SOFF) row("LibreOffice", "OK", firstLine(run(SOFF, ["--version"])) || SOFF);
else row("LibreOffice", "なし", "PDF 変換に必要（libreoffice-impress）");

// ---- PDF → PNG ----
let PNG = false;
const hasModule = (m) => PY && run(PY.argv[0], [...PY.argv.slice(1), "-c", `import ${m}`]).status === 0;
if (hasModule("pymupdf") || hasModule("fitz")) { row("PyMuPDF", "OK", "PDF を PNG にする"); PNG = true; }
else if (which("pdftoppm")) { row("pdftoppm", "OK", firstLine(run("pdftoppm", ["-v"]))); PNG = true; }
// build.js は、手元の Python に PyMuPDF が無ければ uv に取得させて PNG にする
else if (UV) { row("PDF→PNG", "OK", "uv が PyMuPDF を取得して実行する（初回は取得に時間がかかる）"); PNG = true; }
else row("PDF→PNG", "なし", "uv を導入する（PyMuPDF を自動で取得する）。または poppler-utils");

// ---- 日本語フォント ----
// Windows には fc-list が無い。代わりにフォントフォルダを直接見る
// （Yu Gothic は OS 同梱なので、存在しないことはまずない）
let FONT = false;
if (WIN) {
  const dir = path.join(process.env.SystemRoot || "C:\\Windows", "Fonts");
  let found = [];
  try { found = fs.readdirSync(dir).filter((f) => /^(YuGoth|meiryo|msgothic|msmincho)/i.test(f)); } catch (_) { /* 読めなければ無しとして扱う */ }
  if (found.length) { row("日本語フォント", "OK", `${found[0]} ほか (${dir})`); FONT = true; }
  else row("日本語フォント", "なし", `${dir} に日本語フォントが見つからない`);
} else if (which("fc-list")) {
  const f = (run("fc-list", [":", "family"]).stdout || "").split("\n")
    .find((l) => /yu gothic|meiryo|noto sans cjk|noto sans jp|ipa/i.test(l));
  if (f) { row("日本語フォント", "OK", f.trim()); FONT = true; }
  else row("日本語フォント", "なし", "fonts-noto-cjk など（無いと PDF が文字化けする）");
} else {
  row("日本語フォント", "不明", "fc-list が無いため判定できない");
}

// ---- 画像生成と開発 ----
// 引用符付きの --query を渡さずに済むよう、JSON で受け取ってから読む
const AZ_CMD = WIN ? "az.cmd" : "az";
const AZ = which(AZ_CMD);
if (AZ) {
  const r = run(AZ_CMD, ["version", "-o", "json"], { timeout: 60000 });
  let v;
  try { v = JSON.parse(r.stdout)["azure-cli"]; } catch (_) { v = firstLine(r); }
  row("Azure CLI", "OK", v || "バージョンを取得できない");
} else row("Azure CLI", "なし", "画像生成 MCP のデプロイに必要");
if (which("git")) row("git", "OK", firstLine(run("git", ["--version"])));
else row("git", "なし", "clone に必要");

// ---- 機能ごとの判定 ----
console.log();
console.log("--- 機能ごとの判定 ---");
console.log(PPTX ? "PowerPoint の生成: 可" : "PowerPoint の生成: 不可。作業ディレクトリで npm install する");
console.log(PY ? "規格の検査（PowerPoint で開ける保証）: 可" : "規格の検査: 不可。Python 3 が必要");
if (SOFF && PNG && FONT) console.log("PDF と画像への変換: 可");
else if (SOFF) console.log("PDF と画像への変換: 一部可（PDF は出る。PNG かフォントが不足）");
else console.log("PDF と画像への変換: 不可。LibreOffice と日本語フォントが必要");
console.log(UV ? "画像から PowerPoint への変換・アイコンの追加取得: 可" : "画像から PowerPoint への変換・アイコンの追加取得: 不可。uv が必要");
console.log(AZ ? "画像生成 MCP のデプロイ: 可（Azure サブスクリプションは別途確認）" : "画像生成 MCP のデプロイ: 不可。Azure CLI が必要");

process.exit(PPTX ? 0 : 1);
