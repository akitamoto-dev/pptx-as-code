# pptx-as-code

コーディングエージェントで PowerPoint 資料を作成するためのプラグイン。GitHub Copilot と Claude Code に対応する。

内容を渡すとスライドをコードで組み立て、PowerPoint ファイルと PDF を出力する。中身は画像ではなくテキスト・図形・表で構成されるため、PowerPoint でそのまま編集できる。作成・確認・修正は VS Code 上で完結する。

## 含まれるもの

| 種類 | 名前 | 役割 | 使用する場面 |
|---|---|---|---|
| Skill | `content-to-pptx` | 内容からスライドをコードで直接組み立てる | 表・箇条書き・文章が中心の資料 |
| Skill | `image-to-pptx` | スライドを画像で設計し、編集できる pptx へ再構成する | 図が中心の資料、レイアウトの自由度が必要な場合 |
| Skill | `ms-format` | 青基調の所定フォーマットと、文章・構成の規範を与える | **その書式で作成する場合のみ。** 別の書式やブランドでは使用しない |
| Skill | `pptx-lint` | 出力を 1 ページずつ検査し、崩れと規範違反をページ番号付きで返す | 作成の完了時と、構成を変更した場合 |
| Skill | `env-setup` | 実行に必要なものを点検して導入する | 初回と、動作しなくなった場合 |
| MCP | `slide-image-gen` | スライドの案を画像で生成する | `image-to-pptx` が呼び出す。単独でも使用できる |

すべて 1 つのプラグインに含まれる。導入も更新も 1 回で完了する。
画像生成 MCP には Azure サブスクリプションが必要だが、未設定でもスキルは動作する（画像を経由する方法のみ使用できない）。
構成の詳細は [docs/architecture.md](docs/architecture.md)。

## 作成方法

2 通りある。**出力形式は同じで、成果はどちらも作業フォルダの定義ファイル（コード）に残る。**
書式を指定する場合は、どちらにも `ms-format` を併用する。

### 内容から直接作成する

Markdown・テキスト・会話での指示を、そのままスライドの定義に変換する。表・箇条書き・文章が中心の資料に適する。このスキルは画像を扱わず、画像生成も呼び出さない。

### 画像を経由して作成する

**画像生成モデルの表現力を、資料の品質に反映させるための方法。**

コードだけで図を組み立てると、既存の型の組み合わせに限られる。画像生成モデルは、伝えたい内容に応じてレイアウト・図の構造・要素の配置を設計できる。そこで**完成形に近いスライドを先に画像で生成し**、それを設計図として PowerPoint のテキスト・図形・表へ再構成する。自由度の高いレイアウトを、編集できる形で得られる。

起点は 3 通り。

| 入力 | 処理 |
|---|---|
| 内容のみ（テキスト・Markdown・会話での指示） | その要件に沿ったスライドの案を画像で生成し、変換する |
| 内容と参考画像（「このフォーマットで作成」） | 参考画像の書式を踏まえた案を生成し、変換する |
| 変換対象の画像（「この画像を pptx に変換」） | 生成を経由せず、その画像を変換する |

上 2 つがスライドの作成、3 つ目は既存の資料を編集できる形へ変換する作業にあたる。
ページ数は問わない。複数ページの場合は、ページごとに案を生成して変換する。

**生成した画像はスライドに配置しない。** 配置すると文字を編集できず、画像内の文字は精度も低い。ネイティブのテキスト・図形・表として再構成する。
pptx を伴わず画像のみが必要な場合は、チャットで「slide-image-gen で〇〇のスライド画像を作成」と指示する。構図を先に確認する場合に適する。

## 作成後の修正

**修正の規模に応じて、やり直す範囲が変わる。** 文言の修正のたびに画像を再生成したり、全ページを検査したりはしない。

| 修正の内容 | 画像生成 | `pptx-lint` |
|---|---|---|
| 文言、数値、色、強調、要素の位置、表や本文の追記 | 再実行しない | 呼び出さない（該当ページのみ確認） |
| スライドの追加・削除・並べ替え、見出し構成の変更 | 再実行しない | 呼び出す |
| 図のメタファーや構図そのものの変更 | 再実行する | 呼び出す |

判断に迷う場合は、定義ファイルの修正から着手する。図の説得力が不足する場合にのみ画像生成へ戻す。

## 導入

