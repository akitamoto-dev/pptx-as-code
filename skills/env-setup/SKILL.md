---
name: env-setup
description: "スライド作成（content-to-pptx / image-to-pptx / pptx-lint）に必要な環境を点検し、不足しているものを OS に合わせて導入する。画像生成 MCP を使う場合は Foundry のデプロイと接続設定も扱う。「環境構築」「セットアップ」「スライド作成の準備」「MCP の設定」「動かない」でトリガー。"
user-invocable: true
---

# env-setup スキル

必要なものをすべて導入する。導入できなかったものはその内容を報告し、導入できたものだけで動かす（代替は末尾の「判断の指針」）。

**導入は黙って実行しない。** 点検結果と、これから実行するコマンドを利用者に見せ、承諾を得てから走らせる。sudo・管理者権限・既存の設定ファイルの書き換えは事前に確認する。

**利用者に確認を返してもらえない場合（自動承認や非対話での実行）は、次の線で分ける。** 承諾が取れないことを理由に全体を止めない。

- 進めてよい: 依頼された導入そのもの（パッケージの導入、作業ディレクトリでの `npm install`、動作確認）。実行したコマンドは出力に残す
- 止めて報告する: パッケージ取得先の向き先の変更（`npm config set registry` など、既定以外を指させること）、既存の設定ファイルの書き換え。組織の統制・他の設定に影響するため、利用者の判断が要る。導入手順が公式に示すリポジトリの追加（Azure CLI の apt リポジトリなど）と、公式の配布元からの取得（プロジェクト本体の GitHub、OS の公式パッケージ）は通常の導入なので、ここに含めない

止めたときは、何を止めたかだけでなく、**続けるために利用者に何をしてほしいかを 1 行で書く**。「明示的な承認が得られるまで導入していません」では、利用者は次に何をすればよいか分からない。「導入してよければ、そう伝えてください」のように、返す言葉を示す。

**利用者が自分で動けない案内で終わらせない。** 「ネットワーク管理者に確認を依頼してください」は、その場では何も進まない。利用者がその場で答えられる形（「組織の Python パッケージ取得先（index-url）を教えてください」など）で尋ねる。答えが得られない場合は、**できなかった機能だけを切り分けて残りを完了させ**、何が使えて何が使えないかを示す。

**sudo はまず `sudo -n true` で試す。** パスワード無しで通る環境（多くのコンテナや CI）ではそのまま実行してよい。通らない場合だけ、エージェントの端末には入力手段が無く `sudo: a terminal is required to read the password` で止まるため、その 1 行を利用者に実行してもらい、終わったら続きを進める。Windows で管理者権限を求められる導入も同じ。

**導入コマンドの実行そのものが権限で拒否される場合は、回避策を探さない。** 権限を絞ったまま自動で進むモードに入ると、確認を返す相手がいないため導入コマンドがすべて拒否される。何が拒否されたかを伝えたうえで、次のどちらかを実行してもらい、終わったらもう一度依頼してもらう。

- GitHub Copilot CLI: セッションの中で `/allow-all` を実行して全許可にする。または Shift+Tab で通常の対話モードに戻し、確認に 1 つずつ答えてもらう
- Claude Code: Shift+Tab でモードを切り替える（auto mode は確認を classifier が代行する）。コンテナなど隔離された環境に限り、`claude --dangerously-skip-permissions` で起動し直す

## 技術スタック

| 区分 | 導入するもの | 用途 |
|---|---|---|
| PowerPoint の生成 | Node.js、pptxgenjs（作業ディレクトリでの `npm install`） | スライドをコードで組み立て、pptx を出力する |
| 規格の検査 | Python 3（標準ライブラリだけ） | PowerPoint が破損と判定する箇所の修正と検出 |
| PDF と画像への変換 | LibreOffice、poppler（`pdftoppm`）または PyMuPDF、日本語フォント | pptx → PDF → PNG |
| 画像から PowerPoint への変換 | uv（Pillow、PyMuPDF、python-pptx を `uv run` が解決する） | 座標把握、切り出し、レンダリング比較、編集可能性の検証 |
| 画像生成 | uv、Azure CLI、Azure サブスクリプション | Microsoft Foundry で画像形式のスライドを生成する（MCP `slide-image-gen`） |

## 1. 点検する

```bash
bash <このスキル>/scripts/doctor.sh <作業ディレクトリ>
```

読み取り専用で、何も導入・変更しない。表の「なし」の行を利用者に見せ、これから導入するものを確認する。

Windows ネイティブには点検スクリプトを用意していない。`node --version`、`python --version`、`where soffice` を個別に確認する。

## 2. 導入する

承諾を得たら、足りないものをすべて入れる。用途が限られるものも、後で詰まらないようにここで入れておく。

