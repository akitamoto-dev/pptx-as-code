# template

このディレクトリを作業ディレクトリへコピーして使う。コピーした先のファイルは自由に編集してよい（スキルの更新で上書きされない）。

```bash
cp -r <プラグイン>/template/. ~/work/my-deck/
cd ~/work/my-deck && npm install
node build.js            # 同梱の例をビルドして preview/ に PNG が出れば環境は整っている
```

## 構成

| ファイル | 役割 |
|---|---|
| `build.js` | ビルドの入口。pptx 生成 → 規格の正規化と検査 → PDF → PNG。`--no-pdf` `--no-png` `--pages 3-5` `--name <名前>` `--parts a,b` |
| `tools/normalize.py` | PowerPoint で開けなくなる規格違反を直す（標準ライブラリだけ） |
| `tools/render.py` | PDF をページごとに PNG にする（PyMuPDF、無ければ pdftoppm） |
| `tools/fetch_icons.py` | `assets/icons/icons.json` に足りないアイコンを Iconify から取得する（`uv run tools/fetch_icons.py`） |
| `deck.json` | 出力名と、読み込むパーツの順序 |
| `deck-src/theme.json` | 書式の値（色・フォント・サイズ・座標）。書式を変えるときはここ |
| `deck-src/lib.js` | 描画ヘルパー。theme.json を読む。足りない表現はここに足す |
| `deck-src/example.js` | 同梱の例（1 枚）。書式スキルを適用すると見本が増える |
| `assets/icons/` | アイコン（PNG）と一覧 `icons.json`。書式スキルが配置する |

出力は `<name>.pptx`、`<name>.pdf`、`preview/<name>-001.png` …。

## 新しい資料を作る

1. `deck-src/<name>.js` を作る（既存の見本から最も近い型を複製すると早い）
2. `deck.json` の `parts` を `["<name>"]` にする（複数ならビルド順に並べる）
3. `node build.js` を実行し、`preview/` の PNG を確認する

定義の形:

```javascript
module.exports = function (pres, L) {
  const { PRIMARY, DARK, TEXT, MUTED, DANGER } = L.C;

  const s = L.slide();
  L.title(s, "アーキテクチャの構成");            // 名詞の体言止め
  L.keymsg(s, "3 層に分けて責務を明確にします");    // 主語と述語のある完全な文
  L.sec(s, "構成", 2.0);                           // ＜構成＞
  L.BODY(s, "各層の役割は次のとおり。", 2.44, 0.4); // である調
};
```

## ヘルパー

座標と大きさの単位は inch。`s` はスライド、`o` は省略できるオプション。

| ヘルパー | 用途 |
|---|---|
| `L.slide()` | 白背景のスライドを追加する |
| `L.title(s, text, ja)` | タイトル。幅に収まらなければ自動で縮小。`ja` を渡すと訳を括弧書きで添える。PDF のしおり名になる |
| `L.keymsg(s, text, h)` | キーメッセージ。`text` は文字列か run の配列 |
| `L.sec(s, text, y, {x, w, size})` | ＜見出し＞。`x` / `w` で段組み |
| `L.BODY(s, text, y, h, {x, w, size, color, lsm, align, bold})` | 本文。`text` は文字列か run の配列 |
| `L.BULLETS(s, items, y, h, {x, w, size, hl})` | 箇条書き。各文字列の【】の範囲を濃い青の太字にする |
| `L.CAP(s, text, y, h, {x, w})` | 図の上に置く短い説明（灰） |
| `L.SRC(s, runs)` | 出典行（最下部固定）。`runs` に `L.LINK` を混ぜる |
| `L.LINK(text, url, {size, color, bold})` | ハイパーリンクの run。本文や出典に使う |
| `L.RUNS(s, runs, x, y, w, h, {size, color, lsm, align})` | 部分着色などの複数 run テキスト |
| `L.T(s, text, x, y, w, h, {size, color, bold, align, valign})` | 図中のラベル（既定は太字） |
| `L.BOX(s, x, y, w, h, {fill, lineColor, lw, r, dash, line: false, alpha})` | 角丸の枠 |
| `L.OVAL(s, x, y, w, h, {fill, lineColor, lw, line: false})` | 楕円 |
| `L.PILL(s, x, y, w, h, text, {fill, color, size})` | 見出しピル（青地に白） |
| `L.ARROW(s, x1, y1, x2, y2, {color, w, dash, both, arrow: false})` | 矢頭付きの矢印。負のサイズを出さない |
| `L.VLINE(s, x, y, h, {color, w, dash})` / `L.HLINE(s, x, y, w, {...})` | 区切り線 |
| `L.TAG(s, x, y, w, h, text, {fill, icon, size})` | タグ。既定は赤地に白文字と警告アイコン |
| `L.ICON(s, name, x, y, size)` | `assets/icons/<name>.png` を正方形で置く |
| `L.IMG(s, path, x, y, w, h)` | 画像。パスは作業ディレクトリからの相対 |
| `L.TBL(s, rows, y, colW, rowH, {x})` | 表。`rows` は `L.cell` の 2 次元配列、`colW` は列幅の配列、`rowH` は省略すると見積もる |
| `L.cell(text, {bold, color, fill, align, size, margin})` | セル。ヘッダーは `L.cell("見出し", L.hOpt)` |
| `L.rowH(rows, colW)` | 行の高さを文字幅から見積もる |
| `L.CODE(s, code, x, y, w, h, {hl, size, lsm})` | コードボックス。`code` は文字列か行の配列。`hl` は赤くする行番号（0 始まり） |
| `L.divider(label, title, subtitle)` | 章扉（濃い青の全面背景）。スライドを返す |
| `L.subDivider(label, title, subtitle)` | 節扉（白背景、左に青の帯）。スライドを返す |
| `L.toc(s, items, {y})` | 目次。`items` は `[{ no, title, note }]` |
| `L.widthIn(text, pt)` | 文字列の幅（inch）の概算 |

色は `L.C` の役割名で取り出す: `PRIMARY` `DARK` `LIGHT` `PANEL` `PANEL_LINE` `RULE` `TEXT` `MUTED` `WHITE` `DANGER` `DANGER_BG` `DANGER_LINE` `SAFE`、コード用の `CODE_BG` ほか。フォント名は `L.C.FONT` と `L.C.MONO`。
テーマの値は `L.theme`、本文の左端と幅は `L.X` と `L.CW` で参照できる。

## 座標の目安

`deck-src/theme.json` の `title` `keyMessage` `section` `source` が位置を持つ。最初の＜見出し＞は `section.y`、本文はその約 0.44 inch 下から始め、下端は `layout.contentBottom` まで。左端は `layout.left`、幅は `layout.contentWidth`。

## 注意

- 要素は描いた順に重なる。背景のゾーンは中に載せる要素より先に描く
- 矢印は `ARROW` を使う。▶ などの文字を矢印代わりにしない
- 出典行は全角約 95 字が 1 行の上限。半角は 0.6 掛け程度で換算する
- LibreOffice を直接呼ばない。`build.js` がプロファイルを分離して呼ぶ
- 確認は `preview/` の PNG で行う。PDF を読まない