ツール本体の導入手順は [GitHub Copilot CLI のインストール](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) と [Claude Code のセットアップ](https://code.claude.com/docs/en/setup) を参照。

### 1. プラグインを導入する

GitHub Copilot で使用する場合。GitHub Copilot CLI で導入すると、VS Code の GitHub Copilot Chat でも使用できる。

```bash
copilot plugin marketplace add akitamoto-dev/pptx-as-code
copilot plugin install pptx-as-code@pptx-as-code
```

Claude Code で使用する場合。

```bash
claude plugin marketplace add akitamoto-dev/pptx-as-code
claude plugin install pptx-as-code@pptx-as-code
```

両方で使用する場合は、両方を実行する。導入したスキルはすべてのプロジェクトで有効になる。

### 2. 環境を構築する

エージェントを起動する。

GitHub Copilot で使用する場合。

```bash
copilot
```

Claude Code で使用する場合。

```bash
claude
```

環境構築のスキルを実行する。

```
/pptx-as-code:env-setup
```

必要なものの導入、見本のビルド、画像生成 MCP の設定までを実施する。**コマンドの手動実行や環境変数の設定は不要。** 導入の前に承諾を求め、導入できなかったものがあればその内容を報告する。

対応 OS は Linux、WSL、macOS。Windows ネイティブは LibreOffice の導入で動作する見込みだが、実機での検証は未実施。

**画像生成 MCP には Azure サブスクリプションが必要。** 図の自由度と仕上がりに影響するため、可能であれば設定する。使用できない環境でも、図形とアイコンで図を直接作成すれば資料は作成できる。

**課金について。** 作成する Foundry アカウントと GPT-Image-2 のデプロイ（Global Standard）は従量課金で、作成時点では費用が発生しない。生成した画像の枚数に応じて課金される。単価は [Microsoft Foundry の価格](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)（モデルごとの単価と課金単位が分かる）を参照。使用しなくなった場合はリソースグループを削除する。

### 3. 動作確認

1 ページの資料を作成して確認する。

内容から直接作成する方法。

```
/pptx-as-code:ms-format /pptx-as-code:content-to-pptx LLM とは を説明する 1 ページの資料を作成してください。
```

画像を経由して作成する方法（画像生成 MCP の設定が必要）。

```
/pptx-as-code:ms-format /pptx-as-code:image-to-pptx AIエージェント とは を説明する 1 ページの資料を作成してください。
```

出力された pptx を PowerPoint で開き、崩れがなければ完了。

**MCP のツールはスラッシュコマンドの候補に表示されない。** ツールはエージェントが呼び出すもので、利用者が `/` から起動する対象ではないため。質問文にも記載せず、`image-to-pptx` を呼び出せばその中で使用される。
画像生成のみを直接呼び出す場合は、チャットで「slide-image-gen で画像を作成」と指示する。Claude Code ではスラッシュコマンド `/mcp__slide-image-gen__generate` も使用できる。
MCP の認識状況は、セッション内で `/mcp` を実行すると確認できる（Claude Code では起動前に `claude mcp list` でも確認できる）。

## 更新

開発側の修正を、**カタログ（marketplace）とプラグインの順に**取り込む。カタログは提供中のバージョンの索引で、プラグイン本体とは別に管理されるため、先に更新する。

GitHub Copilot。

```bash
copilot plugin marketplace update pptx-as-code
copilot plugin update --all
```

Claude Code。プラグインごとに指定する。

```bash
claude plugin marketplace update pptx-as-code
claude plugin update pptx-as-code@pptx-as-code
```

**更新後はクライアントを再起動する。** プラグインと MCP の定義は起動時にのみ読み込まれる。
VS Code の GitHub Copilot Chat では「Developer: Reload Window」を実行し、画像生成 MCP を更新した場合はツール選択で `slide-image-gen` の「更新ツール」を押す。

導入先のファイルは一式が差し替わるため、スキル・書式・見本・画像生成 MCP の本体は、この手順で反映される。
**作成済みの作業フォルダは更新されない。** 雛形（`template/`）を複製したもので、作成中の資料がプラグインの更新で破損しないよう、独立して扱う設計による。雛形の修正を既存の作業フォルダへ反映する場合は、複製し直す。

### `env-setup` の再実行

**通常は不要。** スキルの手順や書式の変更は、上記の更新と再起動で反映される。次の場合のみ実行する。

- 必要な道具が増えた、または変更された場合（更新の案内に記載される）
- 画像生成 MCP の接続先を変更する場合（リージョンの追加、別のサブスクリプションへの移行）
- 動作しなくなった場合

**何度実行しても安全。** 点検のうえ不足分のみを導入し、Foundry も既存のリソースは再作成しない。

## 参考

| 参照先 | 内容 |
|---|---|
| [docs/architecture.md](docs/architecture.md) | 構成、技術スタック、ディレクトリ |
| [mcp-server/README.md](mcp-server/README.md) | 画像生成 MCP の設定と運用 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | プラグイン自体の改修 |
