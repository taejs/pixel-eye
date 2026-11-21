"""Lossless SVG serialization of decoder RGBA values, not color-managed rendering."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import groupby
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from typing import TextIO

from PIL import Image, UnidentifiedImageError

MAX_PIXELS = 4_194_304
MAX_IMAGE_BYTES = 32 * 1024 * 1024
FORMATS = ("PNG", "JPEG", "WEBP")
MODES = frozenset({"1", "L", "LA", "P", "RGB", "RGBA"})


class ExportError(ValueError):
    """Input or requested export violated the supported contract."""


@dataclass(frozen=True)
class ExportResult:
    width: int
    height: int
    rectangles: int
    omitted_transparent_cells: int


def load_rgba(path: Path, *, max_pixels: int = MAX_PIXELS):
    if not isinstance(max_pixels, int) or not 1 <= max_pixels <= MAX_PIXELS:
        raise ExportError(f"max_pixels must be within 1..{MAX_PIXELS}")
    try:
        if not path.is_file():
            raise ExportError("input must be a regular image file")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise ExportError(f"encoded image exceeds {MAX_IMAGE_BYTES} bytes")
        with path.open("rb") as raw:
            header = raw.read(26)
        if header.startswith(b"\x89PNG\r\n\x1a\n") and (len(header) < 26 or header[24] not in {1, 2, 4, 8}):
            raise ExportError("PNG must use at most 8 bits per channel")
        with Image.open(path, formats=FORMATS) as image:
            width, height = image.size
            if not width or not height or width * height > max_pixels:
                raise ExportError(f"image exceeds {max_pixels} decoded pixels")
            if image.mode not in MODES:
                raise ExportError(f"unsupported pixel mode: {image.mode}")
            if getattr(image, "is_animated", False) or getattr(image, "n_frames", 1) != 1:
                raise ExportError("animated or multi-frame images are not supported")
            return image.convert("RGBA")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise ExportError(f"could not decode supported PNG/JPEG/WebP input: {exc}") from exc


def write_svg(image, out: TextIO, *, mode: str = "rect", alpha: str = "preserve",
              origin: tuple[int, int] = (0, 0)) -> ExportResult:
    if mode not in ("rect", "run") or alpha not in ("preserve", "omit-transparent"):
        raise ExportError("unsupported rectangle mode or alpha policy")
    if image.mode != "RGBA":
        raise ExportError("write_svg expects decoded RGBA")
    if image.width * image.height > MAX_PIXELS or not image.width or not image.height:
        raise ExportError("invalid image dimensions")
    if len(origin) != 2 or any(type(n) is not int or abs(n) > 2_147_483_647 for n in origin):
        raise ExportError("origin coordinates must be signed integers within ±2147483647")
    x0, y0 = origin
    width, height = image.size
    out.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
              f'viewBox="{x0} {y0} {width} {height}" shape-rendering="crispEdges">\n')
    pixels = image.load()
    count, omitted = 0, 0
    for row in range(height):
        cols = ((1, pixels[x, row]) for x in range(width)) if mode == "rect" else (
            (sum(1 for _ in group), color)
            for color, group in groupby(pixels[x, row] for x in range(width)))
        x = x0
        for run, color in cols:
            r, g, b, a = color
            if alpha == "omit-transparent" and not a:
                omitted += run
            else:
                rgba = f' fill-opacity="{a / 255:.17g}"' if a != 255 else ""
                out.write(f'  <rect x="{x}" y="{y0 + row}" width="{run}" height="1" '
                          f'fill="#{r:02x}{g:02x}{b:02x}"{rgba}/>\n')
                count += 1
            x += run
    out.write('</svg>\n')
    return ExportResult(width, height, count, omitted)


def confined(root: Path, arg: str) -> Path:
    """Resolve a relative path, rejecting traversal and symlinks beyond root."""
    raw = Path(arg)
    if raw.is_absolute() or '..' in raw.parts:
        raise ExportError("use a relative path within --root (no '..')")
    try:
        target = (root / raw).resolve()
        target.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExportError("path could not be resolved within --root") from exc
    return target


def export_file(source: Path, target: Path, *, max_pixels: int = MAX_PIXELS, verifier=None, **options):
    if target.suffix.lower() != ".svg":
        raise ExportError("output name must end in .svg")
    if not target.parent.is_dir():
        raise ExportError("output folder must already exist")
    if target.exists():
        raise ExportError("output already exists; refusing to overwrite")
    image = load_rgba(source, max_pixels=max_pixels)
    tmp = None
    try:
        with NamedTemporaryFile(mode="w", encoding="ascii", newline="\n",
                                dir=target.parent, prefix=".pixel-svg-", delete=False) as f:
            tmp = Path(f.name)
            result = write_svg(image, f, **options)
        if verifier is not None:
            with tmp.open("rb") as proof:
                verifier(image, proof, preserve=options.get("alpha", "preserve") == "preserve")
        # Publish by hard-link, not replace: the destination cannot be overwritten even on a race.
        os.link(tmp, target)
        return result
    except OSError as exc:
        raise ExportError(f"output could not be created: {exc}") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main(argv=None, *, verifier=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="PNG/JPEG/WebP path relative to --root")
    p.add_argument("output", help="new .svg path relative to --root")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--mode", choices=("rect", "run"), default="rect")
    p.add_argument("--alpha", choices=("preserve", "omit-transparent"), default="preserve")
    p.add_argument("--origin", type=int, nargs=2, metavar=("X", "Y"), default=(0, 0))
    p.add_argument("--max-pixels", type=int, default=MAX_PIXELS)
    args = p.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ExportError("--root must be a directory")
        source, target = confined(root, args.input), confined(root, args.output)
        if (root / args.output).is_symlink():
            raise ExportError("output path must not be a symlink")
        result = export_file(source, target, max_pixels=args.max_pixels, mode=args.mode,
                             alpha=args.alpha, origin=tuple(args.origin), verifier=verifier)
    except (ExportError, OSError, RuntimeError) as exc:
        print(f"pixel-exact-svg: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.__dict__, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
