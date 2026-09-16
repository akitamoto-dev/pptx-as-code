#!/usr/bin/env python3
# /// script
# dependencies = ["resvg-py>=0.1"]
# ///
"""正規アイコン（既定は Fluent UI System Icons・MIT）を Iconify から取得し、色とサイズを指定して PNG にする。

使い方（作業ディレクトリで実行する）:
    uv run tools/fetch_icons.py                               assets/icons/icons.json を読み、足りない分だけ取得する
    uv run tools/fetch_icons.py <出力ディレクトリ> <spec> [--force]   出力先と spec を指定する（spec はファイルか JSON 文字列）

spec の例（icon は Iconify の "prefix:name"。名前は https://icon-sets.iconify.design/fluent/ で確認する）:
    [
      {"name": "shield_primary", "icon": "fluent:shield-24-filled",    "color": "0078D4", "size": 128},
      {"name": "database_white", "icon": "fluent:database-24-regular", "color": "FFFFFF"}
    ]

- 既に同名の PNG があれば飛ばす（--force で作り直す）
- SVG → PNG の変換は resvg-py（pure wheel。`uv run fetch_icons.py ...` なら自動で入る）を使い、無ければ cairosvg を試す
- 存在しないアイコン名は Iconify が空の SVG（HTTP 200）を返すので、描画要素の無い SVG は失敗として扱う
- api.iconify.design へのネットワーク到達が必要。届かない環境では同梱済みのアイコンだけを使う
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API = "https://api.iconify.design"
DRAW_TAGS = (b"<path", b"<circle", b"<rect", b"<polygon", b"<polyline", b"<ellipse", b"<line", b"<g")


def fetch_svg(icon_id, color=None):
    if ":" not in icon_id:
        raise ValueError(f"icon は 'prefix:name' の形で指定する: {icon_id}")
    prefix, name = icon_id.split(":", 1)
    url = f"{API}/{urllib.parse.quote(prefix)}/{urllib.parse.quote(name)}.svg"
    if color:
        url += "?" + urllib.parse.urlencode({"color": f"#{color}"})
    req = urllib.request.Request(url, headers={"User-Agent": "pptx-as-code"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    if not data.lstrip().startswith(b"<svg"):
        raise RuntimeError(f"SVG ではない応答: {data[:60]!r}")
    if not any(tag in data for tag in DRAW_TAGS):
        raise RuntimeError("空の SVG（アイコン名が存在しない可能性。icon-sets.iconify.design で確認する）")
    return data


def rasterize(svg_bytes, out_path, size):
    try:
        import resvg_py

        png = resvg_py.svg_to_bytes(svg_string=svg_bytes.decode("utf-8"), width=size, height=size)
        with open(out_path, "wb") as f:
            f.write(bytes(png))
        return "resvg"
    except ImportError:
        pass
    try:
        import cairosvg

        cairosvg.svg2png(bytestring=svg_bytes, write_to=out_path, output_width=size, output_height=size)
        return "cairosvg"
    except ImportError as e:
        raise RuntimeError("resvg-py か cairosvg が必要（pip install resvg-py、または uv run fetch_icons.py ...）") from e


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv
    if not args:
        # 引数なしは作業ディレクトリの既定の置き場を使う
        out_dir, spec_arg = "assets/icons", os.path.join("assets", "icons", "icons.json")
        if not os.path.isfile(spec_arg):
            sys.exit(f"{spec_arg} が無い。使い方: fetch_icons.py [<出力ディレクトリ> <spec.json|JSON 文字列>] [--force]")
    elif len(args) < 2:
        sys.exit("使い方: fetch_icons.py [<出力ディレクトリ> <spec.json|JSON 文字列>] [--force]")
    else:
        out_dir, spec_arg = args[0], args[1]
    spec = json.load(open(spec_arg, encoding="utf-8")) if os.path.isfile(spec_arg) else json.loads(spec_arg)
    os.makedirs(out_dir, exist_ok=True)
    failures = []
    done = 0
    for item in spec:
        name = item["name"]
        out = os.path.join(out_dir, f"{name}.png")
        if os.path.exists(out) and not force:
            continue
        size = int(item.get("size", 128))
        try:
            engine = rasterize(fetch_svg(item["icon"], item.get("color")), out, size)
            print(f"{name}.png  <- {item['icon']}  {size}px ({engine})")
            done += 1
        except Exception as e:  # noqa: BLE001
            failures.append((name, item.get("icon"), str(e)))
            print(f"[失敗] {name} <- {item.get('icon')}: {e}")
    if failures:
        print(f"失敗 {len(failures)} 件。アイコン名を https://icon-sets.iconify.design で確認する")
        sys.exit(1)
    print(f"完了: {done} 件を取得（既存はスキップ）")


if __name__ == "__main__":
    main()
