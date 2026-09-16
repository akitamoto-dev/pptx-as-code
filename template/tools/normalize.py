#!/usr/bin/env python3
"""生成した pptx を OOXML の規格に沿う形へ正規化する。PDF 変換の前に必ず通す。

PptxGenJS の出力には PowerPoint が「破損」と判定する規格違反が混じることがある。
LibreOffice・python-pptx・zip の CRC 検証はいずれも通過してしまうため、
**PDF レビューだけでは絶対に発覚しない**。PowerPoint で開いて初めて
「コンテンツに問題が見つかりました」と表示され、修復を押すと PowerPoint が落ちる。

正規化する内容:
  1. 負のサイズ（a:ext の cx/cy が負）→ 外接矩形を正の値にし flipH/flipV で向きを表す
     ※ これが開けなくなる直接の原因。右から左・下から上へ矢印を引くと発生する。
       見た目は変わらない（PDF の画素比較で確認済み）
  2. 同一スライド内で重複する図形 ID（cNvPr/@id）→ 未使用の値に振り直す
  3. [Content_Types].xml の実体のない Override → 削除
  4. zip のディレクトリエントリ → 削除し、[Content_Types].xml を先頭に配置
    5. 同一段落で重複する同内容の a:pPr → 先頭の1件だけを保持

注意: 負のサイズを含んでいても開けるファイルは存在する（閾値や組み合わせは不明）。
「他のファイルでは平気だった」を理由に無視せず、常に 0 件にしておくこと。

使い方:
    python3 normalize_pptx.py <ファイル名>.pptx      # その場で書き換える
    python3 normalize_pptx.py <ファイル名>.pptx --check   # 検査のみ（違反があれば終了コード 1）
"""
import collections
import os
import re
import sys
import zipfile
from xml.dom import minidom

SLIDE = re.compile(r"ppt/slides/slide\d+\.xml$")
XFRM = re.compile(r'<a:xfrm([^>]*)><a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(-?\d+)" cy="(-?\d+)"/>')
DRAWING_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/main"

LABEL = {
    "negative_extent": "負のサイズを反転指定に変換",
    "duplicate_id": "重複する図形 ID を振り直し",
    "phantom_override": "実体のない Override を削除",
    "directory_entry": "ディレクトリエントリを削除",
    "duplicate_paragraph_properties": "同一段落内の重複設定を削除",
}


def _toggle(attrs, name):
    """既に反転指定があれば打ち消す（二重反転を避ける）。"""
    if f'{name}="1"' in attrs:
        return attrs.replace(f' {name}="1"', "")
    return attrs + f' {name}="1"'


def fix_negative_extent(xml, stat):
    def repl(m):
        attrs, x, y, cx, cy = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        if cx >= 0 and cy >= 0:
            return m.group(0)
        if cx < 0:
            x, cx = x + cx, -cx
            attrs = _toggle(attrs, "flipH")
            stat["negative_extent"] += 1
        if cy < 0:
            y, cy = y + cy, -cy
            attrs = _toggle(attrs, "flipV")
            stat["negative_extent"] += 1
        return f'<a:xfrm{attrs}><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>'

    return XFRM.sub(repl, xml)


def fix_duplicate_ids(xml, stat):
    ids = [int(m.group(1)) for m in re.finditer(r'<p:cNvPr id="(\d+)"', xml)]
    if len(ids) == len(set(ids)):
        return xml
    seen, nxt, out, last = set(), max(ids) + 1, [], 0
    for m in re.finditer(r'<p:cNvPr id="(\d+)"', xml):
        v = int(m.group(1))
        if v in seen:
            out.append(xml[last:m.start()])
            out.append('<p:cNvPr id="%d"' % nxt)
            seen.add(nxt)
            nxt += 1
            stat["duplicate_id"] += 1
        else:
            out.append(xml[last:m.end()])
            seen.add(v)
        last = m.end()
    out.append(xml[last:])
    return "".join(out)


def fix_duplicate_paragraph_properties(xml, stat):
    document = minidom.parseString(xml)
    changed = False
    for paragraph in document.getElementsByTagNameNS(DRAWING_NAMESPACE, "p"):
        properties = [
            node for node in paragraph.childNodes
            if node.nodeType == node.ELEMENT_NODE
            and node.namespaceURI == DRAWING_NAMESPACE and node.localName == "pPr"
        ]
        if len(properties) < 2:
            continue
        if any(node.toxml() != properties[0].toxml() for node in properties[1:]):
            raise ValueError("同一段落に異なる段落設定が重複しているため、自動修正できない")
        for duplicate in properties[1:]:
            paragraph.removeChild(duplicate)
            stat["duplicate_paragraph_properties"] += 1
        changed = True
    result = document.toxml() if changed else xml
    document.unlink()
    return result


def normalize(path, check_only=False):
    stat = collections.Counter()
    src = zipfile.ZipFile(path)
    names = src.namelist()
    parts = {}

    for n in names:
        if not SLIDE.match(n):
            continue
        s = src.read(n).decode("utf-8")
        s2 = fix_duplicate_paragraph_properties(fix_duplicate_ids(fix_negative_extent(s, stat), stat), stat)
        if s2 != s:
            parts[n] = s2.encode("utf-8")

    present = set(n for n in names if not n.endswith("/"))
    ct = src.read("[Content_Types].xml").decode("utf-8")

    def keep_override(m):
        if m.group(1).lstrip("/") in present:
            return m.group(0)
        stat["phantom_override"] += 1
        return ""

    ct = re.sub(r'<Override PartName="([^"]+)"[^>]*/>', keep_override, ct)
    stat["directory_entry"] = sum(1 for i in src.infolist() if i.is_dir())

    if check_only:
        src.close()
        return stat

    tmp = path + ".tmp"
    out = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6)
    out.writestr("[Content_Types].xml", ct)          # OPC は Content_Types を先頭に置く
    for i in src.infolist():
        if i.is_dir() or i.filename == "[Content_Types].xml":
            continue
        out.writestr(i.filename, parts.get(i.filename, src.read(i.filename)), zipfile.ZIP_DEFLATED)
    out.close()
    src.close()
    os.replace(tmp, path)
    return stat


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("使い方: python3 normalize_pptx.py <ファイル名>.pptx [--check]")
    target = sys.argv[1]
    only_check = "--check" in sys.argv
    result = normalize(target, only_check)
    body = "／".join(f"{LABEL[k]} {result[k]}" for k in LABEL if result[k])
    if only_check:
        print("検査: " + (body or "規格違反なし"))
        sys.exit(1 if body else 0)
    print("正規化: " + (body or "修正なし"))
