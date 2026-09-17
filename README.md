# pptx-as-code

コーディングエージェントで PowerPoint 資料を作成するためのプラグイン。GitHub Copilot と Claude Code に対応する。

Markdown やテキスト、スライドの画像を渡すと、スライドをコードで組み立て、PowerPoint ファイルと PDF を出力する。作成、確認、修正は VS Code の中で行う。

## 含まれるハーネス

| カテゴリ | 名前 | 役割 | 構成要素 |
|---|---|---|---|
| Skills | `content-to-pptx` | Markdown やテキストから、スライドをコードで組み立てる | 内容を構造化してスライドに落とす手順 |
| Skills | `image-to-pptx` | スライドの画像を、編集できる PowerPoint ファイルに変換する。変換元の画像が無い場合は `slide-image-gen`（MCP）を呼んで生成してから変換する | 画像から座標を読む手順、切り出し・比較・検証のスクリプト |
| Skills | `pptx-lint` | 出来上がりを 1 ページずつ検査し、崩れとルール違反を指摘する | 検査の観点、ページ番号付きで返す形式 |
| Skills | `ms-format` | 青基調の決まった書式と、文章・構成のルールを与える | 書式の定義、文章と構成のルール、アイコン、型の見本 |
| Skills | `env-setup` | 実行に必要なものを点検して導入する | 点検スクリプト、OS 別の導入コマンド |
| MCP | `slide-image-gen` | 画像形式のスライドを 1 枚生成する。`image-to-pptx` から呼ばれるほか、単独でも使用できる | Microsoft Foundry での画像生成。別のプラグインとして追加する（Azure サブスクリプションが必要） |

## 作成方法

**入力がテキストだけなら 1、画像を使うなら 2 を選ぶ。**
図が中心のスライドは、画像を 1 枚作ってから変換する 2 の方法が向いている。
`ms-format` は Microsoft フォーマットで作成する場合に使用する。別の書式で作成する場合は省く。

### 1. 内容から直接作成する方法

Markdown やテキスト、会話での指示を構造化し、スライドをコードで定義する。

| 順 | スキル | 処理 |
|---|---|---|
| 1 | `ms-format` | 青基調の書式と、文章・構成のルールを読み込む（Microsoft フォーマットで作成する場合） |
| 2 | **`content-to-pptx`** | 渡された内容を 1 スライド 1 論点に構造化し、定義を書く。<br>PowerPoint ファイル・PDF・確認用の画像を出力する |
| 3 | `pptx-lint` | 出力を 1 ページずつ検査し、崩れとルール違反をページ番号付きで返す |

### 2. 画像を経由して作成する方法

画像形式のスライドを分解し、編集できる PowerPoint ファイルに変換する。変換元の画像は、渡されたものを使うか、その場で生成する。

| 順 | スキル | 処理 |
|---|---|---|
| 1 | `ms-format` | 書式と作風を読み込む。画像を生成するときの指示も、この書式から組み立てる（Microsoft フォーマットで作成する場合） |
| 2 | **`image-to-pptx`** | まず変換元の画像を決める。<br>・画像が渡されていれば、その画像を変換元にする（他社の資料、過去の PDF、受け取ったスクリーンショットなど）<br>・渡されていなければ、画像生成 MCP（`slide-image-gen`）を呼び、生成された画像を変換元にする<br>次に、その画像から座標を読み取り、文字・図形・矢印・表・アイコンに分解して定義を書く。<br>PowerPoint ファイル・PDF・確認用の画像を出力し、元画像とレンダリング結果を比較して補正する |
| 3 | `pptx-lint` | 出力を 1 ページずつ検査し、崩れとルール違反をページ番号付きで返す |

**生成した画像はスライドに配置せず、図形とアイコンで再構成する。**
`slide-image-gen` を単独で呼び、画像を先に確認してから変換に進むこともできる。

### （補足）作成後の修正

作成の流れとは別に、作成済みの資料を修正する場合の戻り先を示す。
どちらの方法でも成果は同じ定義ファイルに残るため、修正内容によって戻る場所が変わる。

