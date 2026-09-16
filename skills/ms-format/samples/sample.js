// deck-src/sample.js — 見本デッキ（9 枚）。所定フォーマットの代表的な型を 1 枚ずつ示す。
// 新しいデッキを作るときは、ここから最も近い型のブロックを複製して中身を差し替える（座標を発明しない）。
//
// 各スライドの構成: タイトル（体言止め）→ キーメッセージ（ですます調の完全な文）→ ＜見出し＞ → 本文・図・表 → 出典（最下部）
// キーメッセージ以外の文章はである調か体言止め。図の説明文は図の上に置く。

module.exports = function (pres, L) {
  const { PRIMARY, DARK, LIGHT, PANEL, TEXT, WHITE, MUTED, DANGER, DANGER_BG, SAFE, RULE } = L.C;
  const X = L.X, CW = L.CW;

  // ============================================================ 1. 章扉
  L.divider("1", "技術資料の型", "構成・書式・検証の共通ルール");

  // ============================================================ 2. 目次
  (function () {
    const s = L.slide();
    L.title(s, "目次");
    L.toc(s, [
      { no: "1", title: "スライドの階層構造", note: "タイトル・キーメッセージ・見出し・本文の役割" },
      { no: "2", title: "論点に応じた表現の選択", note: "表・図・箇条書き・文章の使い分け" },
      { no: "3", title: "配色の役割", note: "基調色と強調色の使い分け" },
      { no: "4", title: "資料作成の流れ", note: "設計から検証までの手順" },
      { no: "5", title: "スライド定義の書き方", note: "ヘルパーによる定義とビルド" },
      { no: "6", title: "矢印の描き方", note: "PowerPoint で開ける pptx にする条件" },
    ]);
  })();

  // ============================================================ 3. 節扉
  L.subDivider("1-1", "構成と書式", "階層・表現・配色の共通ルール");

  // ============================================================ 4. 箇条書き
  (function () {
    const s = L.slide();
    L.title(s, "スライドの階層構造");
    L.keymsg(s, "各スライドは上から論点・主張・区分・根拠の順に階層を組み、1 枚だけ配布されても内容が伝わるようにします");

    L.sec(s, "階層の役割", 2.0);
    L.BODY(s, "読み手はタイトルとキーメッセージだけで要点を把握し、見出しで区分をたどり、本文で根拠を確かめる。", 2.44, 0.4);
    L.BULLETS(s, [
      "【タイトル】　その 1 枚で扱う論点を、名詞の体言止めで一言にする。疑問文や長い文にしない",
      "【キーメッセージ】　主語と述語のある完全な文で主張を書く。1 文なら句点なし、2 文なら 1 文目だけ句点を付ける",
      "【見出し】　全角の山括弧で囲んだ短い名詞句。そのブロックが何を示すかを言い当てる。個数や主張を入れない",
      "【本文・図・表】　論点の性質に応じて表現を選ぶ。違いは表、構造は図、列挙は箇条書き、結論は文章",
      "【出典】　引用元は最下部の 1 行に固定する。根拠となる語句には本文中でリンクを付ける",
    ], 2.9, 1.7);

    L.sec(s, "守る原則", 4.75);
    L.BODY(s, "階層を守ったうえで、次の原則が読みやすさを決める。", 5.19, 0.36);
    L.BULLETS(s, [
      "【1 スライド 1 論点】　論点が増えたらスライドを分ける。説明に混ぜる軸も増やさない",
      "【自己完結】　章番号や他のスライドへの参照、資料自体への言及を書かない",
      "【まとめ帯を置かない】　主張はキーメッセージに集約し、下部で再掲しない",
      "【説明文は図の上】　図の説明は図の上に置き、本文で図そのものに言及しない",
      "【口語と比喩を避ける】　熟語を使い、身近な例えや造語で説明しない",
    ], 5.6, 1.5);
  })();

  // ============================================================ 5. 比較表
  (function () {
    const s = L.slide();
    L.title(s, "論点に応じた表現の選択");
    L.keymsg(s, "論点の性質に合わせて表・図・箇条書き・文章を使い分けると、読み手が構造を把握しやすくなります");

    L.sec(s, "論点の性質と表現", 2.0);
    L.BODY(s, [
      { text: "文章で足りる論点は文章で書き、図を作ること自体を目的にしない。どの表現も " },
      L.LINK("pptxgenjs のネイティブ要素", "https://gitbrent.github.io/PptxGenJS/", { size: 11.5 }),
      { text: "で作るので、そのまま編集できる。" },
    ], 2.44, 0.4);
    L.TBL(s, [
      [L.cell("論点の性質", L.hOpt), L.cell("表現", L.hOpt), L.cell("例", L.hOpt), L.cell("ヘルパー", L.hOpt)],
      [L.cell("複数の選択肢の違い", { bold: true, color: DARK }), L.cell("表"), L.cell("方式の比較、機能の対応"), L.cell("L.TBL / L.cell")],
      [L.cell("要素の関係・流れ・境界", { bold: true, color: DARK }), L.cell("図"), L.cell("処理の流れ、構成、責任の分界"), L.cell("L.BOX / L.ARROW / L.ICON")],
      [L.cell("並列する項目", { bold: true, color: DARK }), L.cell("箇条書き"), L.cell("前提条件、確認項目、手順"), L.cell("L.BULLETS")],
      [L.cell("結論・判断・理由", { bold: true, color: DARK }), L.cell("文章"), L.cell("方式を選ぶ理由、問題の所在"), L.cell("L.BODY")],
      [L.cell("設定やコマンドの具体", { bold: true, color: DARK }), L.cell("コード"), L.cell("設定ファイル、実行コマンド"), L.cell("L.CODE")],
    ], 2.9, [3.0, 1.6, 4.43, 3.2]);

    L.sec(s, "判断の順序", 5.55);
    L.BODY(s, [
      { text: "まず論点が「違い」か「構造」か「列挙」か「結論」かを決め、それに対応する表現を選ぶ。" },
      { text: "1 枚に複数の性質が混在するときは、表と図と文章の複合構成にする", options: { bold: true, color: DARK } },
      { text: "。図だけで余白が大きいスライドは情報不足の合図であり、説明文や表を足す。" },
    ], 5.99, 0.8);

    L.SRC(s, [{ text: "参考: " }, L.LINK("PptxGenJS のドキュメント（gitbrent.github.io/PptxGenJS）", "https://gitbrent.github.io/PptxGenJS/", { size: 10 })]);
  })();

  // ============================================================ 6. 2 段組みのデータ駆動表
  (function () {
    const s = L.slide();
    L.title(s, "配色の役割");
    L.keymsg(s, "青の濃淡・白・グレーを基調にし、赤は危険や被害を示す箇所だけに使います");

    L.sec(s, "色の役割", 2.0);
    L.BODY(s, "色は theme.json に役割名で定義され、スライド定義側は役割名で取り出す。名前が役割を表すため、テーマを差し替えても定義を書き換えずに済む。", 2.44, 0.55);

    const groups = [
      { head: "基調色（構造を表す）", rows: [
        ["PRIMARY", PRIMARY, "タイトル・見出し・図の主要素・表のヘッダー"],
        ["DARK", DARK, "章扉の背景、本文中の項目名の強調"],
        ["LIGHT", LIGHT, "図の背景ゾーン"],
        ["PANEL / PANEL_LINE", PANEL, "パネルの塗りと表の罫線"],
        ["TEXT / MUTED", TEXT, "本文と注釈・出典"],
      ] },
      { head: "強調色（意味を持つ）", rows: [
        ["DANGER", DANGER, "危険・攻撃・被害。1 枚の中で最小限に絞る"],
        ["DANGER_BG / DANGER_LINE", DANGER_BG, "危険を示す領域の塗りと枠線"],
        ["SAFE", SAFE, "安全・検証済み。アイコンの色にだけ使う"],
        ["WHITE", WHITE, "背景と、青地の上の文字"],
        ["RULE", RULE, "区切り線"],
      ] },
    ];
    const gw = (CW - 0.4) / 2;
    const rh = [0.34, 0.42, 0.42, 0.42, 0.42, 0.42];
    groups.forEach((g, gi) => {
      const gx = X + gi * (gw + 0.4);
      const rows = [[L.cell("役割名", L.hOpt), L.cell("色", L.hOpt), L.cell("用途", L.hOpt)]];
      g.rows.forEach(([name, , use]) => rows.push([L.cell(name, { bold: true, color: DARK, size: 10.5 }), L.cell("", { size: 10.5 }), L.cell(use, { size: 10.5 })]));
      L.T(s, g.head, gx, 3.1, gw, 0.3, { size: 12, color: DARK });
      L.TBL(s, rows, 3.45, [2.2, 0.7, gw - 2.9], rh, { x: gx });
      // 色見本は表の「色」列に重ねて描く（表を先に描き、その上に載せる）
      let y = 3.45 + rh[0];
      g.rows.forEach(([, color], i) => {
        L.BOX(s, gx + 2.2 + 0.12, y + 0.08, 0.46, rh[i + 1] - 0.16, { fill: color, lineColor: color === WHITE ? RULE : color, lw: 0.75, r: 0.04 });
        y += rh[i + 1];
      });
    });

    L.sec(s, "使い分けの原則", 6.05);
    L.BODY(s, "強調は色を増やすのではなく濃淡で表し、等しく重要な並列要素に別々の色を割り当てない。色の違いは意味の違いとして読まれるため、装飾のために色数を増やすと論点がぼやける。補足や結論の文章は色付きの枠で囲まず、太字と色で強調する。アイコンも同じ規則に従い、白や薄い青の上では主色、青地の上では白にする。", 6.45, 0.6);
  })();

  // ============================================================ 7. フロー図（構造図＋アイコン）
  (function () {
    const s = L.slide();
    L.title(s, "資料作成の流れ");
    L.keymsg(s, "雛形の用意からビルドと検証までを 1 巡とし、崩れがあればスライド定義へ戻って修正します");

    L.sec(s, "作成の手順", 2.0);
    L.BODY(s, "各段階の成果物が次の段階の入力になる。検証で崩れが見つかれば定義を修正して再ビルドし、規格違反が 0 件になるまで繰り返す。", 2.44, 0.55);

    const steps = [
      { icon: "document_white", label: "雛形の用意", text: "template を作業ディレクトリへコピーし、npm install する" },
      { icon: "code_white", label: "スライド定義", text: "deck-src に定義を書く。ヘルパーだけを使うと書式が揃う" },
      { icon: "settings_white", label: "ビルド", text: "node build.js で pptx・PDF・PNG を生成し、規格違反を検査する" },
      { icon: "eye_white", label: "目視の検証", text: "PNG を読み、はみ出し・重なり・折り返し・規範違反を列挙する" },
    ];
    const bw = 2.6, by = 3.35, bh = 1.9;
    const bx = [X + 0.3, X + 3.5, X + 6.7, X + 9.9];
    steps.forEach((st, i) => {
      L.BOX(s, bx[i], by, bw, bh, { fill: WHITE, lineColor: PRIMARY, lw: 1.75 });
      L.PILL(s, bx[i] + 0.2, by - 0.17, bw - 0.4, 0.34, `${i + 1}. ${st.label}`, { size: 11 });
      L.OVAL(s, bx[i] + bw / 2 - 0.28, by + 0.38, 0.56, 0.56, { fill: PRIMARY, line: false });
      L.ICON(s, st.icon, bx[i] + bw / 2 - 0.18, by + 0.48, 0.36);
      L.BODY(s, st.text, by + 1.05, 0.8, { x: bx[i] + 0.15, w: bw - 0.3, size: 10.5 });
      if (i < 3) L.ARROW(s, bx[i] + bw + 0.08, by + bh / 2, bx[i + 1] - 0.08, by + bh / 2);
    });
    // 検証から定義への戻り（破線）
    const yb = by + bh + 0.35;
    L.ARROW(s, bx[3] + bw / 2, by + bh, bx[3] + bw / 2, yb, { arrow: false, dash: true, color: MUTED, w: 2 });
    L.ARROW(s, bx[3] + bw / 2, yb, bx[1] + bw / 2, yb, { arrow: false, dash: true, color: MUTED, w: 2 });
    L.ARROW(s, bx[1] + bw / 2, yb, bx[1] + bw / 2, by + bh, { dash: true, color: MUTED, w: 2 });
    L.T(s, "崩れがあれば定義を修正して再ビルド", bx[2] - 0.6, yb - 0.32, 4.0, 0.3, { size: 10.5, color: MUTED, bold: false, align: "center" });

    L.sec(s, "検証の観点", 6.1);
    L.BODY(s, [
      { text: "PDF ではなく PNG を読み、文字のはみ出しと意図しない折り返し、要素の重なり、青以外の色の混入、キーメッセージの再掲、章参照の有無を確認する。" },
      { text: "崩れは体裁の問題に見えて、多くは情報量の入れ過ぎが原因である", options: { bold: true, color: DARK } },
      { text: "。文字を小さくして収めるのではなく、論点を分けるか、表現を変える。" },
    ], 6.5, 0.6);
  })();

  // ============================================================ 8. 表＋コード（2 段組み）
  (function () {
    const s = L.slide();
    L.title(s, "スライド定義の書き方");
    L.keymsg(s, "ヘルパーを呼ぶだけで所定の位置・サイズ・色が適用されるため、座標や書式を個別に指定する必要はありません");

    L.sec(s, "最小の記述例", 2.0, { w: 7.4 });
    L.BODY(s, [
      { text: "deck-src/<name>.js に次の形で書き、deck.json の parts にファイル名を追加する。ヘルパーの引数は " },
      L.LINK("pptxgenjs の座標系", "https://gitbrent.github.io/PptxGenJS/docs/usage-pres-options/", { size: 11.5 }),
      { text: "（inch）に従う。" },
    ], 2.44, 0.55, { w: 7.4 });
    L.CODE(s, [
      "module.exports = function (pres, L) {",
      "  const { PRIMARY, DARK, TEXT } = L.C;      // 色は役割名で取り出す",
      "  const s = L.slide();",
      '  L.title(s, "アーキテクチャの構成");          // 体言止め',
      '  L.keymsg(s, "3 層に分けて責務を明確にします"); // ですます調の完全な文',
      "",
      '  L.sec(s, "構成", 2.0);                        // ＜構成＞',
      '  L.BODY(s, "各層の役割は次のとおり。", 2.44, 0.4);',
      '  L.BOX(s, 0.85, 3.0, 3.0, 1.2, { fill: "FFFFFF" }); // 図の枠',
      '  L.PILL(s, 1.05, 2.84, 2.6, 0.34, "プレゼン層");    // 見出しピル',
      "  L.ARROW(s, 3.95, 3.6, 4.35, 3.6);                  // 矢頭付き矢印",
      "};",
    ], X, 3.05, 7.4, 2.45);

    L.sec(s, "主なヘルパー", 2.0, { x: X + 7.75, w: CW - 7.75 });
    L.BODY(s, "階層・本文・図・表・コードの各段に対応するヘルパーがある。", 2.44, 0.3, { x: X + 7.75, w: CW - 7.75, size: 11 });
    L.TBL(s, [
      [L.cell("ヘルパー", L.hOpt), L.cell("用途", L.hOpt)],
      [L.cell("title / keymsg / sec", { bold: true, color: DARK, size: 10.5 }), L.cell("階層の見出し。位置とサイズは固定", { size: 10.5 })],
      [L.cell("BODY / BULLETS / CAP / SRC", { bold: true, color: DARK, size: 10.5 }), L.cell("本文・箇条書き・図の説明・出典", { size: 10.5 })],
      [L.cell("BOX / PILL / ARROW / ICON", { bold: true, color: DARK, size: 10.5 }), L.cell("図の枠・見出しピル・矢印・アイコン", { size: 10.5 })],
      [L.cell("TBL / cell / hOpt", { bold: true, color: DARK, size: 10.5 }), L.cell("表（青ヘッダー・白データ行）", { size: 10.5 })],
      [L.cell("CODE", { bold: true, color: DARK, size: 10.5 }), L.cell("コードボックス。hl で行を赤く強調", { size: 10.5 })],
      [L.cell("divider / subDivider / toc", { bold: true, color: DARK, size: 10.5 }), L.cell("章扉・節扉・目次", { size: 10.5 })],
    ], 2.78, [2.15, 2.33], null, { x: X + 7.75 });

    L.sec(s, "描画順の注意", 5.95);
    L.BODY(s, [
      { text: "要素は追加した順に重なり、後に追加したものが前面に来る。" },
      { text: "背景のゾーンを表す BOX は、その中に載せる要素より先に描く", options: { bold: true, color: DARK } },
      { text: "。逆にすると、塗りが手前の文字を覆って消してしまう。図形とテキストを重ねるときも、枠を描いてからテキストを載せる。" },
    ], 6.35, 0.7);

    L.SRC(s, [{ text: "参考: " }, L.LINK("PptxGenJS のドキュメント（gitbrent.github.io/PptxGenJS）", "https://gitbrent.github.io/PptxGenJS/", { size: 10 })]);
  })();

  // ============================================================ 9. NG・OK のコード対比
  (function () {
    const s = L.slide();
    L.title(s, "矢印の描き方");
    L.keymsg(s, "矢印は始点と終点から幅と高さを計算せず、外接矩形を正の値で与えて向きは反転指定で表します");

    L.sec(s, "幅と高さの与え方", 2.0);
    L.BODY(s, [
      { text: "右から左、下から上へ引いた矢印は幅や高さが負になる。負のサイズは OOXML の規格違反で、" },
      { text: "PowerPoint はファイル全体を破損と判定して開けなくなる", options: { bold: true, color: DANGER } },
      { text: "。LibreOffice は許容して PDF を出せるため、PDF の確認だけでは気づけない。" },
    ], 2.44, 0.6);

    const colW = (CW - 0.4) / 2;
    const lx = X, rx = X + colW + 0.4, ty = 3.2;
    L.TAG(s, lx, ty, 1.3, 0.34, "NG");
    L.T(s, "幅と高さが負になる", lx + 1.45, ty, colW - 1.45, 0.34, { size: 12, color: DANGER });
    L.CODE(s, [
      "const ARROW = (s, x1, y1, x2, y2) =>",
      "  s.addShape(pres.shapes.LINE, {",
      "    x: x1, y: y1,",
      "    w: x2 - x1, h: y2 - y1,   // 右から左へ引くと負になる",
      '    line: { endArrowType: "triangle" },',
      "  });",
    ], lx, ty + 0.45, colW, 1.3, { hl: [3] });

    L.TAG(s, rx, ty, 1.3, 0.34, "OK", { fill: PRIMARY, icon: "checkmark_white" });
    L.T(s, "外接矩形は正の値、向きは反転で表す", rx + 1.45, ty, colW - 1.45, 0.34, { size: 12, color: DARK });
    L.CODE(s, [
      "const ARROW = (s, x1, y1, x2, y2) => {",
      "  const dx = x2 - x1, dy = y2 - y1;",
      "  return s.addShape(pres.shapes.LINE, {",
      "    x: Math.min(x1, x2), y: Math.min(y1, y2),",
      "    w: Math.abs(dx), h: Math.abs(dy),",
      "    ...(dx < 0 ? { flipH: true } : {}),",
      "    ...(dy < 0 ? { flipV: true } : {}),",
      '    line: { endArrowType: "triangle" },',
      "  });",
      "};",
    ], rx, ty + 0.45, colW, 2.05);

    L.sec(s, "規格違反の検査", 5.85);
    L.BODY(s, "ヘルパーを経由せず addShape を直接書くと、同じ違反が入り込む。build.js は生成のたびに normalize.py で修正と検査を行い、違反が残れば PDF を出さない。負のサイズを含んでいても開けるファイルはあるため、他のファイルで問題が無かったことを根拠に無視せず、常に 0 件にしておく。", 6.25, 0.7);
  })();
};
