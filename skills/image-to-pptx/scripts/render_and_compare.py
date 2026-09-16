#!/usr/bin/env python3
# /// script
# dependencies = ["Pillow>=10", "pymupdf>=1.24"]
# ///
"""pptx（または PDF）をページごとに PNG にし、任意で元画像と上下に並べた比較画像を作る。

レンダリング比較ループの中核。流れは LibreOffice で PDF 化 → PDF を PNG 化 → compare.png。
出力 PNG と元画像を見比べて崩れを特定し、生成スクリプトを直して再実行する。

使い方:
    python3 render_and_compare.py <pptx|pdf> <出力ディレクトリ> [--source <元画像>] [--page N] [--dpi 144]

出力:
    <出力ディレクトリ>/<名前>.pdf            pptx を渡したときだけ（PDF を渡せば変換を省く）
    <出力ディレクトリ>/render-001.png ...   全ページ。3 桁ゼロ埋め（ページ数に依存しない）
    <出力ディレクトリ>/compare.png          --source を渡したとき。元画像と --page（既定 1）を上下に並べる

道具の探し方:
    LibreOffice  環境変数 SOFFICE → PATH の soffice / soffice.com / libreoffice → OS 既定の導入先
    PDF → PNG    PyMuPDF（import pymupdf。旧名 fitz でも可）を優先し、無ければ pdftoppm
`uv run render_and_compare.py ...` なら Pillow と PyMuPDF が自動で入る。

LibreOffice のユーザープロファイルは <出力ディレクトリ>/.soffice-profile に分離する。既定のプロファイルを
共有したまま複数のセッションが同時に変換すると、片方が無言で失敗する（終了コード 1・PDF 未生成）。
"""
import argparse
import glob
import os
import pathlib
import platform
import shutil
import subprocess
import sys

# 比較画像のラベル描画に使うフォント。OS ごとの一般的な配置を順に試す。
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
    from PIL import ImageFont

    for p in font_paths():
        if not p:
            continue
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def find_soffice():
    """LibreOffice の実行ファイルを探す。環境変数 → PATH → OS 既定の導入先の順。無ければ None。"""
    env = os.environ.get("SOFFICE")
    if env and os.path.isfile(env):
        return env
    for name in ("soffice", "soffice.com", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    system = platform.system()
    if system == "Windows":
        roots = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        fixed = [os.path.join(r, "LibreOffice", "program", "soffice.com") for r in roots if r]
    elif system == "Darwin":
        fixed = ["/Applications/LibreOffice.app/Contents/MacOS/soffice"]
    else:
        fixed = ["/opt/libreoffice/program/soffice", "/usr/lib/libreoffice/program/soffice", "/snap/bin/libreoffice"]
    for p in fixed:
        if os.path.isfile(p):
            return p
    return None


def to_pdf(pptx, out_dir):
    """pptx を LibreOffice で PDF にし、PDF のパスを返す。"""
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice（soffice）が見つからない。環境変数 SOFFICE に実行ファイルのパスを設定する")
    profile = pathlib.Path(out_dir, ".soffice-profile").resolve().as_uri()
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(pptx))[0] + ".pdf")
    if os.path.exists(pdf):
        os.remove(pdf)
    r = subprocess.run(
        [soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf", "--outdir", out_dir, pptx],
        capture_output=True, text=True, timeout=300,
    )
    if not os.path.exists(pdf):
        raise RuntimeError("PDF 変換に失敗\n" + (r.stdout or "") + (r.stderr or ""))
    return pdf


def to_png(pdf, out_dir, dpi):
    """PDF を render-NNN.png にする。PyMuPDF を優先し、無ければ pdftoppm。(ページ数, エンジン名) を返す。"""
    for f in glob.glob(os.path.join(out_dir, "render-*.png")):
        os.remove(f)
    prefix = os.path.join(out_dir, "render")
    mupdf = None
    for mod in ("pymupdf", "fitz"):  # 新しい名前を先に試す（fitz は非推奨の別名）
        try:
            mupdf = __import__(mod)
            break
        except ImportError:
            continue
    if mupdf is not None:
        # LibreOffice が書く PDF の構造ツリーに対する警告（描画には影響しない）を抑える
        try:
            mupdf.TOOLS.mupdf_display_errors(False)
        except Exception:  # noqa: BLE001
            pass
        doc = mupdf.open(pdf)
        zoom = dpi / 72.0
        for i in range(doc.page_count):
            doc[i].get_pixmap(matrix=mupdf.Matrix(zoom, zoom)).save(f"{prefix}-{i + 1:03d}.png")
        return doc.page_count, "PyMuPDF"
    exe = shutil.which("pdftoppm")
    if not exe:
        raise RuntimeError("PyMuPDF も pdftoppm も無い。pip install pymupdf か poppler の導入が必要")
    subprocess.run([exe, "-png", "-r", str(dpi), pdf, prefix], check=True)
    # pdftoppm はページ数の桁で名前がぶれるため 3 桁に揃える
    n = 0
    for f in glob.glob(f"{prefix}-*.png"):
        stem = os.path.basename(f)[len("render") + 1:-4]
        if stem.isdigit():
            if len(stem) != 3:
                os.replace(f, f"{prefix}-{int(stem):03d}.png")
            n += 1
    return n, "pdftoppm"


def compare(source, page_png, out_path, page_no):
    """元画像とレンダリング結果を上下に並べた比較画像を書く。"""
    from PIL import Image, ImageDraw

    def fit(im, w=1200):
        return im.resize((w, int(im.height * w / im.width)))

    src = fit(Image.open(source).convert("RGB"))
    ren = fit(Image.open(page_png).convert("RGB"))
    gap = 46
    sheet = Image.new("RGB", (1200, src.height + ren.height + gap * 2), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    font = load_font(26)
    d.text((10, 8), "1) original image", fill=(200, 0, 0), font=font)
    sheet.paste(src, (0, gap))
    d.text((10, src.height + gap + 8), f"2) rendered pptx (page {page_no})", fill=(0, 120, 0), font=font)
    sheet.paste(ren, (0, src.height + gap * 2))
    sheet.save(out_path)


def main():
    ap = argparse.ArgumentParser(description="pptx をレンダリングして PNG 化し、元画像と比較する")
    ap.add_argument("input", help="pptx か PDF")
    ap.add_argument("out_dir")
    ap.add_argument("--source", default=None, help="元画像。--page のページと上下に並べた compare.png を出す")
    ap.add_argument("--page", type=int, default=1, help="比較対象のページ番号（1 始まり）")
    ap.add_argument("--dpi", type=int, default=144)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    if a.input.lower().endswith(".pdf"):
        pdf = a.input
        print(f"pdf: {pdf}（変換を省略）")
    else:
        pdf = to_pdf(a.input, a.out_dir)
        print(f"pdf: {pdf}")
    n, engine = to_png(pdf, a.out_dir, a.dpi)
    print(f"rendered: {n} ページ → {os.path.join(a.out_dir, 'render-NNN.png')}（{engine}, {a.dpi} dpi）")

    if a.source:
        page_png = os.path.join(a.out_dir, f"render-{a.page:03d}.png")
        if not os.path.exists(page_png):
            raise RuntimeError(f"ページ {a.page} のレンダリングが無い（全 {n} ページ）")
        out = os.path.join(a.out_dir, "compare.png")
        compare(a.source, page_png, out, a.page)
        print(f"compare: {out}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"render_and_compare.py: {e}", file=sys.stderr)
        sys.exit(1)
