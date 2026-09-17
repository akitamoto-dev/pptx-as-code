# 構成と技術スタック

導入と使い方、スキルと MCP の一覧は [README.md](../README.md)。ここには、何で出来ているかを書く。

## 技術スタック

`env-setup` がすべて導入する。利用者が手動で導入するものはない。

| 区分 | 使用するもの | 用途 |
|---|---|---|
| PowerPoint の生成 | Node.js、pptxgenjs | スライドをコードで組み立てる。python-pptx ではなく JavaScript の pptxgenjs を採用している |
| 規格の検査 | Python 3 | 生成したファイルを開き、PowerPoint が破損と判定する箇所を修正・検出する。標準ライブラリだけで動く |
| PDF と画像への変換 | LibreOffice、poppler（pdftoppm）または PyMuPDF、日本語フォント（Noto Sans CJK） | PowerPoint ファイルを PDF に変換し、各ページを PNG にする |
| 画像から PowerPoint への変換 | uv、Pillow、PyMuPDF、python-pptx | 座標の読み取り、切り出し、レンダリング比較、編集可能性の検証。uv が実行時に依存を解決する |
| アイコン | Fluent UI System Icons | Iconify から取得し、PNG として配置する。使用頻度の高いものは同梱している |

pptxgenjs が出力する pptx には、PowerPoint が破損と判定する規格違反が混じることがある。LibreOffice も python-pptx もこれを通過させるため、PDF が出せたことは開ける根拠にならない。
`template/build.js` は生成のたびに `tools/normalize.py` を通し、違反が残れば PDF を出さない。詳しくは [references/pptxgenjs.md](../references/pptxgenjs.md)。

## ディレクトリ

プラグインは 1 つで、スキルと MCP の両方が入っている。

```
pptx-as-code/
├── plugin.json                 プラグインの定義（Copilot CLI と VS Code が読む）
├── .claude-plugin/             Claude Code 用の定義と、導入元の一覧
├── mcp.json                    画像生成 MCP の起動定義。ルートに置くと読み込まれる
├── skills/                     スキル本体。それぞれ専用の資材だけを持つ
│   ├── content-to-pptx/        内容から組み立てる手順
│   ├── image-to-pptx/          画像の生成・変換手順と、座標把握・切り出し・比較のスクリプト
│   ├── blue-format/            書式の定義、文章と構成のルール、アイコン、型の見本
│   ├── pptx-lint/              検査の観点と、指摘の返し方
│   └── env-setup/              環境の点検スクリプトと、OS 別の導入手順
├── template/                   作業フォルダの雛形。描画用の関数、ビルド、規格の検査、既定の書式
├── references/                 スキルが読む技術資料（pptxgenjs の技法と、PowerPoint で開けなくなる条件）
├── mcp-server/                 画像生成 MCP の本体（Python）。mcp.json がこの場所を指して起動する
├── infra/                      画像生成 MCP が使用する Microsoft Foundry と画像生成モデルを
│                               Azure にデプロイするスクリプトと Bicep
├── devcontainer/               Dev コンテナ（サンドボックス環境）の定義。利用者のプロジェクトへ複製する
├── docs/                       人が読む説明（この文書、書式と規範、開発の手順）
├── LICENSE                     本体のライセンス（MIT）
└── THIRD-PARTY-NOTICES.md      同梱物の権利表示
```

### なぜ `template/` と `references/` が `skills/` の外にあるか

**複数のスキルが使用する資産であるため。** スキルの下に配置すると、所有関係が実態と食い違う。

| | 使用するスキル | 配置の理由 |
|---|---|---|
| `template/` | `content-to-pptx`、`image-to-pptx`、`pptx-lint` | 3 つが使用し、さらに**作業フォルダへコピーする配布物**でもある。スキルの一部ではない |
| `references/pptxgenjs.md` | `content-to-pptx`、`image-to-pptx` | 片方の下に配置すると、もう一方が `../content-to-pptx/references/…` と辿ることになる |
| `skills/*/scripts/` など | そのスキルのみ | 専用であるため下に配置する |

`template/` は資料を作成するたびに作業フォルダへ複製し、複製先で編集する。
**プラグインを更新しても、作成中の資料には影響しない。** 逆に、`template/` の修正を既存の作業フォルダへ反映したいときは、コピーし直す。

## 画像生成 MCP

| 区分 | 内容 |
|---|---|
| 画像生成 | Microsoft Foundry の GPT-Image-2。16:9 の PNG を 1 枚ずつ生成する。品質は既定で `high`（画像内の日本語が崩れにくい） |
| MCP サーバー | FastMCP（Python）で実装。openai と azure-identity で Foundry を呼び出す |
| 起動 | `mcp.json` が `${CLAUDE_PLUGIN_ROOT}/mcp-server` を指し、`uv run` が依存を解決して起動する。リポジトリから取り直さないので、起動にネットワークが要らず、バージョンはプラグインと一体になる |
| 公開しているもの | ツール `generate_slide_image`（モデルが呼ぶ）と、プロンプト `generate`（人がスラッシュコマンドから呼ぶ）の 2 つ |
| 認証 | Entra ID（`DefaultAzureCredential`）。API キーは持たない |
| 耐障害性 | 複数リージョンに展開し、呼び出しごとに分散する。制限に達したリージョンは一定時間避けて別のリージョンで再試行する |
| 接続先 | env ファイル（`~/.config/slide-image-gen/env`）に置く。`infra/deploy.py` が書き込み、MCP が起動時に読む。起動定義には書かない |
| インフラ | 1 リージョン分の Bicep と、それをリージョンごとに実行するデプロイスクリプト（Python） |

設定と環境変数の詳細は [mcp-server/README.md](../mcp-server/README.md)。
