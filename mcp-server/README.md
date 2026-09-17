# slide-image-gen（スライド用の画像生成 MCP）

Microsoft Foundry の画像生成モデル（GPT-Image-2）で 16:9 の PNG を 1 枚生成し、指定された場所に保存する MCP サーバー。
ツールは `generate_slide_image` の 1 つだけ。エージェントに「〇〇のスライドを画像で作成」と指示すると呼び出される。

- 複数リージョンの Foundry を束ね、レート制限（429）が起きたリージョンを避けて別リージョンへ自動フェイルオーバーする。連続生成でも失敗しにくい
- 認証は Entra ID（`DefaultAzureCredential`）だけ。`az login` 済みなら API キーは不要
- 参考画像を渡すとそのスタイルを踏襲する（`images.edit` API）
- 接続先は MCP サーバー自身が env ファイルから読む。起動定義に利用者固有の値を書かないので、起動定義は全員同じ 1 行になる

スライドの構成を、コードで組む前に画像で設計するための MCP。図の自由度と仕上がりに影響する。Azure を使用できない環境では、これを導入しなくても資料は作成できる（図の構成を会話で決定し、図形とアイコンで直接作成する）。
生成画像は資料に貼らず、pptxgenjs のネイティブ要素で描き直す前提（文字の精度と編集可能性のため）。
利用には Azure サブスクリプションが必要。

## 1. 前提

- [uv](https://docs.astral.sh/uv/)。MCP 本体はプラグインに同梱されており、`uv run` が依存を解決して起動する
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)。`az login` で事前にサインインする。MCP はそのトークンを使用する
- Python 3.10 以上。Foundry をデプロイする `infra/deploy.py` が使用する（標準ライブラリのみで動作する）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
az login
```

## 2. Foundry のデプロイ

リポジトリの `infra/deploy.py` が、GPT-Image-2 に対応するリージョンを 1 つずつ調べてデプロイする。この手順のときだけリポジトリを clone する。

```bash
git clone https://github.com/akitamoto-dev/pptx-as-code.git
cd pptx-as-code