| 修正内容 | 戻り先 | 使用するスキル |
|---|---|---|
| 文言、配置、色、表の内容 | 定義ファイルを修正し、作業フォルダでビルドし直す | **なし**（雛形のビルドスクリプトを実行するだけ） |
| 図の構成そのもの | 画像を作り直し、変換からやり直す | `slide-image-gen`（MCP） → `image-to-pptx` |

書式と作業フォルダはそのまま使用でき、修正後は `pptx-lint` で再検査する。

## 構成

```
pptx-as-code/
├── plugin.json                 プラグインの定義（Copilot CLI と VS Code が読む）
├── .claude-plugin/             Claude Code 用の定義と、導入元の一覧
├── template/                   作業フォルダの雛形。描画用の関数、ビルド、規格の検査、既定の書式
├── references/                 pptxgenjs の技法と、PowerPoint で開けなくなる条件
├── devcontainer/               コンテナで使う場合の定義。利用者のプロジェクトにコピーする
├── skills/
│   ├── content-to-pptx/        内容から作成する手順
│   ├── image-to-pptx/          変換手順と、座標把握・切り出し・比較のスクリプト
│   ├── ms-format/              書式の定義、文章と構成のルール、アイコン、型の見本
│   ├── pptx-lint/              検査の観点と、指摘の返し方
│   └── env-setup/              環境の点検スクリプトと、OS 別の導入手順
├── plugins/slide-image-gen/    画像生成 MCP。起動定義と本体（Python）。独立したプラグインとして追加する
└── infra/                      画像生成 MCP が使う Microsoft Foundry と画像生成モデルを
                                Azure にデプロイするスクリプトと Bicep
```

`template/` は特定のスキルに属さない**共通の資産**で、`content-to-pptx`、`image-to-pptx`、`pptx-lint` の 3 つが使用する。
資料を作成するたびに作業フォルダへコピーし、コピー先で編集する。プラグインを更新しても、作成中の資料には影響しない。

## セットアップ方法

### 1. プラグインのインストール

