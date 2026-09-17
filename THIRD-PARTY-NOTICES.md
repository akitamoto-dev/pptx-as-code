# 同梱物の権利表示

このリポジトリ自体は MIT ライセンス（[LICENSE](LICENSE)）。加えて、第三者が提供するものを同梱している。以下にその権利表示を記載する。

## Fluent UI System Icons

`skills/blue-format/icons/` の PNG は、[Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) の SVG から色を指定して生成したもの。取得元と色の定義は `skills/blue-format/icons/icons.json` にある。

```
MIT License

Copyright (c) 2020 Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

この表示は、資料を社外へ配布する場合にも保持する。別のアイコンセットへ差し替えた場合は、そのセットの表示条件に従う（Lucide は ISC、Tabler は MIT、Material Symbols は Apache-2.0）。

## 実行時に取得するもの

次のものは同梱しておらず、`env-setup` が実行時に公式の配布元から取得する。それぞれの提供元の条件に従う。

| 名前 | 用途 | 提供元 |
|---|---|---|
| pptxgenjs | pptx の生成 | [gitbrent/PptxGenJS](https://github.com/gitbrent/PptxGenJS) |
| Pillow、PyMuPDF、python-pptx | 画像の処理と検証 | PyPI |
| fastmcp、openai、azure-identity | 画像生成 MCP | PyPI |
| LibreOffice | PDF への変換 | [The Document Foundation](https://www.libreoffice.org/) |
| Noto Sans CJK JP | 日本語フォント | [Google Fonts](https://github.com/notofonts/noto-cjk) |
