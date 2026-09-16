#!/usr/bin/env python3
# /// script
# dependencies = ["Pillow>=10"]
# ///
"""元画像に座標グリッドを重ねた確認用画像を生成する。

要素分解の前処理。生成した画像を表示して各要素の px 矩形（x1, y1, x2, y2）を読み取ると、
目測よりも正確な座標が得られる。step ごとに細線、500px ごとに太線と座標ラベルを描く。

使い方:
    python3 grid_overlay.py <元画像> <出力画像> [step]      step の既定は 100

依存は Pillow だけ。`uv run grid_overlay.py ...` なら自動で入る。
座標ラベルのフォントは環境変数 SLIDE_FONT_PATH → fc-match → 既知のパスの順に探す。
"""
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

# 座標ラベルの描画に使うフォント。OS ごとの一般的な配置を順に試す。
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/mnt/c/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font_paths():
    """フォント候補を優先順に返す。環境変数 → fc-match → 既知のパスの順に試す。"""
    yield os.environ.get("SLIDE_FONT_PATH")
    if shutil.which("fc-match"):
        try:
            out = subprocess.run(
                ["fc-match", "-f", "%{file}", "sans-serif:lang=ja:weight=bold"],
                capture_output=True, text=True, timeout=5,
            )
            yield out.stdout.strip()
        except Exception:  # noqa: BLE001
            pass
    yield from FONT_CANDIDATES


def load_font(size):
    for p in font_paths():
        if not p:
            continue
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def main():
    if len(sys.argv) < 3:
        sys.exit("使い方: grid_overlay.py <元画像> <出力画像> [step]")
    src, dst = sys.argv[1], sys.argv[2]
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    img = Image.open(src).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)
    font = load_font(18)

    def color(v):
        return (255, 0, 0) if v % 500 == 0 else (0, 180, 255)

    def width(v):
        return 2 if v % 500 == 0 else 1

    for x in range(0, W, step):
        draw.line([(x, 0), (x, H)], fill=color(x), width=width(x))
        if x % 500 == 0:
            draw.text((x + 2, 2), str(x), fill=(255, 0, 0), font=font)
    for y in range(0, H, step):
        draw.line([(0, y), (W, y)], fill=color(y), width=width(y))
        if y % 500 == 0:
            draw.text((2, y + 2), str(y), fill=(255, 0, 0), font=font)

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    img.save(dst)
    print(f"saved {dst} ({W}x{H}, step={step})")


if __name__ == "__main__":
    main()
