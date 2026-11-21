from io import BytesIO, StringIO
import unittest

from PIL import Image
from exact_svg import ExportError, write_svg
from verify_pixels import verify

class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGBA", (4, 2))
        self.image.putdata([(41, 88, 172, 255)] * 2 + [(232, 138, 49, 128),
                           (16, 2, 1, 0), (41, 88, 172, 255), (7, 12, 29, 255),
                           (16, 2, 1, 0), (41, 88, 172, 255)])

    def svg(self, **options):
        buf = StringIO()
        write_svg(self.image, buf, origin=(-4, 9), **options)
        return buf.getvalue().encode()

    def check(self, raw, **options):
        return verify(self.image, BytesIO(raw), **options)

    def test_both_modes(self):
        for mode in ("rect", "run"):
            self.assertEqual(self.check(self.svg(mode=mode)),
                {"decoded_pixels":8, "matched_rect_cells":8,
                 "mismatches":0, "omitted_transparent_cells":0})

    def test_detect_one_color(self):
        with self.assertRaisesRegex(ExportError, r"differs at \(0, 0\)"):
            self.check(self.svg().replace(b"#2958ac", b"#2958ad", 1))

    def test_detect_one_alpha(self):
        with self.assertRaisesRegex(ExportError, r"differs at \(2, 0\)"):
            self.check(self.svg().replace(b"0.50196078431372548", b"1"))

    def test_detect_missing_or_overlap(self):
        lines = self.svg().splitlines(keepends=True)
        with self.assertRaisesRegex(ExportError, r"missing pixel at \(0, 0\)"):
            self.check(b"".join(lines[:1] + lines[2:]))
        with self.assertRaisesRegex(ExportError, r"overlap"):
            self.check(b"".join(lines[:2] + lines[1:]))

    def test_omit_is_explicit(self):
        raw = self.svg(mode="run", alpha="omit-transparent")
        with self.assertRaisesRegex(ExportError, r"missing pixel at \(3, 0\)"):
            self.check(raw)
        self.assertEqual(self.check(raw, preserve=False)["omitted_transparent_cells"], 2)

    def test_reject_unknown_grammar(self):
        with self.assertRaisesRegex(ExportError, r"invalid rectangle"):
            self.check(self.svg().replace(b"</svg>", b"<script/>\n</svg>"))
        with self.assertRaisesRegex(ExportError, r"unexpected data"):
            self.check(self.svg()+b"trailing")

    def test_integrated_copy_does_not_publish_failed_validation(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from exact_svg import export_file
        with TemporaryDirectory() as root:
            src, dst = Path(root)/"input.png", Path(root)/"output.svg"
            self.image.save(src)
            def reject(*args, **kwargs):
                raise ExportError("test injected discrepancy")
            with self.assertRaisesRegex(ExportError, "test injected"):
                export_file(src, dst, verifier=reject)
            self.assertFalse(dst.exists())
            self.assertEqual(sorted(p.name for p in Path(root).iterdir()), ["input.png"])
            export_file(src, dst, verifier=verify)
            with dst.open("rb") as svg:
                self.assertEqual(verify(self.image, svg)["mismatches"], 0)