GitHub Copilot と Claude Code で使用できる。ツール本体の導入手順は [GitHub Copilot CLI のインストール](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) と [Claude Code のセットアップ](https://code.claude.com/docs/en/setup) を参照。
どちらか一方で使用する場合は、そのツールの手順を 1 回だけ実行する。両方で使用する場合は、両方の手順を実行する。
インストールしたスキルは、すべてのプロジェクトで有効になる。

#### GitHub Copilot で使用する場合

インストールには GitHub Copilot CLI を使う。インストールしたプラグインは、GitHub Copilot CLI と VS Code の GitHub Copilot Chat で使用できる。

```bash
copilot plugin marketplace add akitamoto-dev/pptx-as-code
copilot plugin install pptx-as-code@pptx-as-code
```

#### Claude Code で使用する場合

```bash
claude plugin marketplace add akitamoto-dev/pptx-as-code
claude plugin install pptx-as-code@pptx-as-code
```

更新は、GitHub Copilot CLI では `copilot plugin update pptx-as-code@pptx-as-code`、Claude Code では `claude plugin update pptx-as-code@pptx-as-code` を実行する。

### 2. 環境のセットアップ（`env-setup` スキルが実行）

エージェントを起動する。

```bash
copilot
```

```bash
claude
```

起動したら、環境構築のスキルを実行する。

```
/pptx-as-code:env-setup
```

`env-setup` が以下の 2.1〜2.3 を順に行う。手動でコマンドを実行する必要はない。導入の前に承諾を求め、導入できなかったものがあればその内容を報告する。動作しなくなったときも、同じスキルを実行する。

対応 OS は Linux、WSL、macOS。Windows ネイティブは LibreOffice の導入で動作する見込みだが、実機での検証は未実施。

#### 2.1 実行環境の導入

技術スタックは次のとおり。すべて導入する。

| 区分 | 導入するもの | 用途 |
|---|---|---|
| PowerPoint の生成 | Node.js、pptxgenjs | スライドをコードで組み立て、PowerPoint ファイルを出力する。python-pptx ではなく JavaScript の pptxgenjs を採用している |
| 規格の検査 | Python 3 | 生成したファイルを開き、PowerPoint が破損と判定する箇所を修正・検出する。標準ライブラリだけで動作する |
| PDF と画像への変換 | LibreOffice、poppler（pdftoppm）または PyMuPDF、日本語フォント（Noto Sans CJK） | PowerPoint ファイルを PDF に変換し、各ページを PNG にする |
| 画像から PowerPoint への変換 | uv、Pillow、PyMuPDF、python-pptx | 座標の読み取り、切り出し、レンダリング比較、編集可能性の検証。uv が実行時に依存を解決する |
| アイコン | Fluent UI System Icons | Iconify から取得し、PNG として配置する。取得済みのものはプラグインに同梱している |

#### 2.2 見本のビルド

見本のスライドをビルドし、PDF と画像が出力されることを確認する。

#### 2.3 画像生成 MCP のセットアップ

Microsoft Foundry に画像生成モデルをデプロイし、MCP を接続する。Azure サブスクリプションが必要。
図の自由度と仕上がりに影響するため、可能であれば設定する。

**課金について。** 作成する Foundry アカウントと GPT-Image-2 のデプロイ（Global Standard）は従量課金で、作った時点では費用が発生しない。生成した画像の枚数に応じて課金される。単価は [Microsoft Foundry の価格](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)（モデルごとの単価と課金単位が分かる）を参照。使わなくなったらリソースグループを削除する。

| 区分 | 内容 |
|---|---|
| 画像生成 | Microsoft Foundry の GPT-Image-2。16:9 の PNG を 1 枚ずつ生成する |
| MCP サーバー | FastMCP（Python）で実装。openai と azure-identity で Foundry を呼び出す |
| 耐障害性 | 複数リージョンに展開し、呼び出しごとに分散する。制限に達したリージョンは一定時間避けて別のリージョンで再試行する |
| インフラ | 1 リージョン分の Bicep と、それをリージョンごとに実行するデプロイスクリプト（Python） |

| 手順 | 内容 |
|---|---|
| 1 | デプロイスクリプトで Microsoft Foundry をデプロイする。GPT-Image-2 に対応するリージョンを 1 つずつ調べ、作成できないリージョンはスキップし、残りのリージョンで続行する |
| 2 | 作成できたリージョンの接続先を、スクリプトが env ファイルに書き込む。MCP の設定ファイルには書かない |
| 3 | 画像生成 MCP のプラグインをインストールする |

| 使用するツール | 手順 3 のコマンド |
|---|---|
| GitHub Copilot | `copilot plugin install slide-image-gen@pptx-as-code` |
| Claude Code | `claude plugin install slide-image-gen@pptx-as-code` |

導入したら、**クライアントを再起動する**。MCP の定義は起動時にしか読まれない。VS Code の Copilot Chat では「Developer: Reload Window」を実行し、ツール選択で `slide-image-gen` の「更新ツール」を押す。

手順の詳細と環境変数は [画像生成 MCP の説明](plugins/slide-image-gen/README.md) にある。

Azure を使用できない環境ではこの手順を省く。画像生成を経由せず、図形とアイコンで図を直接作成する。

## 動作確認

セットアップが済んだら、1 ページの資料を作って確かめる。

内容から直接作成する方法。

```
/pptx-as-code:ms-format /pptx-as-code:content-to-pptx LLM とは を説明する 1 ページの資料を作成してください。
```

画像を経由して作成する方法（画像生成 MCP の設定が要る）。

```
/pptx-as-code:ms-format /pptx-as-code:image-to-pptx AIエージェント とは を説明する 1 ページの資料を作成してください。
```

変換元の画像を渡していないので、`image-to-pptx` が `slide-image-gen` を呼んで 1 枚生成し、それを変換する。MCP はスラッシュコマンドではないため、質問文には書かない。

どちらも仕上げに `pptx-lint` が全ページを検査する。出力された pptx を PowerPoint で開いて崩れが無ければ完了。

## プラグイン自体の改修

書式のルールや描画関数を修正する場合は、プラグインとしてインストールせず、clone したディレクトリを直接読み込ませる。

```bash
git clone https://github.com/akitamoto-dev/pptx-as-code.git ~/pptx-as-code
```

GitHub Copilot CLI と Claude Code のどちらも、起動時に `--plugin-dir ~/pptx-as-code` を付けて読み込ませる。
インストール済みのプラグインと同時に有効にすると二重に読み込まれるため、どちらか一方にする。
更新は `git pull`、改善は Pull Request で行う。
