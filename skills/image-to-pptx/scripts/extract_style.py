#!/usr/bin/env python3
# /// script
# dependencies = ["Pillow>=10"]
# ///
"""参考画像（PNG/JPEG）から theme.json（schemaVersion 2）の草案とスウォッチ画像を作る。

「参考の書式だけを取り出して別の内容に適用する」ための道具。画素から分かるのは色と幾何だけなので、
出力はあくまで草案。値を確認し、サンプルを生成して参考画像と並べて（render_and_compare.py --source）
詰めてから使う。フォント名は画素からは復元できないため既定値を入れてある。

使い方:
    python3 extract_style.py <画像> <出力ディレクトリ> [<regions>] [--name <テーマ名>] [--colors 16]

    regions: 領域ごとの px 矩形 [x1, y1, x2, y2] を JSON 文字列かファイルで渡す（3 番目の位置引数でも --regions でも可）。
             省略すると上から順に帯を検出して title / keyMessage / body を当てる
      {"title": [60, 40, 1700, 120], "keyMessage": [60, 140, 1700, 230], "body": [60, 260, 1700, 960], "table": [...]}
    --colors: 領域ごとに量子化する色数（既定 16）

出力:
    <出力ディレクトリ>/theme-draft.json   theme.json の草案。既定テーマ（../../../template/deck-src/theme.json）が見つかれば
                                        それを土台にし、測れた値だけを上書きする（土台が無ければ最小構成）
    <出力ディレクトリ>/swatches.png       割り当てた色の見本（名前と 16 進値付き）
    標準出力                              領域ごとの支配色と、割り当てた色・幾何の表

方法:
    色   領域を Pillow の quantize（メディアンカット）で減色し、getcolors で頻度順に並べる。最頻色を背景、
         背景から十分離れた色を前景とし、近い色は 1 つにまとめる（アンチエイリアスの中間色を吸収する）。
         title 領域の背景が有彩色なら「色帯の上に白文字」とみなし、帯の色を primary にする
    幾何 px → inch は 幅 13.33 / 画像幅、px → pt は 540 / 画像高（16:9 のスライド高 7.5 inch = 540 pt）
         文字サイズは領域内の文字行（前景画素の行の帯）の高さから推定する。漢字はほぼ em の高さになる
"""
import argparse
import json
import os
import statistics
import sys

from PIL import Image, ImageDraw, ImageFont

DEFAULT_WIDTH_IN = 13.33
DEFAULT_HEIGHT_IN = 7.5
BUNDLED_THEME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "content-to-pptx", "template", "deck-src", "theme.json")

# 土台のテーマが無いときの最小構成。色は「未計測」を示すため既定の灰系を入れる（草案なので確認が前提）
MINIMAL_THEME = {
    "schemaVersion": 2,
    "name": "draft",
    "description": "",
    "layout": {"width": DEFAULT_WIDTH_IN, "height": DEFAULT_HEIGHT_IN, "left": 0.55, "contentWidth": 12.23, "contentBottom": 7.1},
    "fonts": {},
    "colors": {},
    "title": {},
    "keyMessage": {},
}
DEFAULT_FONTS = {
    "body": "Yu Gothic UI",
    "code": "Consolas",
    "fallback": {"body": ["Meiryo UI", "Noto Sans CJK JP", "Noto Sans JP"], "code": ["Cascadia Mono", "DejaVu Sans Mono"]},
}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
    "/mnt/c/Windows/Fonts/arialbd.ttf",
]


# ------------------------------------------------------------ 色の道具

def hexs(rgb):
    return "%02X%02X%02X" % tuple(int(v) for v in rgb[:3])


def dist(a, b):
    return sum((int(x) - int(y)) ** 2 for x, y in zip(a[:3], b[:3])) ** 0.5


