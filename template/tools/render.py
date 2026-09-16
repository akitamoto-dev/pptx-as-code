#!/usr/bin/env python3
# /// script
# dependencies = ["pymupdf>=1.24"]
# ///
"""PDF をページごとに PNG にする。PyMuPDF があればそれを使い、無ければ pdftoppm を呼ぶ。

使い方: python3 render.py <pdf> <出力プレフィックス> [--dpi 110] [--pages 3-5]
出力:   <プレフィックス>-001.png のように 3 桁ゼロ埋めで書き出す（総ページ数に依存しない）

PyMuPDF は pip だけで入る（Windows でも wheel がある）。uv があれば `uv run render.py ...` で自動解決される。
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys


def parse_pages(spec, total):
    if not spec:
        return 1, total
    a, _, b = spec.partition("-")
    first = int(a)
    last = int(b) if b else first
    return max(1, first), min(total, last)


def with_pymupdf(pdf, prefix, dpi, pages):
    try:
        import pymupdf as fitz  # PyMuPDF の現在の名前
    except ImportError:
        import fitz  # 旧来の名前（1.28 以降は非推奨）

    # LibreOffice が書く PDF の構造ツリーに対する警告（描画には影響しない）を抑える
    fitz.TOOLS.mupdf_display_errors(False)
    doc = fitz.open(pdf)
    first, last = parse_pages(pages, doc.page_count)
    zoom = dpi / 72.0
    n = 0
    for i in range(first - 1, last):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        pix.save(f"{prefix}-{i + 1:03d}.png")
        n += 1
    return n, doc.page_count


def with_pdftoppm(pdf, prefix, dpi, pages):
    exe = shutil.which("pdftoppm")
    if not exe:
        raise RuntimeError("PyMuPDF も pdftoppm も無い。pip install pymupdf か poppler の導入が必要")
    cmd = [exe, "-png", "-r", str(dpi)]
    if pages:
        a, _, b = pages.partition("-")
        cmd += ["-f", a, "-l", b or a]
    subprocess.run(cmd + [pdf, prefix], check=True)
    n = 0
    for f in glob.glob(f"{prefix}-*.png"):
        stem = os.path.basename(f)[len(os.path.basename(prefix)) + 1 : -4]
        if stem.isdigit() and len(stem) != 3:
            os.replace(f, f"{prefix}-{int(stem):03d}.png")
        n += 1
    return n, None


def main():
    ap = argparse.ArgumentParser(description="PDF をページごとに PNG にする")
    ap.add_argument("pdf")
    ap.add_argument("prefix")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--pages", default=None, help="例: 3-5")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.prefix)), exist_ok=True)
    try:
        n, total = with_pymupdf(a.pdf, a.prefix, a.dpi, a.pages)
        engine = "PyMuPDF"
    except ImportError:
        n, total = with_pdftoppm(a.pdf, a.prefix, a.dpi, a.pages)
        engine = "pdftoppm"
    print(f"{n} ページを PNG 化（{engine}, {a.dpi} dpi" + (f", 全 {total} ページ" if total else "") + "）")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"render.py: {e}", file=sys.stderr)
        sys.exit(1)