python3 infra/deploy.py --check   # 調べた結果だけを表示する。Azure にも env ファイルにも書き込まない
python3 infra/deploy.py           # デプロイし、使えるリージョンの接続先を env ファイルに書き込む
```

Windows では `python3` の代わりに `py` を使用する。

作成するリソースは次のとおり。

| リソース | 名前と内容 |
|---|---|
| リソースグループ | `rg-slide-image-gen-mcp` |
| Foundry（AI Services）アカウント | `aif-slide-image-gen-<6 文字>-<リージョン>`。6 文字はサブスクリプション ID から生成する |
| モデルのデプロイ | `gpt-image-2`（GlobalStandard）。リージョンあたりの capacity は 2 まで |
| ロール割り当て | 実行したユーザーに、各アカウントの Cognitive Services User |

`aif` は、Foundry アカウント（kind: AIServices）に対する [Azure リソースの略語の推奨](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations)（リソースの種類ごとの接頭辞が分かる）に合わせている。

アカウント名はカスタムサブドメインとして Azure 全体で一意である必要がある。サブスクリプションごとに異なる 6 文字を含めるため、別の利用者と名前が衝突せず、同じサブスクリプションで再実行すれば同じ名前になる。

環境によって結果が変わる箇所は、次のように扱う。1 つのリージョンで失敗しても処理を止めず、残りのリージョンで続行する。

| 状況 | 扱い |
|---|---|
| GPT-Image-2 が提供されていないリージョン | スキップする |
| クォータに空きがない | スキップする。空きが capacity の上限より少ない場合は、空きの分だけ割り当てる |
| アカウント名が使用済み | スキップする。削除から 48 時間以内のアカウントが名前を保持している場合は、完全に削除（purge）するコマンドを表示する |
| リソースグループが既にある | そのまま使用する |
| アカウントとデプロイが既にある | 作り直さずに使用する |
| デプロイが失敗した（Azure Policy による禁止など） | エラーの内容を表示し、スキップする |
| ロールを付与する権限がない | リソースは作成し、管理者に依頼するロールの付与コマンドを表示する |

env ファイルには、実行したユーザーが呼び出せるリージョンの接続先だけを書く。MCP は 401・403 を別のリージョンで再試行しないため、呼び出せないリージョンを含めると一部の呼び出しが失敗する。
呼び出せるかどうかは、Cognitive Services User、Foundry User など、画像の生成と編集を許可するロールがグループ経由も含めて付与されているかで判定する。
どのリージョンでもロールを付与できなかった場合に限り、作成したリージョンをすべて書く。管理者がロールを付与すれば、そのまま使用できる。

スキップしたリージョンは、原因を解消してから再実行すると追加される。

| オプション | 既定値 | 説明 |
|---|---|---|
| `--check` | — | 調べた結果だけを表示する |
| `--regions` | `eastus2,westus3,swedencentral,polandcentral,uaenorth` | 試すリージョン（カンマ区切り） |
| `--resource-group` | `rg-slide-image-gen-mcp` | リソースグループ名 |
| `--capacity` | `2` | リージョンあたりの capacity の上限 |
| `--name-prefix` | `aif-slide-image-gen-<6 文字>` | アカウント名の接頭辞。末尾に `-<リージョン>` が付く |
| `--env-file` | `~/.config/slide-image-gen/env` | 書き込む env ファイル |
| `--no-role` | — | ロール割り当てを作成しない（ロールを別途管理する場合） |

無申請のクォータは、1 リージョンあたり capacity 2（約 2 RPM）。足りなければリージョンごとに増加を申請する。手順は [Azure OpenAI のクォータ管理](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/quota)（リージョン単位で割り当てを引き上げる方法が分かる）。
対応リージョンはモデルの更新で変わる。スクリプトは指定されたリージョンごとに提供状況を確かめるが、新たに対応したリージョンを使用するには `--regions` で指定する。対応状況は [モデルのリージョン可用性](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models#model-summary-table-and-region-availability) で確認する。

既存のアカウントを削除してクォータを空ける場合は、デプロイを先に削除してからアカウントを削除する。アカウントを先に削除すると、purge するまでの 48 時間はクォータが解放されない。
[クォータの管理: リソースの削除](https://learn.microsoft.com/azure/foundry/openai/how-to/quota#resource-deletion) に、削除の順序と、クォータが解放されない期間が書かれている。

## 3. 接続先の設定（env ファイル）

`deploy.py` を実行すると、`~/.config/slide-image-gen/env` に接続先が書き込まれる（環境変数 `SLIDE_IMAGE_GEN_ENV_FILE` があれば、その場所に書き込む）。
既存のファイルは `env.bak` に退避し、スクリプトが管理しないキー（`LB_COOLDOWN_SECONDS` など）はそのまま残す。単数形の `FOUNDRY_ENDPOINT` は、古い接続先が混ざらないよう削除する。

MCP サーバーは起動時に次の順で探し、最初に見つかった 1 ファイルを読んで環境変数に取り込む。既に設定されている環境変数は上書きしない。

1. 環境変数 `SLIDE_IMAGE_GEN_ENV_FILE` が指すファイル
2. カレントディレクトリの `.slide-image-gen.env`（案件ごとに接続先を変えるとき。`.gitignore` 済み）
3. `~/.config/slide-image-gen/env`（Windows は `%APPDATA%\slide-image-gen\env`）

形式は 1 行 1 組の `KEY=VALUE`。`#` で始まる行はコメント、空行は無視、値の前後の引用符は外される。手で書く場合も同じ形式にする。

```bash
# ~/.config/slide-image-gen/env
FOUNDRY_ENDPOINTS=https://<アカウント名 1>.cognitiveservices.azure.com/,https://<アカウント名 2>.cognitiveservices.azure.com/
IMAGE_DEPLOYMENT_NAME=gpt-image-2
# Foundry が属するテナント（az login のテナントと異なる場合に指定する）
FOUNDRY_TENANT_ID=00000000-0000-0000-0000-000000000000
```

## 4. 起動定義の登録

接続先を env ファイルに置くため、起動定義はどの経路でも同じ 1 行になる。登録は 2 通り。

### (a) プラグイン `pptx-as-code` を導入する（推奨）

