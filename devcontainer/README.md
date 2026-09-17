# コンテナ内での環境構築（サンドボックス環境）

スライド作成の環境を Dev コンテナの中に構築するための定義。**作業を隔離した状態で実行できる。**

エージェントはパッケージの導入とコマンドの実行を伴うため、既存の環境への影響を完全には制御できない。手元の環境を変更せずに試す場合や、影響の範囲を限定したい場合に使用する。ホスト側に Node.js や LibreOffice を導入する必要もない。
参考として同梱しているため、使用するときは資料を作成するプロジェクトへ複製する。

## 使用方法

1. `devcontainer.json` を、資料を作成するプロジェクトの `.devcontainer/devcontainer.json` に配置する。エージェントに「Dev コンテナの定義をこのプロジェクトに配置して」と指示すると、プラグインの中から複製される
2. VS Code でそのプロジェクトを開き、コマンドパレットの「Dev Containers: Reopen in Container」を実行する。コンテナの作成時に、このプラグインが導入される
3. コンテナの中のターミナルでサインインする。GitHub Copilot CLI は `copilot login`、Claude Code は `claude` を起動して案内に従う。Copilot でブラウザーが 127.0.0.1 に飛んで失敗する場合は `copilot login --device-code` を使う。キーチェーンが無いため、トークンを平文で保存してよいか聞かれる
4. コンテナの中で `copilot` または `claude` を起動し、`/pptx-as-code:env-setup` を実行する。`env-setup` が点検し、不足分を導入する

GitHub Copilot CLI と Claude Code の両方が導入されるため、使用する方だけサインインする。
Claude Code は npm を経由しない配布形式で `~/.local/bin` に導入されるため、コンテナの中から `claude update` で更新できる。

uv もコンテナの作成時に導入する。画像生成 MCP を起動するのはクライアント本体で、利用者のシェルの PATH を引き継がないため、後から導入すると検出できない。事前に導入し、`/usr/local/bin` から参照できるようにしている。

## 前提

- Docker の実行環境。WSL から使う場合は、Docker Desktop の Settings > Resources > WSL Integration で、そのディストリビューションを有効にする
- VS Code の Dev Containers 拡張。導入とコンテナの開き方は [Developing inside a Container](https://code.visualstudio.com/docs/devcontainers/containers)（拡張の導入手順、コンテナで開く操作、定義の書き方が分かる）を参照

## 備考

- コンテナを作り直すと、導入したものとサインインの状態が失われる。再度 `env-setup` を実行する。停止と再開のみであれば残る
- 書式が指定する Yu Gothic UI はコンテナに存在しないため、PDF と確認用の画像は Noto Sans CJK JP で描かれる。文字幅が変わるので、最終的な見た目は PowerPoint で確認する
- 画像生成 MCP を使用する場合は、コンテナの中で `az login` が必要。ブラウザーを開けない環境ではデバイスコードでのサインインになる
- ホスト側の資格情報はマウントしない。必要なものはコンテナの中で導入する
