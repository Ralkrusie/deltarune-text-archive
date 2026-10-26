"""Pixel geometry and repeatability of optional font conversion."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from font_woff import bitmap_rects, grid_for, solve_asc


class FontRulesTests(unittest.TestCase):
    def test_baseline_and_pixel_rectangles(self):
        self.assertEqual(solve_asc({ord('A'):[0,0,1,13],ord('中'):[0,0,1,16]}), 13)
        self.assertEqual(bitmap_rects([[1,1],[1,1]],2,2),[(0,0,2,2)])
        self.assertEqual([grid_for('fnt_main','zh')(ord(x)) for x in 'A中·'],[8,14,14])

    @unittest.skipUnless(all(importlib.util.find_spec(n) for n in ('PIL','fontTools','brotli')), 'optional requirements-assets.txt not installed')
    def test_conversion_geometry_and_identical_rebuild(self):
        from PIL import Image
        from fontTools.ttLib import TTFont
        from font_woff import build_font
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            Image.new('RGBA',(2,2),(255,255,255,255)).save(root/'fnt_main.png')
            csv=root/'glyphs.csv';csv.write_text('test;12;False;False;0;0;1;1\n65;0;0;2;2;3;0\n',encoding='utf-8')
            outputs=[root/'one.woff2', root/'two.woff2']
            for out in outputs:build_font(str(root/'fnt_main.png'),str(csv),str(out),'zh',grid=grid_for('fnt_main','zh'))
            self.assertEqual(outputs[0].read_bytes(),outputs[1].read_bytes())
            with TTFont(outputs[0]) as f:
                glyph=f.getBestCmap()[65]
                self.assertEqual(f['hmtx'][glyph][0],8*128)
                self.assertEqual(f['glyf'][glyph].numberOfContours,1)
