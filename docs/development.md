# 開発

書式の規範、描画関数、スキルの手順を変更する場合の手順。構成は [architecture.md](architecture.md)。

## 変更をその場で検証する

プラグインとしてインストールすると、ファイルは `~/.copilot/installed-plugins/` などへコピーされる。
その状態では手元の編集が反映されないため、**clone したディレクトリを直接読み込ませる。**

```bash
git clone https://github.com/akitamoto-dev/pptx-as-code.git ~/pptx-as-code
```

GitHub Copilot CLI と Claude Code のどちらも、起動時に `--plugin-dir ~/pptx-as-code` を付けて読み込ませる。
導入済みのプラグインと同時に有効にすると二重に読み込まれるため、いずれか一方に限る。

導入したまま検証する場合は、変更を push してから `copilot plugin update pptx-as-code@pptx-as-code`（Claude Code は `claude plugin update ...`）を実行する。

## 見本を変更した場合

`skills/blue-format/samples/sample.js` を変更したら、ビルドが完了することを確認する。

```bash
cp -r template/. /tmp/check/
node skills/blue-format/apply.js /tmp/check
cp skills/blue-format/samples/sample.js /tmp/check/deck-src/
cd /tmp/check && npm install && node build.js --name sample
```

`deck.json` の `parts` を `["sample"]` にしてから実行する。規格違反 0 件で PDF と PNG が出力されれば正常。

## 画像生成 MCP を変更した場合

MCP 本体（`mcp-server/`）はプラグインに同梱され、`mcp.json` の起動処理がクライアントから受け取った導入先をもとにその場所を探す。
**ルートの `plugin.json` に `$schema` を書かない。起動処理に `${` を書かない。** どちらも MCP が起動しなくなる。理由は [architecture.md](architecture.md#画像生成-mcp)。
**スキルと同様に、commit して push すれば配布される。** タグの作成は不要。

依存を変更した場合（`pyproject.toml`）は `uv lock` で `uv.lock` を更新してから commit する。利用者側では `uv run` が lock を参照して自動的に再導入する。

## バージョン

`plugin.json` と `.claude-plugin/plugin.json` の `version` に同じ値を書く。クライアントごとに読むファイルが異なるため、2 か所に必要になる（`copilot plugin list` と `claude plugin details` がそれぞれ表示する）。

**上げるのは、利用者に伝えたい変更があるときだけ。** 動作には関与せず、表示にのみ使われるため、内部的な修正では上げなくてよい。

利用者側の取り込み手順は [README.md の「更新」](../README.md)。カタログを更新してからプラグインを更新し、クライアントの再起動を依頼する。

## 書かないもの

配布するファイルには、次を残さない。

- 日付を伴う決定の経緯（「◯月◯日に変更」など）。規範は理由とともに記載し、決定の時期は記載しない
- 個人名、案件名、社内の固有名詞、実在の資料名
- 特定の利用者の環境に依存する値（絶対パス、テナント ID、エンドポイント）

規範には理由を添える。根拠が記載されていれば、判断が必要な場面でエージェントが応用できる。