def lum(rgb):
    r, g, b = rgb[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def sat(rgb):
    return max(rgb[:3]) - min(rgb[:3])


def is_chromatic(rgb):
    return sat(rgb) > 30


def darken(rgb, k=0.75):
    return tuple(int(v * k) for v in rgb[:3])


def blend_white(rgb, k):
    """k=0 で元の色、k=1 で白。"""
    return tuple(int(v + (255 - v) * k) for v in rgb[:3])


def hue_close(a, b):
    """色相が近いか（RGB の各成分の大小関係が同じで、正規化した差が小さい）。"""
    sa, sb = sat(a), sat(b)
    if sa < 30 or sb < 30:
        return False
    na = [(v - min(a[:3])) / sa for v in a[:3]]
    nb = [(v - min(b[:3])) / sb for v in b[:3]]
    return sum(abs(x - y) for x, y in zip(na, nb)) < 0.5


def dominant_colors(im, n_colors=16, merge_dist=28, min_share=0.002):
    """領域の支配色を (rgb, 画素数) の頻度順リストで返す。近い色は 1 つにまとめる。"""
    rgb = im.convert("RGB")
    q = rgb.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = q.getcolors(n_colors * 4) or []
    total = rgb.width * rgb.height
    raw = sorted(((c, tuple(pal[i * 3:i * 3 + 3])) for c, i in counts), reverse=True)
    merged = []  # [rgb, count]
    for c, col in raw:
        for m in merged:
            if dist(m[0], col) <= merge_dist:
                m[1] += c
                break
        else:
            merged.append([col, c])
    merged.sort(key=lambda m: -m[1])
    return [(tuple(col), c) for col, c in merged if c >= total * min_share]


def split_bg_fg(colors, fg_dist=60):
    """最頻色を背景、背景から離れた色を前景として返す。"""
    if not colors:
        return None, []
    bg = colors[0][0]
    fg = [(col, c) for col, c in colors[1:] if dist(col, bg) > fg_dist]
    return bg, fg


# ------------------------------------------------------------ 幾何の道具

def fg_mask_rows(im, bg, thr=60):
    """各行に前景画素があるかの真偽リストを返す（背景色との距離で判定）。"""
    rgb = im.convert("RGB")
    px = rgb.load()
    w, h = rgb.size
    rows = []
    for y in range(h):
        hit = False
        for x in range(0, w, 2):
            if dist(px[x, y], bg) > thr:
                hit = True
                break
        rows.append(hit)
    return rows


def bands(flags, min_h=2):
    """True が連続する区間を [(start, end)] で返す（end は排他）。"""
    out, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start >= min_h:
                out.append((start, i))
            start = None
    return out


def fg_bbox(im, bg, thr=60):
    """前景画素の外接矩形（領域内の相対 px）。無ければ None。"""
    rgb = im.convert("RGB")
    px = rgb.load()
    w, h = rgb.size
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if dist(px[x, y], bg) > thr:
                minx, maxx = min(minx, x), max(maxx, x)
                miny, maxy = min(miny, y), max(maxy, y)
    if maxx < 0:
        return None
    return (minx, miny, maxx + 1, maxy + 1)


def glyph_height(im, bg):
    """領域内の文字行の高さ（px）を推定する。行の帯の高さの中央値。"""
    bs = bands(fg_mask_rows(im, bg))
    if not bs:
        return None
    hs = sorted(e - s for s, e in bs)
    # 下線や罫線のような極端に低い帯を除く
    hs = [h for h in hs if h >= max(4, hs[-1] * 0.4)] or hs
    return statistics.median(hs)


def auto_regions(img, page_bg):
    """領域指定が無いとき、上から帯を検出して title / keyMessage / body を当てる。"""
    W, H = img.size
    bs = [b for b in bands(fg_mask_rows(img, page_bg), min_h=max(6, H // 120)) if b[0] < H * 0.6]
    regions = {}
    if bs:
        s, e = bs[0]
        regions["title"] = [0, s, W, e]
    if len(bs) > 1:
        s, e = bs[1]
        regions["keyMessage"] = [0, s, W, e]
    if len(bs) > 2:
        regions["body"] = [0, bs[2][0], W, int(H * 0.95)]
    elif "keyMessage" in regions:
        regions["body"] = [0, regions["keyMessage"][3], W, int(H * 0.95)]
    # 帯は全幅で取っているので、前景の外接矩形で左右を詰める
    for key in ("title", "keyMessage"):
        if key in regions:
            x1, y1, x2, y2 = regions[key]
            sub = img.crop((x1, y1, x2, y2))
            colors = dominant_colors(sub)
            bg, _ = split_bg_fg(colors)
            bb = fg_bbox(sub, bg or page_bg)
            if bb and dist(bg or page_bg, page_bg) <= 60:
                regions[key] = [x1 + bb[0], y1 + bb[1], x1 + bb[2], y1 + bb[3]]
    return regions


# ------------------------------------------------------------ 本体

def load_base_theme():
    if os.path.isfile(BUNDLED_THEME):
        with open(BUNDLED_THEME, encoding="utf-8") as f:
            return json.load(f), True
    return json.loads(json.dumps(MINIMAL_THEME)), False


def analyze(img, regions, n_colors):
    """領域ごとに背景・前景色と幾何を測る。"""
    W, H = img.size
    page_colors = dominant_colors(img, n_colors)
    page_bg, page_fg = split_bg_fg(page_colors)
    result = {"page": {"bg": page_bg, "fg": page_fg}}
    for key, box in regions.items():
        x1, y1, x2, y2 = [int(v) for v in box]
        sub = img.crop((x1, y1, x2, y2))
        colors = dominant_colors(sub, n_colors)
        bg, fg = split_bg_fg(colors)
        info = {"box": [x1, y1, x2, y2], "bg": bg, "fg": fg, "on_band": bool(bg) and dist(bg, page_bg) > 60}
        if bg is not None:
            gh = glyph_height(sub, bg)
            info["glyph_px"] = gh
            bb = fg_bbox(sub, bg)
            info["fg_bbox"] = [x1 + bb[0], y1 + bb[1], x1 + bb[2], y1 + bb[3]] if bb else None
        result[key] = info
    return result


def assign_colors(a):
    """測った色から theme の colors を組み立てる。値は (rgb, 由来) の辞書。"""
    page_bg = a["page"]["bg"]
    all_fg = list(a["page"]["fg"])
    for key in ("title", "keyMessage", "body", "table"):
        if key in a:
            all_fg += a[key]["fg"]
    chrom = sorted([c for c, _ in all_fg if is_chromatic(c)], key=lum)
    neutral = sorted([c for c, _ in all_fg if not is_chromatic(c)], key=lum)
    out = {}

    # primary: タイトルが色帯の上なら帯の色、そうでなければタイトル文字の色。無ければ最頻の有彩色
    t = a.get("title")
    if t and t["on_band"] and is_chromatic(t["bg"]):
        out["primary"] = (t["bg"], "title の帯の色")
    elif t and t["fg"]:
        out["primary"] = (t["fg"][0][0], "title の文字色")
    elif "table" in a and any(is_chromatic(c) for c, _ in a["table"]["fg"]):
        out["primary"] = (next(c for c, _ in a["table"]["fg"] if is_chromatic(c)), "table の塗り")
    elif chrom:
        out["primary"] = (chrom[0], "最も濃い有彩色")
    elif neutral:
        out["primary"] = (neutral[0], "最も濃い前景色（有彩色が無い）")
    else:
        out["primary"] = ((0, 120, 212), "既定（前景色を検出できない）")
    p = out["primary"][0]

    # primaryDark: primary と同系で暗い色があればそれ、無ければ primary を暗くする
    darker = [c for c in chrom if hue_close(c, p) and lum(c) < lum(p) - 20]
    out["primaryDark"] = (darker[0], "primary と同系の濃い色") if darker else (darken(p), "primary を 75% に暗くした導出値")

    # text: body の前景で最も濃い色（無彩色を優先。最頻色はカードの枠などの薄い色になりやすい）、
    #       無ければ最も濃い無彩色、それも無ければ既定
    b = a.get("body")
    if b and b["fg"] and not b["on_band"]:
        body_fg = [c for c, _ in b["fg"]]
        body_neutral = [c for c in body_fg if not is_chromatic(c)]
        out["text"] = (min(body_neutral or body_fg, key=lum), "body の前景で最も濃い色")
    elif neutral:
        out["text"] = (neutral[0], "最も濃い無彩色")
    else:
        out["text"] = ((51, 51, 51), "既定（無彩色の前景を検出できない）")
    tx = out["text"][0]

    # muted: text より明るく背景より暗い無彩色
    mids = [c for c in neutral if lum(tx) + 25 < lum(c) < lum(page_bg) - 60]
    out["muted"] = (mids[0], "text より薄い無彩色") if mids else ((102, 102, 102), "既定（薄い無彩色を検出できない）")

    # primaryLight / panel / panelLine: primary と同系の明るい色があればそれ、無ければ白との混色
    lights = sorted([c for c in chrom if hue_close(c, p) and lum(c) > 200], key=lambda c: -lum(c))
    out["primaryLight"] = (lights[0], "primary と同系の薄い色") if lights else (blend_white(p, 0.9), "primary を白に 90% 寄せた導出値")
    out["panel"] = (lights[0], "primary と同系の薄い色") if lights else (blend_white(p, 0.92), "primary を白に 92% 寄せた導出値")
    out["panelLine"] = (lights[-1], "primary と同系の薄い色（濃い方）") if len(lights) > 1 else (blend_white(p, 0.72), "primary を白に 72% 寄せた導出値")

    # rule: 薄い無彩色（罫線）
    rules = [c for c in neutral if lum(page_bg) - 60 <= lum(c) < lum(page_bg) - 15]
    out["rule"] = (rules[-1], "薄い無彩色") if rules else ((208, 208, 208), "既定（薄い無彩色を検出できない）")
    out["white"] = (page_bg if lum(page_bg) > 240 else (255, 255, 255), "ページの背景色" if lum(page_bg) > 240 else "既定")
    return out


def assign_geometry(a, W, H, width_in, height_in):
    """title / keyMessage の x, y, w, h（inch）と fontSize（pt）を推定する。

    x, y は前景（文字）の外接矩形の左上。w は文字の幅ではなく左右対称のコンテンツ幅（lib.js が
    自動縮小の判定に使うため）、h は外接矩形と 1 行分の行高の大きい方にする。文字の外接矩形そのものは
    text_bbox として返し、_measured に残す。
    """
    kx, ky = width_in / W, height_in / H
    pt = 540.0 / H
    out = {}
    for key in ("title", "keyMessage"):
        if key not in a:
            continue
        info = a[key]
        box = info.get("fg_bbox") or info["box"]
        x1, y1, x2, y2 = box
        x, y = round(x1 * kx, 2), round(y1 * ky, 2)
        geo = {"x": x, "y": y, "w": round(width_in - x * 2, 2), "h": round((y2 - y1) * ky, 2)}
        if info.get("glyph_px"):
            geo["fontSize"] = round(info["glyph_px"] * pt * 2) / 2  # 0.5pt 刻み
            geo["h"] = max(geo["h"], round(geo["fontSize"] * 1.4 / 72, 2))  # 1 行分の行高は確保する
        geo["text_bbox"] = {"x": x, "y": y, "w": round((x2 - x1) * kx, 2), "h": round((y2 - y1) * ky, 2)}
        out[key] = geo
    return out, kx, ky


def write_swatches(colors, path):
    """色見本を名前付きで並べた画像を書く。"""
    names = list(colors.keys())
    cell_w, cell_h, pad = 220, 120, 12
    cols = 4
    rows = (len(names) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell_w + pad, rows * cell_h + pad), (245, 245, 245))
    d = ImageDraw.Draw(im)
    font = None
    for p in FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(p, 16)
            break
        except Exception:  # noqa: BLE001
            continue
    font = font or ImageFont.load_default()
    for i, name in enumerate(names):
        rgb = colors[name][0]
        x = pad + (i % cols) * cell_w
        y = pad + (i // cols) * cell_h
        d.rectangle([x, y, x + cell_w - pad, y + cell_h - 44], fill=tuple(rgb), outline=(180, 180, 180))
        d.text((x + 4, y + cell_h - 40), name, fill=(30, 30, 30), font=font)
        d.text((x + 4, y + cell_h - 22), "#" + hexs(rgb), fill=(90, 90, 90), font=font)
    im.save(path)


def main():
    ap = argparse.ArgumentParser(description="参考画像から theme.json の草案とスウォッチを作る")
    ap.add_argument("image")
    ap.add_argument("out_dir")
    ap.add_argument("regions_pos", nargs="?", default=None, metavar="regions", help="領域の px 矩形（JSON 文字列かファイル）")
    ap.add_argument("--regions", default=None, help="regions と同じ（オプション形式）")
    ap.add_argument("--name", default="draft", help="テーマ名（theme.name）")
    ap.add_argument("--colors", type=int, default=16, help="領域ごとの量子化色数")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    img = Image.open(a.image).convert("RGB")
    W, H = img.size
    base, from_bundled = load_base_theme()
    width_in = base.get("layout", {}).get("width", DEFAULT_WIDTH_IN)
    height_in = base.get("layout", {}).get("height", DEFAULT_HEIGHT_IN)

    page_bg, _ = split_bg_fg(dominant_colors(img, a.colors))
    regions_arg = a.regions or a.regions_pos
    if regions_arg:
        regions = json.load(open(regions_arg, encoding="utf-8")) if os.path.isfile(regions_arg) else json.loads(regions_arg)
        source = "指定"
    else:
        regions = auto_regions(img, page_bg)
        source = "自動検出"
    measured = analyze(img, regions, a.colors)
    colors = assign_colors(measured)
    geometry, kx, ky = assign_geometry(measured, W, H, width_in, height_in)

    # ---- theme の組み立て ----
    theme = base
    theme["name"] = a.name
    notes = [
        f"extract_style.py が {os.path.basename(a.image)}（{W}x{H}px）から作った草案。色と幾何は画素からの推定値で、確認が必要",
        "fonts は画素からは復元できないので既定値を入れてある。確認が必要",
    ]
    if from_bundled:
        notes.append("測れなかった項目は既定テーマ theme.json の値のまま")
    else:
        notes.append("同梱テーマが見つからないため最小構成。lib.js で使うには不足する項目を補う")
    theme["description"] = "。".join(notes)
    theme.setdefault("fonts", {})
    for k, v in DEFAULT_FONTS.items():
        theme["fonts"].setdefault(k, v)
    theme.setdefault("colors", {})
    for k, (rgb, _) in colors.items():
        theme["colors"][k] = hexs(rgb)
    for key, geo in geometry.items():
        theme.setdefault(key, {})
        theme[key].update({k: v for k, v in geo.items() if k != "text_bbox"})
        if key == "title" and "fontSize" in geo:
            theme[key]["minFontSize"] = max(geo["fontSize"] - 4, 8)
    if "title" in geometry:
        left = geometry["title"]["x"]
        theme.setdefault("layout", {})
        theme["layout"].update({"width": width_in, "height": height_in, "left": left, "contentWidth": round(width_in - left * 2, 2)})
    theme["_measured"] = {
        "image": {"width": W, "height": H, "pxToInchX": round(kx, 5), "pxToInchY": round(ky, 5), "pxToPt": round(540.0 / H, 5)},
        "regions": {k: v["box"] for k, v in measured.items() if k != "page"},
        "textBbox": {k: g["text_bbox"] for k, g in geometry.items()},
        "regionSource": source,
        "dominant": {k: {"bg": hexs(v["bg"]) if v["bg"] else None, "fg": [hexs(c) for c, _ in v["fg"][:6]]} for k, v in measured.items()},
        "colorSource": {k: why for k, (_, why) in colors.items()},
    }

    out_json = os.path.join(a.out_dir, "theme-draft.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(theme, f, ensure_ascii=False, indent=2)
        f.write("\n")
    out_png = os.path.join(a.out_dir, "swatches.png")
    write_swatches(colors, out_png)

    # ---- 標準出力 ----
    if abs(kx - ky) / kx > 0.02:
        print(f"注意: 画像が {width_in}x{height_in} の比率ではない（x係数 {kx:.5f}, y係数 {ky:.5f}）。幾何は縦横で別係数で換算した")
    print(f"領域（{source}）:")
    print(f"  {'領域':<12}{'矩形 px':<28}{'背景':<9}{'前景（頻度順）'}")
    for k, v in measured.items():
        if k == "page":
            continue
        fg = " ".join(hexs(c) for c, _ in v["fg"][:5]) or "-"
        band = "（色帯）" if v["on_band"] else ""
        print(f"  {k:<12}{str(v['box']):<28}{hexs(v['bg']) if v['bg'] else '-':<9}{fg}{band}")
    print("色の割り当て:")
    print(f"  {'名前':<14}{'値':<9}由来")
    for k, (rgb, why) in colors.items():
        print(f"  {k:<14}{hexs(rgb):<9}{why}")
    print("幾何の推定（inch / pt。w はコンテンツ幅、文字の実測幅は textW）:")
    print(f"  {'要素':<12}{'x':>6}{'y':>6}{'w':>7}{'h':>6}{'fontSize':>10}{'textW':>8}")
    for k, g in geometry.items():
        print(f"  {k:<12}{g['x']:>6}{g['y']:>6}{g['w']:>7}{g['h']:>6}{str(g.get('fontSize', '-')):>10}{g['text_bbox']['w']:>8}")
    print(f"フォント: {theme['fonts']['body']} / {theme['fonts']['code']}（既定値。画素からは復元できないので確認する）")
    print(f"wrote {out_json}")
    print(f"wrote {out_png}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"extract_style.py: {e}", file=sys.stderr)
        sys.exit(1)