| OS | コマンド |
|---|---|
| Ubuntu / Debian / WSL | `sudo apt-get update && sudo apt-get install -y nodejs npm python3 libreoffice-impress fonts-noto-cjk poppler-utils` |
| macOS | `brew install node python uv && brew install --cask libreoffice font-noto-sans-cjk` |
| Windows | `winget install OpenJS.NodeJS.LTS Python.Python.3.12 astral-sh.uv TheDocumentFoundation.LibreOffice` |

uv（Linux / WSL）は `curl -LsSf https://astral.sh/uv/install.sh | sh`。導入後はシェルを開き直すか `~/.local/bin` を PATH に足す。

Azure CLI は Ubuntu / WSL が `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`、macOS が `brew install azure-cli`、Windows が `winget install Microsoft.AzureCLI`。画像生成 MCP でしか使わないが、使う段になって止まらないよう、ここで一緒に入れる。

補足:

- pptxgenjs はグローバルに入れない。作業ディレクトリで `npm install` すると `package.json` から入る
- apt の Node.js が 18 未満のときは [nodejs.org](https://nodejs.org/) の LTS か nvm に置き換える
- WSL で Windows 側の Yu Gothic を使う: `mkdir -p ~/.local/share/fonts && ln -sf /mnt/c/Windows/Fonts/YuGoth*.ttc ~/.local/share/fonts/ && fc-cache -f`
- 日本語フォントが用意できない場合、PDF は代替フォントで描画される（PowerPoint では正しく出る）
- pip が「externally-managed-environment」で拒否される環境では、uv を入れて `uv run` に任せる
- Windows ネイティブは LibreOffice を入れれば動く見込み。実機検証はこれからなので、WSL が使えるならそちらを勧める

### パッケージの取得先が塞がれている場合

`npm install` や `uv run` が TLS の失敗（handshake failure）や 403 で止まる環境がある。ネットワーク全体が不通なわけではないので、次の順で切り替える。

1. 同じ利用者の別の環境で、設定されている取得先を尋ねる

   ```bash
   npm config get registry
   pip config list
   ```

   **尋ねる先は、塞がれている環境と同じ経路の環境にする。** 同じ端末でも、WSL は通るのにコンテナや Windows は塞がれる、という組み合わせがある。制限を受けていない側を調べても「既定のまま」としか分からず、社内の取得先を見落とす。Docker Desktop のコンテナは Windows 側と同じ経路なので、Windows 側の設定を尋ねる。

2. 既定（`https://registry.npmjs.org/`、PyPI）以外が設定されていれば、作業する環境にも同じ値を設定する。**この設定変更は利用者の判断が要る**ので、値を見せて確認してから行う

   ```bash
   npm config set registry <取得先>
   mkdir -p ~/.config/pip && printf '[global]\nindex-url = <取得先>\n' > ~/.config/pip/pip.conf
   export UV_INDEX_URL=<取得先>   # uv にも同じ取得先を渡す
   ```

3. **社内の取得先が無い、または分からない場合は、公式の配布元に切り替える。** 推測ではないので、承諾を待たずに進めてよい

   | 入れるもの | 切り替え先 |
   |---|---|
   | pptxgenjs | 公式 GitHub（`gitbrent/PptxGenJS`）のタグを clone し、`dist/`・`types/`・`package.json` を作業ディレクトリの `node_modules/pptxgenjs/` に置く。依存の JSZip は apt の `node-jszip` |
   | PyMuPDF・Pillow | apt の `python3-fitz`・`python3-pil` |
   | python-pptx | 公式 GitHub（`scanny/python-pptx`）のタグを clone し、`python3 -m pip install --user --break-system-packages --no-deps --no-build-isolation <clone 先>` |

   apt が無い環境（macOS / Windows）では、OS の公式パッケージの代わりに Homebrew / winget の公式パッケージを使い、無いものは公式 GitHub から取る。
   置き換えたら §3 の動作確認まで通し、一時的に clone したものは消す。`node_modules/pptxgenjs` を直接置いた作業ディレクトリでは、あとから `npm install` を実行すると取得しに行って失敗するので実行しない。

   **画像生成 MCP の依存（fastmcp、openai、azure-identity ほか）には、この切り替えが効かない。** PyPI 以外の配布が無く、公式 GitHub から入れると依存の木が深すぎて現実的でないため。ここだけは組織の取得先が要る。分からないまま進める場合は、**MCP は使えないと伝え、画像生成なしで残りを完了させる**（スライド作成そのものは MCP なしで動く）。取得先が分かったら `UV_INDEX_URL` に設定し、**エージェントを同じシェルから起動し直す**（MCP はエージェントが起動するため、環境変数が引き継がれない）。

4. **非公式のミラーや中継は使わない。** 使ってよいのは、組織が指定した取得先と、公式の配布元（プロジェクト本体の GitHub、OS の公式パッケージ）だけ。それ以外は取得元を勝手に変えることになり、組織の統制からも外れる

## 3. 動作を確認する

```bash
mkdir -p ~/work/deck-test && cp -r <プラグイン>/template/. ~/work/deck-test/
cd ~/work/deck-test && npm install && node build.js --name sample
```

- `sample.pptx`、`sample.pdf`、`preview/sample-001.png` がすべてできれば完了。できなかったものがあれば、何が足りないかを報告する
- `preview/sample-001.png` を読んで文字化けが無ければフォントも問題ない
- 「規格違反なし」が出ていれば PowerPoint で開ける
- Python 側の依存解決も 1 回試す: `uv run --with pymupdf python -c "import pymupdf; print('ok')"`。点検スクリプトは実体の有無を見るだけなので、取得先が塞がれている環境はここで分かる

## 4. 画像生成 MCP を設定する

Azure サブスクリプションが必要。**環境構築の一部としてデプロイまで行い、MCP が使える状態にする。** 作成するリソースは `--check` の出力で見せる。Foundry アカウントと Global Standard のデプロイは従量課金なので、作った時点では費用が発生しない（生成した画像の分だけかかる）。
**`az login` は利用者に実行してもらう。** ブラウザーでの承認が要るため、エージェントからは完了できない。コンテナや SSH など、ブラウザーの折り返しを受け取れない環境では `az login --use-device-code` を使い、表示されたコードと URL を利用者に伝えて承認を待つ。
デプロイ手順と環境変数の詳細はリポジトリの `plugins/slide-image-gen/README.md` にある。要点は次の 3 つ。

1. **Foundry をデプロイする**。プラグインに同梱している `infra/deploy.py` を使う（プラグインの導入先にあるので、clone は要らない）。まず `python3 infra/deploy.py --check` を実行し、作成するリソース、リージョンごとの判定、書き込む env ファイルを見せてから、`python3 infra/deploy.py` を実行する。対応リージョンを 1 つずつ調べ、モデルが提供されていない、クォータに空きがない、名前が使用済み、デプロイに失敗したリージョンはスキップして続行する
2. **接続先は `deploy.py` が env ファイルに書き込む**。MCP の設定ファイルには書かない。サーバーは `SLIDE_IMAGE_GEN_ENV_FILE` → カレントの `.slide-image-gen.env` → `~/.config/slide-image-gen/env` の順で読む。手で書く場合の形式は次のとおり

   ```
   FOUNDRY_ENDPOINTS=https://<ep1>.cognitiveservices.azure.com/,https://<ep2>.cognitiveservices.azure.com/
   IMAGE_DEPLOYMENT_NAME=gpt-image-2
   FOUNDRY_TENANT_ID=<tenant-id>
   ```

   使えるリージョンが 1 つも無い場合（終了コード 1）は、表示された理由（クォータ、Azure Policy、権限など）を利用者に伝え、起動定義の登録には進まない。ロールを付与する権限が無い場合は、表示された付与コマンドを管理者に依頼するよう伝える

3. **起動定義を登録する**。接続先を設定ファイルに書かないので、起動定義は誰でも同じ 1 行になる

   | 方法 | コマンド |
   |---|---|
   | プラグイン（推奨） | `copilot plugin install slide-image-gen@pptx-as-code` / `claude plugin install slide-image-gen@pptx-as-code` |
   | 直接登録 | `claude mcp add -s user slide-image-gen -- uvx --from "git+https://github.com/akitamoto-dev/pptx-as-code.git@v0.1.0#subdirectory=plugins/slide-image-gen" slide-image-gen-mcp` |
   | 直接登録（Copilot CLI） | `copilot mcp add slide-image-gen -- uvx --from "git+https://github.com/akitamoto-dev/pptx-as-code.git@v0.1.0#subdirectory=plugins/slide-image-gen" slide-image-gen-mcp` |

   登録の前に `command -v uvx` で実体を確かめる。`~/.local/bin` に入れた直後などで PATH に無い場合、エージェントが起動する MCP には PATH が引き継がれず、「No such file or directory」で接続に失敗する。そのときは絶対パス（`~/.local/bin/uvx`）で登録する。

   プラグイン経由なら設定ファイルへの追記は要らない。プロジェクトの `.mcp.json` や `.vscode/mcp.json` には勝手に書かない（書くなら内容を見せて承諾を得てから、起動定義だけを書く）。

クライアントを再起動し、`generate_slide_image` ツールが見えれば完了。初回は uvx がパッケージを取得するため時間がかかる。

## 前提バージョン

Node.js 18 以上、Python 3.10 以上、GitHub Copilot CLI 1.0.74 以上、VS Code 1.118 以上、Claude Code 2.1 以上。

## 判断の指針

- すべて導入する。導入できなかったものはその内容を報告し、導入できたものだけで動かす
- 導入できないものがあっても止めない。代替（PowerPoint での PDF 変換、代替フォント、PNG を省略して PDF を渡す）を示して続行する
- 設定ファイルを書き換えるときは、読み込んでから追記し、他の定義を消さず、書き換え後に JSON として妥当かを確かめる
