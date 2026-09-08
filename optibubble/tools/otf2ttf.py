#!/usr/bin/env python3
"""
One-off converter: OPTIBubbleDoubleBold.otf (CFF outlines) → .ttf (TrueType).

ReportLab can only embed TrueType-outline fonts, so the wordmark OTF is
converted once and the .ttf is committed alongside the original.
Requires: pip install fonttools cu2qu
"""
import struct
import sys
from pathlib import Path

from cu2qu.pens import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

src = Path(sys.argv[1] if len(sys.argv) > 1 else
           "optibubble/fonts/OPTIBubbleDoubleBold.otf")
dst = src.with_suffix(".ttf")

font = TTFont(str(src))
glyph_order = font.getGlyphOrder()
cs = font["CFF "].cff.topDictIndex[0].CharStrings

glyf = newTable("glyf")
glyf.glyphOrder = glyph_order
glyf.glyphs = {}
for name in glyph_order:
    pen = TTGlyphPen(None)
    if name in cs and name != ".notdef":
        cs[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
    glyf.glyphs[name] = pen.glyph()

font["glyf"] = glyf
font["loca"] = newTable("loca")            # populated during compile
font["maxp"].numGlyphs = len(glyph_order)
font.tables.pop("CFF ", None)
font.sfntVersion = "\x00\x01\x00\x00"
font.save(str(dst))

# fontTools writes maxp version 0.5 (CFF-style); ReportLab wants 1.0 — patch it
data = bytearray(dst.read_bytes())
num_tables = struct.unpack(">H", data[4:6])[0]
for i in range(num_tables):
    off = 12 + 16 * i
    if bytes(data[off:off + 4]) == b"maxp":
        toff = struct.unpack(">I", data[off + 8:off + 12])[0]
        data[toff:toff + 4] = b"\x00\x01\x00\x00"
dst.write_bytes(bytes(data))
print(f"converted {src.name} → {dst.name}")