起動定義（ルートの `mcp.json`）がプラグインに同梱されているため、**スキルを入れた時点で MCP も有効になる。** 設定ファイルへの追記は不要。導入手順は [プラグインの README](../README.md#導入)。

### (b) ユーザー設定に 1 行書く

プラグインとして読み込んでいない場合（clone したリポジトリの `skills/` だけをコピーして使う場合など）に使用する。

```bash
# Claude Code
claude mcp add -s user slide-image-gen -- uv run --directory ~/pptx-as-code/mcp-server slide-image-gen-mcp

# GitHub Copilot CLI（~/.copilot/mcp-config.json に書かれる）
copilot mcp add slide-image-gen -- uv run --directory ~/pptx-as-code/mcp-server slide-image-gen-mcp
```

## 5. 使い方

クライアントを再起動して MCP が認識されたら、チャットで指示する。画像は 16:9（1792x1008）で保存される。

- ツール `generate_slide_image` はモデルが呼び出す。利用者から明示的に呼び出す場合は、プロンプト `generate` を使用する（Claude Code では `/mcp__slide-image-gen__generate <主題>`）。チャットで「slide-image-gen で画像を作成」と指示してもよい
- **スライド 1 枚の案**を指示する。タイトル・見出し・図中のラベルを短い日本語で含んだ構図にすると、配置ごと設計してもらえる。文字の精度が要るのは資料側なので、画像の文字は構図を読むためのものとして扱う
- 複数枚は 1 枚ずつ順に呼ばれる。「5 ページ分をそれぞれ画像にして」で足りる。サーバーが呼び出しごとに別リージョンへ分散し、429 は別リージョンで再試行する
- 生成画像は資料に貼らずネイティブ要素で描き直すため、成果物に画像は残らない。独自のモチーフだけを切り出して使う場合は [顧客著作権コミットメント](https://learn.microsoft.com/azure/foundry/responsible-ai/openai/customer-copyright-commitment)（Microsoft が一定の第三者著作権クレームに対し顧客を防御する条件が書かれている）を確認する。生成画像には [Content Credentials](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/content-credentials)（AI 生成であることを示す C2PA のメタデータ）が付くが、切り出しや透過処理で失われる
- 参考画像は**絶対パス**で渡す（「`/home/me/deck/source/sample.png` を参考に、同じレイアウトで緑基調に」）。チャットに直接添付した画像は MCP に渡らないので、ファイルに保存してから指示するか、画像の内容を言葉で伝える

## 6. 環境変数

| 変数 | 必須 | 既定値 | 説明 |
|---|---|---|---|
| `FOUNDRY_ENDPOINTS` | ※ | — | Foundry のエンドポイント（複数可。カンマまたは改行区切り）。`/openai/v1` は省略可 |
| `FOUNDRY_ENDPOINT` | ※ | — | 単一エンドポイント（後方互換）。両方あれば和集合 |
| `IMAGE_DEPLOYMENT_NAME` | yes | — | 全リージョン共通のデプロイ名（例 `gpt-image-2`） |
| `FOUNDRY_TENANT_ID` | no | — | Foundry が属する Entra テナント ID。`az login` のテナントと異なるときに指定する |
| `DEFAULT_OUTPUT_DIR` | no | `./output` | 既定の保存先。相対パスはサーバーのカレントディレクトリ基準になるため、絶対パスを推奨 |
| `LB_COOLDOWN_SECONDS` | no | `60` | 429 時に `Retry-After` が無い場合のクールダウン秒数 |
| `SLIDE_IMAGE_GEN_ENV_FILE` | no | — | env ファイルの場所を明示する（探索順の先頭） |

※ いずれか一方が必要。シークレットは置かない（トークンは `DefaultAzureCredential` が取得する）。

## 7. ツール仕様

`generate_slide_image`

| 引数 | 型 | 既定値 | 説明 |
|---|---|---|---|
| `prompt` | string | （必須） | 画像生成の指示文。会話履歴を統合した詳細な指示を推奨 |
| `quality` | `low` / `medium` / `high` | `high` | 画質。既定の `high` は画像内の日本語が崩れにくい。構図だけを速く見たいときだけ下げる |
| `reference_image_path` | string | null | 参考画像のパス（**絶対パス**）。指定時は `images.edit` |
| `output_dir` | string | env で決まる | 保存先（**絶対パス**）。資料を作っている場合はその作業フォルダーの中、画像だけを作る場合は利用者が開いているプロジェクトの中を指定する |
| `filename_hint` | string | null | ファイル名ヒント（英数字とハイフンに正規化） |

**`reference_image_path` と `output_dir` は絶対パスで渡す。** このサーバーのカレントディレクトリは、起動したクライアント（Copilot CLI、VS Code、Claude Code）が決めるもので、資料を作っているフォルダーとは限らない。相対パスを渡すと、意図しない場所に保存される。
相対パスは後方互換のためカレントディレクトリ基準で解決するが、頼らない。

戻り値: `saved_path`（絶対パス）、`size`（`1792x1008`）、`model`（デプロイ名）、`endpoint`（生成したリージョン）、`bytes`。

## 8. フェイルオーバーの挙動

- 呼び出しごとにエンドポイントをラウンドロビンで選ぶ（起動時に順序をシャッフル）
- 429、タイムアウト、接続断、5xx はそのリージョンをクールダウン（`Retry-After` 秒、無ければ 60 秒）させ、次のリージョンで即座に再試行する。1 回の呼び出しでリージョン数まで試す
- 認証エラー、404（デプロイ名不一致）、コンテンツフィルタ（400）は別リージョンでも直らないので、そのまま返す
- 全リージョンがクールダウン中なら 30 秒以内の待ちだけ待ち、超えるならレート制限エラーを返す

## 9. モデルの更新

全リージョンで同じデプロイ名を使うため、世代交代は 2 手順。

1. `infra/deploy.py` の `MODEL_NAME`・`MODEL_VERSION`・`REGIONS` を新しいモデルに合わせて変え、再実行する。新しいデプロイが作成され、env ファイルの `IMAGE_DEPLOYMENT_NAME` も書き換わる
2. クライアントを再起動する。コードの変更は不要

新しいモデルのクォータが足りない場合は、古いデプロイを削除してから再実行する。
API に非互換の変更が入った場合だけ [foundry_client.py](src/slide_image_gen_mcp/foundry_client.py) を直す。

## 10. ローカル開発

clone したソースで動かすときは `uv run` を使う。起動定義には `--project` を使う（カレントディレクトリを変えない）。
`--directory` は MCP のディレクトリへ移動してから実行するため、保存先とパス制限の基準が作業ディレクトリでなくなる。

```bash
git clone https://github.com/akitamoto-dev/pptx-as-code.git ~/pptx-as-code
cd ~/pptx-as-code/mcp-server && uv sync          # 依存を uv.lock どおりに入れる
uv run --project ~/pptx-as-code/mcp-server slide-image-gen-mcp   # 手動で起動して確かめる（Ctrl+C で終了）

# 起動定義（Claude Code の例。Copilot CLI は copilot mcp add）
claude mcp add -s user slide-image-gen -- uv run --project ~/pptx-as-code/mcp-server slide-image-gen-mcp
```

依存が古いまま残っている場合は
`uv sync --directory ~/pptx-as-code/mcp-server` を実行して依存を入れ直す。

## 11. ディレクトリ構成

```
pptx-as-code/
├── infra/
│   ├── deploy.py                    リージョンごとに調べてデプロイし、env ファイルに書き込む
│   └── foundry-image.bicep          1 リージョン分（アカウント + デプロイ + ロール割り当て）
├── mcp.json                         起動定義。両方の plugin.json が参照する
└── mcp-server/                      MCP 本体。mcp.json の起動処理がこの場所を探して起動する
    ├── pyproject.toml / uv.lock     エントリポイント定義と依存の固定
    └── src/slide_image_gen_mcp/
        ├── __main__.py              エントリポイント（env ファイルの読み込み → stdio 起動）
        ├── config.py                env ファイルの探索と読み込み
        ├── server.py                ツール定義（generate_slide_image、パス制限）
        ├── endpoint_pool.py         ラウンドロビン + フェイルオーバー + クールダウン
        └── foundry_client.py        Foundry 呼び出し（Entra ID 認証）
```

起動定義をプラグインに含めているのは、スキルと MCP を 1 つのプラグインとして配るため。導入も更新も 1 コマンドで済む。
`mcp.json` はクライアントから受け取ったプラグインの導入先をもとに、同梱の本体をその場で起動する。
リポジトリから取り直さないので、起動にネットワークが要らず、タグの管理も不要になる。

`node` の短い起動処理を挟んでいる理由は [docs/architecture.md](../docs/architecture.md#画像生成-mcp) にある。導入先の値が Windows 形式で届く環境があること、変更するときに守る点（`$schema` と `${` を書かない）が分かる。
