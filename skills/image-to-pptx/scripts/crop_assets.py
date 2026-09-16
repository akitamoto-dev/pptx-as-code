#!/usr/bin/env python3
# /// script
# dependencies = ["Pillow>=10"]
# ///
"""元画像から矩形領域を切り出してアセット PNG にする（正規アイコンで代用できない図版・写真向けの補助手段）。

白背景は既定で透過にし、白いスライドや薄い色のカードの上で馴染ませる。
autotrim を有効にすると、矩形は「広め」に取っておき、非白（実コンテンツ）の外接矩形を検出して
詰める。手動座標のずれでアイコンの端が途切れる問題を防げる。
トリム後の実際の矩形（元画像の px）を --map で JSON に書き出すので、pptx 側はその座標・サイズで
配置すれば位置が自動的に合う。

使い方:
    python3 crop_assets.py <元画像> <出力ディレクトリ> <rects> [--map <placement.json>]
        rects: JSON 文字列またはファイルパス
          [{"name": "icon1", "box": [x1, y1, x2, y2],
            "transparent": true, "threshold": 248,
            "autotrim": true, "pad": 6}, ...]

依存は Pillow だけ。`uv run crop_assets.py ...` なら自動で入る。
"""
import json
import os
import sys

from PIL import Image


def white_to_transparent(im, thr=248):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= thr and g >= thr and b >= thr:
                px[x, y] = (r, g, b, 0)
    return im


def content_bbox(im, thr=248):
    """非白（コンテンツ）画素の外接矩形を返す。無ければ None。"""
    rgb = im.convert("RGB")
    px = rgb.load()
    w, h = rgb.size
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if not (r >= thr and g >= thr and b >= thr):
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return None
    return (minx, miny, maxx + 1, maxy + 1)


def main():
    args = sys.argv[1:]
    map_out = None
    if "--map" in args:
        i = args.index("--map")
        map_out = args[i + 1]
        del args[i:i + 2]
    if len(args) < 3:
        sys.exit("使い方: crop_assets.py <元画像> <出力ディレクトリ> <rects> [--map <placement.json>]")
    src, out_dir, rects = args[0], args[1], args[2]
    spec = json.load(open(rects, encoding="utf-8")) if os.path.isfile(rects) else json.loads(rects)
    os.makedirs(out_dir, exist_ok=True)
    img = Image.open(src).convert("RGBA")
    placement = []
    for item in spec:
        name = item["name"]
        x1, y1, x2, y2 = item["box"]
        thr = item.get("threshold", 248)
        crop = img.crop((x1, y1, x2, y2))
        if item.get("autotrim", False):
            bb = content_bbox(crop, thr)
            if bb:
                pad = int(item.get("pad", 6))
                bx1 = max(0, bb[0] - pad)
                by1 = max(0, bb[1] - pad)
                bx2 = min(crop.width, bb[2] + pad)
                by2 = min(crop.height, bb[3] + pad)
                crop = crop.crop((bx1, by1, bx2, by2))
                ax1, ay1 = x1 + bx1, y1 + by1
                ax2, ay2 = x1 + bx2, y1 + by2
            else:
                ax1, ay1, ax2, ay2 = x1, y1, x2, y2
        else:
            ax1, ay1, ax2, ay2 = x1, y1, x2, y2
        if item.get("transparent", True):
            crop = white_to_transparent(crop, thr)
        crop.save(os.path.join(out_dir, f"{name}.png"))
        placement.append({"name": name, "box": [ax1, ay1, ax2, ay2],
                          "w": ax2 - ax1, "h": ay2 - ay1})
        print(f"{name}.png  {ax2 - ax1}x{ay2 - ay1}px (box={ax1},{ay1},{ax2},{ay2})")
    if map_out:
        with open(map_out, "w", encoding="utf-8") as f:
            json.dump(placement, f, ensure_ascii=False, indent=2)
        print(f"wrote {map_out}")
    print("done")


if __name__ == "__main__":
    main()
