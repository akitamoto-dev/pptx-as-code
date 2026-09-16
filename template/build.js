#!/usr/bin/env node
// build.js — デッキのビルド入口。OS を問わず node だけで動く。
//
//   node build.js                 deck.json の parts を読み込み、pptx → normalize → PDF → PNG まで行う
//   node build.js --no-pdf        pptx の生成と規格検査だけ（LibreOffice が無い環境でも動く）
//   node build.js --no-png        PDF まで
//   node build.js --pages 3-5     PNG にするページ範囲を絞る
//   node build.js --name sample   出力名を deck.json より優先する
//   node build.js --parts a,b     読み込むパーツを deck.json より優先する
//
// 出力: <name>.pptx、<name>.pdf、preview/<name>-001.png ...
// 流れ: (1) pptxgenjs で pptx を生成し、各スライドの内部名を実タイトルにする（PDF のしおり用）
//       (2) tools/normalize.py で OOXML の規格違反を直し、--check で 0 件を確認する（違反が残れば PDF を出さず終了）
//       (3) LibreOffice で PDF に変換する（プロファイルは作業ディレクトリ配下に分離）
//       (4) tools/render.py（PyMuPDF）か pdftoppm で PNG にする
// 無い道具があればその段階で止まらず、できたところまでを報告する。
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { pathToFileURL } = require("url");

const WORK = __dirname;
const SRC = path.join(WORK, "deck-src");
const TOOLS = path.join(WORK, "tools");
const WIN = process.platform === "win32";

// ---- 引数 ----
const args = { noPdf: false, noPng: false, pages: null, name: null, parts: null, dpi: 110 };
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === "--no-pdf") args.noPdf = true;
  else if (a === "--no-png") args.noPng = true;
  else if (a === "--pages") args.pages = argv[++i];
  else if (a === "--name") args.name = argv[++i];
  else if (a === "--parts") args.parts = argv[++i];
  else if (a === "--dpi") args.dpi = +argv[++i];
  else if (a === "-h" || a === "--help") { console.log(fs.readFileSync(__filename, "utf8").split("\n").slice(1, 15).map((l) => l.replace(/^\/\/ ?/, "")).join("\n")); process.exit(0); }
  else if (!a.startsWith("-") && !args.name) args.name = a;
  else fail(`不明な引数: ${a}`);
}

function fail(msg) { console.error("エラー: " + msg); process.exit(1); }
function note(msg) { console.log("  " + msg); }

// ---- 設定 ----
const cfgPath = path.join(WORK, "deck.json");
const cfg = fs.existsSync(cfgPath) ? JSON.parse(fs.readFileSync(cfgPath, "utf8")) : {};
const NAME = args.name || cfg.name || "deck";
const PARTS = args.parts ? args.parts.split(",").map((s) => s.trim()).filter(Boolean) : (cfg.parts || ["sample"]);
const OUT = path.join(WORK, `${NAME}.pptx`);
const PDF = path.join(WORK, `${NAME}.pdf`);
const PREVIEW = path.join(WORK, "preview");

