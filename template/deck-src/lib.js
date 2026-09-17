// deck-src/lib.js — 描画ヘルパー（書式の正）。
//
// 色・フォント・サイズ・座標はすべて同じディレクトリの theme.json から読む。
// スライド定義側はこのヘルパーだけを使い、pptxgenjs の addText / addShape / addTable を直接呼ばない
// （書式が揃わず、負のサイズなど PowerPoint で開けなくなる事故の原因になる）。
// 足りない表現があれば、このファイルにヘルパーを足してから使う。
//
// 使い方（deck-src/<name>.js）:
//   module.exports = function (pres, L) {
//     const s = L.slide();
//     L.title(s, "タイトル");                          // 名詞の体言止め
//     L.keymsg(s, "主張を主語と述語のある文で書きます"); // ですます調
//     L.sec(s, "見出し", 2.0);                         // ＜見出し＞
//     L.BODY(s, "本文はである調で書く。", 2.44, 0.4);
//   };
//
// このファイルは作業ディレクトリへコピーされたものなので、自由に編集してよい（スキルの更新で上書きされない）。
const fs = require("fs");
const path = require("path");

module.exports = function (pres, WORK) {
  const SRC = __dirname;
  const T = JSON.parse(fs.readFileSync(path.join(SRC, "theme.json"), "utf8"));
  const K = T.colors;
  const FONT = T.fonts.body;
  const MONO = T.fonts.code;

  // 役割名の色定数。スライド定義側は const { PRIMARY, DARK, TEXT } = L.C; のように取り出す
  const C = {
    FONT, MONO,
    PRIMARY: K.primary, DARK: K.primaryDark, LIGHT: K.primaryLight,
    PANEL: K.panel, PANEL_LINE: K.panelLine, RULE: K.rule,
    TEXT: K.text, MUTED: K.muted, WHITE: K.white,
    DANGER: K.danger, DANGER_BG: K.dangerBg, DANGER_LINE: K.dangerLine, SAFE: K.safe,
    CODE_BG: K.code.bg, CODE_TEXT: K.code.text, CODE_COMMENT: K.code.comment,
    CODE_STRING: K.code.string, CODE_HL: K.code.highlight,
  };
  const { PRIMARY, DARK, TEXT, WHITE, MUTED, PANEL_LINE, DANGER, RULE } = C;
  const X = T.layout.left;
  const CW = T.layout.contentWidth;
  const [BL, BR] = (T.writing && T.writing.sectionBrackets) || ["＜", "＞"];

  const L = { C, theme: T, X, CW, W: T.layout.width, H: T.layout.height, BOTTOM: T.layout.contentBottom };

  const warned = new Set();
  const warn = (msg) => { if (!warned.has(msg)) { warned.add(msg); console.warn("lib.js: " + msg); } };

  // ---- 文字幅の概算（半角 0.6em・全角 1.0em）。折り返しや自動縮小の判定に使う ----
  // 半角は実測で全角の 0.6 掛け程度。0.5 で見積もると幅を過小評価し、折り返して上の要素と重なる
  const HALF = (T.text && T.text.halfWidthEm) || 0.6;
  L.em = (str) => [...String(str)].reduce((a, c) => a + (c.charCodeAt(0) < 0x100 ? HALF : 1), 0);
  L.widthIn = (str, size) => (L.em(str) * size) / 72;

  // ============================================================ 基本要素

  L.slide = () => { const s = pres.addSlide(); s.background = { color: WHITE }; return s; };

  // 汎用テキスト（ラベル用。既定は太字・中央揃え縦）
  L.T = (s, text, x, y, w, h, o = {}) =>
    s.addText(text, {
      x, y, w, h, fontFace: FONT, fontSize: o.size || T.label.fontSize, bold: o.bold !== false,
      color: o.color || TEXT, align: o.align || "left", valign: o.valign || "middle",
      margin: 0, lineSpacingMultiple: o.lsm || T.label.lineSpacingMultiple,
    });

  // 複数 run のテキスト（部分的に色や太字を変えるとき）。runs は [{ text, options }] の配列
  L.RUNS = (s, runs, x, y, w, h, o = {}) =>
    s.addText(runs, {
      x, y, w, h, fontFace: FONT, fontSize: o.size || T.body.fontSize, bold: !!o.bold,
      color: o.color || TEXT, align: o.align || "left", valign: o.valign || "top",
      margin: 0, lineSpacingMultiple: o.lsm || T.body.lineSpacingMultiple,
    });

  // ハイパーリンク付きの run。本文中の根拠語句や出典行に使う
  L.LINK = (text, url, o = {}) => ({
    text,
    options: { hyperlink: { url }, color: o.color || PRIMARY, underline: { style: "sng" }, ...(o.size ? { fontSize: o.size } : {}), ...(o.bold ? { bold: true } : {}) },
  });

  // 画像。パスは作業ディレクトリからの相対（例: "assets/icons/shield_primary.png"）
  L.IMG = (s, f, x, y, w, h) => {
    const p = path.isAbsolute(f) ? f : path.join(WORK, f);
    if (!fs.existsSync(p)) { warn(`画像が見つからないため省略: ${f}`); return null; }
    return s.addImage({ path: p, x, y, w, h });
  };
  // アイコン（assets/icons/<name>.png）。正方形なので w=h
  L.ICON = (s, name, x, y, size) => L.IMG(s, `assets/icons/${name}.png`, x, y, size, size);

  // 角丸の枠。o.fill 塗り／o.lineColor 枠色／o.lw 枠幅／o.r 角丸／o.dash 破線／o.line=false 枠なし／o.alpha 透明度
  L.BOX = (s, x, y, w, h, o = {}) =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h, rectRadius: o.r == null ? T.shapes.boxRadius : o.r,
      fill: o.fill ? { color: o.fill, ...(o.alpha != null ? { transparency: o.alpha } : {}) } : { type: "none" },
      line: o.line === false ? { type: "none" } : { color: o.lineColor || PRIMARY, width: o.lw || T.shapes.boxLineWidth, ...(o.dash ? { dashType: "dash" } : {}) },
    });
  // 楕円。オプションは BOX と同じ
  L.OVAL = (s, x, y, w, h, o = {}) =>
    s.addShape(pres.shapes.OVAL, {
      x, y, w, h,
      fill: o.fill ? { color: o.fill, ...(o.alpha != null ? { transparency: o.alpha } : {}) } : { type: "none" },
      line: o.line === false ? { type: "none" } : { color: o.lineColor || PRIMARY, width: o.lw || T.shapes.boxLineWidth, ...(o.dash ? { dashType: "dash" } : {}) },
    });
  // ピル（見出しラベル）。既定は青地に白文字
  L.PILL = (s, x, y, w, h, text, o = {}) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: h / 2, fill: { color: o.fill || PRIMARY }, line: { color: o.fill || PRIMARY, width: 1 } });
    s.addText(text, { x, y: y - 0.01, w, h, fontFace: FONT, fontSize: o.size || T.shapes.pillFontSize, bold: true, color: o.color || WHITE, align: "center", valign: "middle", margin: 0 });
  };
  // 矢頭付きの矢印。始点 (x1,y1) → 終点 (x2,y2)。o.both 双方向／o.arrow=false 矢頭なし／o.dash 破線
  // 右から左・下から上へ引くと w/h が負になり、そのまま出力すると PowerPoint がファイルを破損と判定して開けない。
  // 外接矩形を正の値で与え、向きは flipH/flipV で表す（見た目は同じ）。
  L.ARROW = (s, x1, y1, x2, y2, o = {}) => {
    const dx = x2 - x1, dy = y2 - y1;
    return s.addShape(pres.shapes.LINE, {
      x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(dx), h: Math.abs(dy),
      ...(dx < 0 ? { flipH: true } : {}), ...(dy < 0 ? { flipV: true } : {}),
      line: {
        color: o.color || PRIMARY, width: o.w || T.shapes.arrowWidth,
        ...(o.dash ? { dashType: "dash" } : {}),
        ...(o.both ? { beginArrowType: "triangle", endArrowType: "triangle" } : {}),
        ...(o.arrow === false || o.both ? {} : { endArrowType: "triangle" }),
      },
    });
  };
  // 区切り線（灰の細線）
  L.VLINE = (s, x, y, h, o = {}) =>
    s.addShape(pres.shapes.LINE, { x, y, w: 0, h, line: { color: o.color || RULE, width: o.w || T.shapes.ruleWidth, ...(o.dash ? { dashType: "dash" } : {}) } });
  L.HLINE = (s, x, y, w, o = {}) =>
    s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: o.color || RULE, width: o.w || T.shapes.ruleWidth, ...(o.dash ? { dashType: "dash" } : {}) } });
  // タグ（既定は危険を示す赤地に白文字＋警告アイコン）。o.fill で色、o.icon でアイコン名を変える
  L.TAG = (s, x, y, w, h, text, o = {}) => {
    const fill = o.fill || DANGER;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: T.shapes.tagRadius, fill: { color: fill }, line: { color: fill, width: 1 } });
    const icon = o.icon === undefined ? "warning_white" : o.icon;
    const has = icon && fs.existsSync(path.join(WORK, "assets", "icons", `${icon}.png`));
    if (has) L.ICON(s, icon, x + 0.09, y + (h - 0.2) / 2, 0.2);
    const pad = has ? 0.34 : 0.16;
    L.T(s, text, x + pad, y, w - pad - 0.08, h, { size: o.size || 11, color: o.color || WHITE, align: o.align || "left" });
  };

  // ============================================================ 階層要素
  // タイトル → キーメッセージ → ＜見出し＞ → 本文・図・表 → 出典

  // タイトル（名詞の体言止め）。幅に収まらないときは最小サイズまで自動で縮小する。
  // 第 3 引数 ja を渡すと、英語名の後ろに日本語訳を小さく括弧書きで添える
  L.title = (s, t, ja) => {
    s.__pdftitle = t;
    const tt = T.title;
    let ts = tt.fontSize, js = tt.fontSize * 0.57;
    const wid = () => L.widthIn(t, ts) + (ja ? L.widthIn(`（${ja}）`, js) : 0);
    while (wid() > tt.w - 0.1 && ja && js > 13) js -= 0.5;
    while (wid() > tt.w - 0.1 && ts > tt.minFontSize) ts -= 0.5;
    if (wid() > tt.w - 0.1) warn(`タイトルが幅に収まらない可能性: ${t}`);
    const runs = ja ? [{ text: t }, { text: `（${ja}）`, options: { fontSize: js } }] : t;
    return s.addText(runs, { x: tt.x, y: tt.y, w: tt.w, h: tt.h, fontFace: FONT, fontSize: ts, bold: true, color: PRIMARY, align: "left", valign: "middle", margin: 0, lineSpacingMultiple: tt.lineSpacingMultiple });
  };
  // キーメッセージ（主語と述語のある完全な文。ですます調）。segs は文字列か runs 配列
  L.keymsg = (s, segs, h) => {
    const k = T.keyMessage;
    return s.addText(segs, { x: k.x, y: k.y, w: k.w, h: h || k.h, fontFace: FONT, fontSize: k.fontSize, bold: true, color: TEXT, align: "left", valign: "top", margin: 0, lineSpacingMultiple: k.lineSpacingMultiple });
  };
  // ＜見出し＞。段組みにするときは o.x / o.w で位置と幅を指定する
  L.sec = (s, t, y, o = {}) =>
    L.T(s, `${BL}${t}${BR}`, o.x || X, y, o.w || CW, T.section.h, { size: o.size || T.section.fontSize, color: PRIMARY });
  // 本文（である調）。text は文字列か runs 配列。o.x / o.w で段組み、o.size で縮小（下限は theme の minFontSize）
  L.BODY = (s, text, y, h, o = {}) =>
    s.addText(text, { x: o.x || X, y, w: o.w || CW, h, fontFace: FONT, fontSize: o.size || T.body.fontSize, bold: !!o.bold, color: o.color || TEXT, align: o.align || "left", valign: o.valign || "top", margin: 0, lineSpacingMultiple: o.lsm || T.body.lineSpacingMultiple });
  // 箇条書き。items の各文字列で【】に囲んだ範囲は濃い青で強調される（項目の要点や用語に使う）
  L.BULLETS = (s, items, y, h, o = {}) => {
    const runs = [];
    items.forEach((t, i) => {
      const segs = [];
      let hl = false;
      String(t).split(/(【|】)/).forEach((seg) => {
        if (seg === "【") { hl = true; return; }
        if (seg === "】") { hl = false; return; }
        if (seg !== "") segs.push([seg, hl]);
      });
      // pptxgenjs は run ごとに段落設定（a:pPr）を書き出すため、同じ項目の run には同じ段落設定を与える
      // （食い違うと normalize が「同一段落に異なる段落設定」として止める）
      const para = i < items.length - 1 ? { paraSpaceAfter: T.bullets.paraSpaceAfter } : {};
      segs.forEach(([text, isHl], j) => {
        // pptxgenjs の bullet オプションは部分着色の複数 run と両立しないため、行頭記号は文字として埋め込む
        runs.push({
          text: (j === 0 ? "•  " : "") + text,
          options: {
            color: isHl ? (o.hl || DARK) : (o.color || TEXT), ...(isHl ? { bold: true } : {}),
            ...para, ...(j === segs.length - 1 ? { breakLine: true } : {}),
          },
        });
      });
    });
    return s.addText(runs, { x: o.x || X, y, w: o.w || CW, h, fontFace: FONT, fontSize: o.size || T.bullets.fontSize, bold: false, color: TEXT, align: "left", valign: "top", margin: 0, lineSpacingMultiple: o.lsm || T.bullets.lineSpacingMultiple });
  };
  // 図の上に置く短い説明（灰）。図の下には置かない
  L.CAP = (s, segs, y, h, o = {}) =>
    s.addText(segs, { x: o.x || X, y, w: o.w || CW, h: h || 0.4, fontFace: FONT, fontSize: o.size || T.caption.fontSize, bold: false, color: MUTED, align: "left", valign: "top", margin: 0, lineSpacingMultiple: T.caption.lineSpacingMultiple });
  // 出典行（最下部に固定）。runs には L.LINK を混ぜられる。全角約 95 字が 1 行の上限
  L.SRC = (s, runs) => {
    const r = T.source;
    return s.addText(runs, { x: r.x, y: r.y, w: r.w, h: r.h, fontFace: FONT, fontSize: r.fontSize, bold: false, color: MUTED, align: "left", valign: "bottom", margin: 0 });
  };

  // ============================================================ 表

  // セル。o.bold / o.color / o.fill / o.align / o.size / o.margin（[上, 右, 下, 左] pt）
  L.cell = (t, o = {}) => ({
    text: t,
    options: {
      fontFace: FONT, fontSize: o.size || T.table.fontSize, bold: !!o.bold, color: o.color || TEXT,
      align: o.align || "left", valign: o.valign || "middle",
      fill: o.fill ? { color: o.fill } : undefined, margin: o.margin || T.table.cellMargin,
    },
  });
  // ヘッダーセル用のオプション（青地に白文字）
  L.hOpt = { bold: true, color: WHITE, align: "center", fill: PRIMARY, size: T.table.headerFontSize };
  // 行の高さを見積もる（各セルの折り返し行数から）。TBL で rowH を省略したときに使われる
  L.rowH = (rows, colW, o = {}) => {
    const textOf = (c) => {
      const t = c && c.text !== undefined ? c.text : c;
      return Array.isArray(t) ? t.map((r) => (typeof r === "string" ? r : r.text || "")).join("") : String(t == null ? "" : t);
    };
    return rows.map((row) => {
      let maxLines = 1, size = T.table.fontSize;
      row.forEach((c, j) => {
        const opt = (c && c.options) || {};
        const sz = opt.fontSize || T.table.fontSize;
        const m = opt.margin || T.table.cellMargin;
        const avail = colW[j] - (m[1] + m[3]) / 72 - 0.02;
        const lines = textOf(c).split("\n").reduce((a, ln) => a + Math.max(1, Math.ceil(L.widthIn(ln, sz) / Math.max(avail, 0.3))), 0);
        if (lines > maxLines) maxLines = lines;
        if (sz > size) size = sz;
      });
      const m = T.table.cellMargin;
      return +(maxLines * size * (o.lsm || 1.2) / 72 + (m[0] + m[2]) / 72 + 0.08).toFixed(2);
    });
  };
  // 表。rows は L.cell の 2 次元配列、colW は列幅（合計が幅）、rowH は行高（省略時は見積もり）。o.x / o.w で段組み
  L.TBL = (s, rows, y, colW, rowH, o = {}) =>
    s.addTable(rows, {
      x: o.x || X, y, w: o.w || colW.reduce((a, b) => a + b, 0), colW, rowH: rowH || L.rowH(rows, colW),
      border: { type: "solid", color: PANEL_LINE, pt: T.table.borderWidth }, valign: "middle",
    });

  // ============================================================ コード

  // コードボックス（エディタ風のダーク配色）。code は文字列か行の配列。
  // # や // のコメントは緑、"文字列" はオレンジ、o.hl の行番号（0 始まり）は赤で強調する
  L.CODE = (s, code, x, y, w, h, o = {}) => {
    const cc = T.code;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: cc.radius, fill: { color: C.CODE_BG }, line: { color: C.CODE_BG, width: 0.5 } });
    const lines = Array.isArray(code) ? code : String(code).split("\n");
    const hl = o.hl || [];
    const runs = [];
    lines.forEach((ln, i) => {
      const lineRuns = [];
      if (!ln.length) lineRuns.push({ text: " ", options: { color: C.CODE_TEXT } });
      else if (hl.includes(i)) lineRuns.push({ text: ln, options: { color: C.CODE_HL } });
      else {
        let codePart = ln, comment = "";
        const lead = ln.trimStart();
        if (lead.startsWith("#") || lead.startsWith("//")) { codePart = ""; comment = ln; }
        else {
          const m = ln.match(/\s+(#|\/\/)(?!\S*:)/);
          if (m) { codePart = ln.slice(0, m.index); comment = ln.slice(m.index); }
        }
        if (codePart) codePart.split(/(f?"[^"]*"|'[^']*')/).forEach((sg) => {
          if (sg) lineRuns.push({ text: sg, options: { color: /^(f?"|')/.test(sg) ? C.CODE_STRING : C.CODE_TEXT } });
        });
        if (comment) lineRuns.push({ text: comment, options: { color: C.CODE_COMMENT } });
        if (!lineRuns.length) lineRuns.push({ text: " ", options: { color: C.CODE_TEXT } });
      }
      lineRuns[lineRuns.length - 1].options.breakLine = i < lines.length - 1;
      runs.push(...lineRuns);
    });
    return s.addText(runs, {
      x: x + cc.paddingX, y: y + cc.paddingY, w: w - cc.paddingX * 2, h: h - cc.paddingY * 2,
      fontFace: MONO, fontSize: o.size || cc.fontSize, align: "left", valign: "top",
      margin: 0, lineSpacingMultiple: o.lsm || cc.lineSpacingMultiple,
    });
  };

  // ============================================================ 章扉・節扉・目次

  // 章扉（濃い青の全面背景）。label は章番号など、subtitle は任意
  L.divider = (label, t, subtitle) => {
    const d = T.divider;
    const s = pres.addSlide();
    s.__pdftitle = (label ? label + " " : "") + t;
    s.background = { color: DARK };
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: L.W, h: d.barHeight, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0, y: L.H - d.barHeight, w: L.W, h: d.barHeight, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
    if (label) s.addText(label, { x: 0.9, y: 1.16, w: 11.5, h: 0.45, fontFace: FONT, fontSize: d.labelFontSize, bold: true, color: d.labelColor, align: "left", valign: "middle", margin: 0, charSpacing: 4 });
    s.addText(t, { x: 0.9, y: 1.66, w: 11.5, h: 0.9, fontFace: FONT, fontSize: d.titleFontSize, bold: true, color: WHITE, align: "left", valign: "middle", margin: 0 });
    if (subtitle) s.addText(subtitle, { x: 0.9, y: 2.55, w: 11.5, h: 0.5, fontFace: FONT, fontSize: d.subtitleFontSize, color: d.subtitleColor, align: "left", valign: "middle", margin: 0 });
    return s;
  };
  // 節扉（白背景・左に青の縦帯）。章の中を節に分けるときに使う
  L.subDivider = (label, t, subtitle) => {
    const d = T.subDivider;
    const s = L.slide();
    s.__pdftitle = (label ? label + " " : "") + t;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.9, y: 2.35, w: 0.12, h: 1.55, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
    if (label) s.addText(label, { x: 1.25, y: 2.3, w: 11.0, h: 0.4, fontFace: FONT, fontSize: d.labelFontSize, bold: true, color: MUTED, align: "left", valign: "middle", margin: 0, charSpacing: 4 });
    s.addText(t, { x: 1.25, y: 2.72, w: 11.0, h: 0.8, fontFace: FONT, fontSize: d.titleFontSize, bold: true, color: DARK, align: "left", valign: "middle", margin: 0 });
    if (subtitle) s.addText(subtitle, { x: 1.25, y: 3.5, w: 11.0, h: 0.45, fontFace: FONT, fontSize: d.subtitleFontSize, color: MUTED, align: "left", valign: "middle", margin: 0 });
    return s;
  };
  // 目次。items は [{ no: "1", title: "章名", note: "任意の補足" }] の配列
  L.toc = (s, items, o = {}) => {
    const tc = T.toc;
    let y = o.y || 1.5;
    items.forEach((it) => {
      L.PILL(s, X + 0.1, y + 0.1, 0.7, 0.36, it.no, { size: 12 });
      L.T(s, it.title, X + 1.05, y, 6.5, tc.rowHeight - 0.05, { size: tc.fontSize, color: DARK });
      if (it.note) L.T(s, it.note, X + 7.6, y, CW - 7.6, tc.rowHeight - 0.05, { size: 11, color: MUTED, bold: false });
      y += tc.rowHeight;
    });
  };

  return L;
};
