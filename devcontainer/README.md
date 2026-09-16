# コンテナで使う

スライド作成の環境を、コンテナの中に作るための定義。ホスト側に Node.js や LibreOffice を入れずに試せる。
参考として同梱しているものなので、使うときは資料を作るプロジェクトへコピーする。

## 使用方法

1. `devcontainer.json` を、資料を作るプロジェクトの `.devcontainer/devcontainer.json` に置く。エージェントに「コンテナの定義をこのプロジェクトに置いて」と伝えれば、プラグインの中からコピーされる
2. VS Code でそのプロジェクトを開き、コマンドパレットの「Dev Containers: Reopen in Container」を実行する。コンテナの作成時に、このプラグインが入る
3. コンテナの中のターミナルでサインインする。GitHub Copilot CLI は `copilot login`、Claude Code は `claude` を起動して案内に従う。Copilot でブラウザーが 127.0.0.1 に飛んで失敗する場合は `copilot login --device-code` を使う。キーチェーンが無いため、トークンを平文で保存してよいか聞かれる
4. コンテナの中で `copilot` または `claude` を起動し、`/pptx-as-code:env-setup` を実行する。`env-setup` が点検し、足りないものを導入する

GitHub Copilot CLI と Claude Code の両方が入るので、使う方だけサインインすればよい。
Claude Code は npm を経由しない配布形式で `~/.local/bin` に入るため、コンテナの中から `claude update` で更新できる。

## 前提

- Docker の実行環境。WSL から使う場合は、Docker Desktop の Settings > Resources > WSL Integration で、そのディストリビューションを有効にする
- VS Code の Dev Containers 拡張。導入とコンテナの開き方は [Developing inside a Container](https://code.visualstudio.com/docs/devcontainers/containers)（拡張の導入手順、コンテナで開く操作、定義の書き方が分かる）を参照

## 備考

- コンテナを作り直すと、導入したものとログインが消える。もう一度 `env-setup` に依頼する。停止と再開だけなら残る
- 書式が指定する Yu Gothic UI はコンテナに無いため、PDF と確認用の画像は Noto Sans CJK JP で描かれる。文字幅が変わるので、最終的な見た目は PowerPoint で確認する
- 画像生成 MCP を使う場合は、コンテナの中で `az login` が必要。ブラウザーを開けない環境ではデバイスコードでのサインインになる
- ホスト側の資格情報はマウントしない。必要なものはコンテナの中で入れる
