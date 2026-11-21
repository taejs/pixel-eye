from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from PIL import Image
from exact_svg import ExportError, MAX_IMAGE_BYTES, load_rgba, main, write_svg


def read_rects(payload, size):
    root = ET.fromstring(payload)
    x0, y0, w, h = map(int, root.attrib['viewBox'].split())
    assert (w, h) == tuple(size)
    cells, rects, widths = {}, 0, []
    for elem in root:
        a = elem.attrib
        assert int(a['height']) == 1
        alpha = round(float(a.get('fill-opacity', '1')) * 255)
        color = tuple(bytes.fromhex(a['fill'][1:])) + (alpha,)
        widths.append(int(a['width']))
        for i in range(int(a['width'])):
            key = (int(a['x']) - x0 + i, int(a['y']) - y0)
            assert key not in cells
            cells[key] = color
        rects += 1
    return cells, rects, widths


class ExactSVGTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'work'
        self.root.mkdir()
        self.input = self.root/'synth.png'
        self.rgba = [(17, 58, 99, 255), (17, 58, 99, 255), (12, 78, 30, 0),
                     (12, 78, 30, 0), (7, 72, 110, 127), (7, 72, 110, 1),
                     (127, 38, 220, 254), (0, 0, 0, 255), (14, 45, 111, 0),
                     (11, 21, 31, 0)]
        a = Image.new('RGBA', (5, 2))
        a.putdata(self.rgba)
        a.save(self.input)

    def cli(self, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['--root', str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def test_rect_and_run_exact_coords_and_png_rgba(self):
        for mode, expected_rects in [('rect', 10), ('run', 8)]:
            target = self.root/f'{mode}.svg'
            code, _, err = self.cli('--origin', '-4', '17', '--mode', mode, 'synth.png', target.name)
            self.assertEqual(code, 0, err)
            svg = target.read_text()
            self.assertIn('viewBox="-4 17 5 2"', svg)
            cells, count, widths = read_rects(svg, (5, 2))
            self.assertEqual([cells[(x, y)] for y in range(2) for x in range(5)], self.rgba)
            self.assertEqual(count, expected_rects)
            if mode == 'rect':
                self.assertEqual(set(widths), {1})

    def test_preserve_every_alpha_byte(self):
        fixture = Image.new('RGBA', (256, 1))
        fixture.putdata([(101, 21, 73, i) for i in range(256)])
        out = StringIO()
        write_svg(fixture, out)
        cells, _, _ = read_rects(out.getvalue(), (256, 1))
        self.assertEqual([cells[(i, 0)] for i in range(256)],
                         [(101, 21, 73, i) for i in range(256)])

    def test_omit_transparent_while_preserving_partial(self):
        code, message, err = self.cli('--mode', 'run', '--alpha', 'omit-transparent', 'synth.png', 'out.svg')
        self.assertEqual(code, 0, err)
        self.assertIn('"omitted_transparent_cells": 4', message)
        actual, _, _ = read_rects((self.root/'out.svg').read_text(), (5, 2))
        expected = {(i % 5, i // 5): c for i, c in enumerate(self.rgba) if c[3]}
        self.assertEqual(actual, expected)

    def test_jpeg_against_decoder_not_source_before_compression(self):
        f = self.root/'test.jpg'
        Image.new('RGB', (3, 4), '#b456ca').save(f, quality=84)
        with Image.open(f) as a:
            expected = [a.convert('RGBA').getpixel((x, y)) for y in range(4) for x in range(3)]
        code, _, err = self.cli('test.jpg', 'out.svg')
        self.assertEqual(code, 0, err)
        cells, _, _ = read_rects((self.root/'out.svg').read_text(), (3, 4))
        self.assertEqual([cells[(x, y)] for y in range(4) for x in range(3)], expected)

    def test_zero_external_changes_for_traversal_absolute_and_symlinks(self):
        outside = self.root.parent/'outside.png'
        outside.write_bytes(self.input.read_bytes())
        (self.root/'link.png').symlink_to(outside)
        (self.root/'external').symlink_to(self.root.parent, target_is_directory=True)
        (self.root/'dangling.svg').symlink_to(self.root/'new.svg')
        for src, dst in [('synth.png', '../elsewhere.svg'), (str(outside), 'out.svg'),
                         ('link.png', 'out.svg'), ('synth.png', 'external/out.svg'),
                         ('synth.png', 'dangling.svg')]:
            self.assertEqual(self.cli(src, dst)[0], 2, (src, dst))
        self.assertFalse((outside.parent/'elsewhere.svg').exists())
        self.assertFalse((outside.parent/'out.svg').exists())
        self.assertFalse((self.root/'new.svg').exists())

    def test_guards_non_image_disallowed_and_oversized(self):
        (self.root/'unknown.png').write_bytes(b'not image bytes')
        (self.root/'truncated.png').write_bytes(self.input.read_bytes()[:40])
        Image.new('RGB', (2, 2)).save(self.root/'disallowed.gif')
        Image.new('I;16', (2, 2)).save(self.root/'16bit.png')
        with (self.root/'huge.png').open('wb') as f:
            f.truncate(MAX_IMAGE_BYTES + 1)
        for path in ('unknown.png', 'truncated.png', 'disallowed.gif', '16bit.png', 'huge.png'):
            with self.subTest(path=path):
                self.assertEqual(self.cli(path, 'out.svg')[0], 2)
                self.assertFalse((self.root/'out.svg').exists())
        self.assertEqual(self.cli('--max-pixels', '9', 'synth.png', 'out.svg')[0], 2)
        self.assertFalse((self.root/'out.svg').exists())

    def test_palette_transparency_and_animated_png_rejection(self):
        palette = Image.new('P', (2, 1))
        palette.putpalette([3, 5, 7, 11, 13, 17] + [0] * 762)
        palette.putdata([0, 1])
        palette.save(self.root/'palette.png', transparency=bytes([0, 120]))
        self.assertEqual(self.cli('palette.png', 'out.svg')[0], 0)
        cells, _, _ = read_rects((self.root/'out.svg').read_text(), (2, 1))
        self.assertEqual(cells, {(0, 0): (3, 5, 7, 0), (1, 0): (11, 13, 17, 120)})
        a = Image.new('RGBA', (2, 1), 'black')
        a.save(self.root/'animated.png', save_all=True,
               append_images=[Image.new('RGBA', (2, 1), 'white')], duration=100)
        code, _, err = self.cli('animated.png', 'animation.svg')
        self.assertEqual(code, 2, err)
        self.assertIn('animated', err)
        self.assertFalse((self.root/'animation.svg').exists())

    def test_determinism_refuse_overwrite_and_no_temp_left(self):
        for name in ('one.svg', 'two.svg'):
            self.assertEqual(self.cli('--mode', 'run', 'synth.png', name)[0], 0)
        one, two = self.root/'one.svg', self.root/'two.svg'
        self.assertEqual(one.read_bytes(), two.read_bytes())
        one.write_bytes(b'user data')
        self.assertEqual(self.cli('synth.png', 'one.svg')[0], 2)
        self.assertEqual(one.read_bytes(), b'user data')
        self.assertEqual(list(self.root.glob('.pixel-svg-*')), [])