// ---- 外部コマンドの探索 ----
function run(cmd, cmdArgs, opts = {}) {
  return spawnSync(cmd, cmdArgs, { encoding: "utf8", shell: WIN && !opts.noShell, ...opts });
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
// Python 3 の起動コマンド（python3 / python / py -3 の順）
function findPython() {
  const cands = WIN ? [["python", []], ["py", ["-3"]], ["python3", []]] : [["python3", []], ["python", []]];
  for (const [cmd, pre] of cands) {
    const r = run(cmd, [...pre, "--version"]);
    if (r.status === 0 && /^Python 3/.test((r.stdout || "") + (r.stderr || ""))) return [cmd, ...pre];
  }
  return null;
}
// LibreOffice の実行ファイル（環境変数 SOFFICE → PATH → 既定の導入先）
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
// pptxgenjs（作業ディレクトリの node_modules → グローバル導入）
function loadPptxgen() {
  try { return require("pptxgenjs"); } catch (_) { /* 次へ */ }
  const r = run(WIN ? "npm.cmd" : "npm", ["root", "-g"]);
  if (r.status === 0) {
    try { return require(path.join(r.stdout.trim(), "pptxgenjs")); } catch (_) { /* 次へ */ }
  }
  return fail("pptxgenjs が見つかりません。作業ディレクトリで npm install を実行してください。");
}
// jszip（pptxgenjs の依存。グローバル導入では pptxgenjs/node_modules 配下にネストする）
function loadJSZip() {
  try { return require("jszip"); } catch (_) { /* 次へ */ }
  try { const { createRequire } = require("module"); return createRequire(require.resolve("pptxgenjs"))("jszip"); } catch (_) { return null; }
}

// ---- (1) pptx の生成 ----
async function buildPptx() {
  const pptxgen = loadPptxgen();
  const pres = new pptxgen();
  const theme = JSON.parse(fs.readFileSync(path.join(SRC, "theme.json"), "utf8"));
  // pptxgenjs 組み込みの LAYOUT_16x9 は 10 x 5.625 inch で PowerPoint 既定の 13.33 x 7.5 と異なる。
  // フォントサイズは絶対単位なので、キャンバスが小さいと文字が相対的に大きく見える。必ず theme の値で定義する
  pres.defineLayout({ name: "THEME", width: theme.layout.width, height: theme.layout.height });
  pres.layout = "THEME";

  // 生成順にスライドを集める（pptxgenjs は追加順に slide1.xml.. を書くので添字がスライド番号）
  const slides = [];
  const origAddSlide = pres.addSlide.bind(pres);
  pres.addSlide = (...a) => { const s = origAddSlide(...a); slides.push(s); return s; };

  const L = require(path.join(SRC, "lib.js"))(pres, WORK);
  for (const name of PARTS) {
    const file = path.join(SRC, `${name}.js`);
    if (!fs.existsSync(file)) fail(`パーツが見つかりません: deck-src/${name}.js（deck.json の parts を確認）`);
    require(file)(pres, L);
  }
  if (!slides.length) fail("スライドが 1 枚もありません");

  await pres.writeFile({ fileName: OUT });
  await setSlideNames(OUT, slides.map((s) => s.__pdftitle));
  console.log(`(1) pptx: ${path.relative(WORK, OUT)}（${slides.length} 枚）`);
  return slides.length;
}
// 各スライドの <p:cSld name> を実タイトルにする。LibreOffice の PDF 変換はこの名前をしおりに使う
async function setSlideNames(file, titles) {
  const JSZip = loadJSZip();
  if (!JSZip) { note("jszip を解決できないため PDF のしおり名は既定のまま（pptx は生成済み）"); return; }
  const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  for (let i = 0; i < titles.length; i++) {
    if (!titles[i]) continue;
    const entry = zip.file(`ppt/slides/slide${i + 1}.xml`);
    if (!entry) continue;
    let xml = await entry.async("string");
    xml = xml.replace(/<p:cSld(?:\s+name="[^"]*")?>/, `<p:cSld name="${esc(titles[i])}">`);
    zip.file(`ppt/slides/slide${i + 1}.xml`, xml);
  }
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

// ---- (2) 規格違反の正規化と検査 ----
function normalize(py) {
  if (!py) { note("Python 3 が無いため normalize を省略。PowerPoint で開く前に tools/normalize.py を通すこと"); return true; }
  const script = path.join(TOOLS, "normalize.py");
  const r1 = run(py[0], [...py.slice(1), script, OUT]);
  process.stdout.write("(2) " + (r1.stdout || "") + (r1.stderr || ""));
  if (r1.status !== 0) fail("normalize に失敗");
  const r2 = run(py[0], [...py.slice(1), script, OUT, "--check"]);
  process.stdout.write("    " + (r2.stdout || "") + (r2.stderr || ""));
  if (r2.status !== 0) { console.error("エラー: 規格違反が残っているため PDF を出さない。定義側の addShape 直呼びなどを見直す"); process.exit(1); }
  return true;
}

// ---- (3) PDF 変換 ----
function toPdf() {
  if (fs.existsSync(PDF)) fs.unlinkSync(PDF);
  const soffice = findSoffice();
  if (!soffice) { note("(3) LibreOffice が無いため PDF は生成しない。pptx を PowerPoint で開いて確認する"); return false; }
  fontCheck();
  // LibreOffice はプロファイルを共有すると別ディレクトリの同時変換が無言で失敗するため、作業ディレクトリ配下に分離する
  const profile = pathToFileURL(path.join(WORK, ".soffice-profile")).href;
  const r = run(soffice, [`-env:UserInstallation=${profile}`, "--headless", "--convert-to", "pdf", "--outdir", WORK, OUT], { noShell: true, timeout: 180000 });
  if (!fs.existsSync(PDF)) { console.error("エラー: PDF 変換に失敗\n" + (r.stdout || "") + (r.stderr || "")); return false; }
  console.log(`(3) pdf: ${path.relative(WORK, PDF)}（LibreOffice）`);
  return true;
}
// テーマのフォントが無い環境では PDF が代替フォントで描画される。気づけるように一言出す
function fontCheck() {
  if (WIN || !which("fc-list")) return;
  const theme = JSON.parse(fs.readFileSync(path.join(SRC, "theme.json"), "utf8"));
  const r = run("fc-list", [":", "family"]);
  if (r.status === 0 && !r.stdout.includes(theme.fonts.body)) {
    note(`フォント「${theme.fonts.body}」が無いため、PDF は代替フォントで描画される（PowerPoint では正しく出る）`);
  }
}

// ---- (4) PNG 化 ----
function toPng(py) {
  if (!fs.existsSync(PREVIEW)) fs.mkdirSync(PREVIEW);
  // 古いページが残らないよう同名の PNG を消す
  for (const f of fs.readdirSync(PREVIEW)) if (f.startsWith(`${NAME}-`) && f.endsWith(".png")) fs.unlinkSync(path.join(PREVIEW, f));
  const prefix = path.join(PREVIEW, NAME);
  const pageArgs = args.pages ? ["--pages", args.pages] : [];
  if (py) {
    const r = run(py[0], [...py.slice(1), path.join(TOOLS, "render.py"), PDF, prefix, "--dpi", String(args.dpi), ...pageArgs]);
    if (r.status === 0) { console.log(`(4) png: preview/${NAME}-NNN.png` + (r.stdout ? `（${r.stdout.trim()}）` : "")); return true; }
    note((r.stderr || "").trim());
  }
  const pdftoppm = which("pdftoppm");
  if (!pdftoppm) { note("(4) PyMuPDF も pdftoppm も無いため PNG は生成しない。PDF を直接確認する"); return false; }
  const range = args.pages ? args.pages.split("-") : null;
  const r = run(pdftoppm, ["-png", "-r", String(args.dpi), ...(range ? ["-f", range[0], "-l", range[1] || range[0]] : []), PDF, prefix], { noShell: true });
  if (r.status !== 0) { note("pdftoppm に失敗: " + (r.stderr || "")); return false; }
  // pdftoppm はページ数の桁で名前がぶれるため 3 桁に揃える
  for (const f of fs.readdirSync(PREVIEW)) {
    const m = f.match(new RegExp(`^${NAME.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}-(\\d+)\\.png$`));
    if (m && m[1].length !== 3) fs.renameSync(path.join(PREVIEW, f), path.join(PREVIEW, `${NAME}-${m[1].padStart(3, "0")}.png`));
  }
  console.log(`(4) png: preview/${NAME}-NNN.png（pdftoppm）`);
  return true;
}

// ---- 実行 ----
(async () => {
  const count = await buildPptx();
  const py = findPython();
  normalize(py);
  if (args.noPdf) { console.log(`完了: ${count} 枚。PDF は省略（--no-pdf）`); return; }
  if (!toPdf()) { console.log(`完了: ${count} 枚（pptx のみ）`); return; }
  if (args.noPng) { console.log(`完了: ${count} 枚（pptx, pdf）`); return; }
  toPng(py);
  console.log(`完了: ${count} 枚。preview/ の PNG を目視で確認する（はみ出し・重なり・折り返し）`);
})().catch((e) => { console.error("エラー:", e && e.stack ? e.stack : e); process.exit(1); });
