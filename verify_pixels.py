"""Fail-closed verifier for the SVG subset emitted by Pixel Eye."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from exact_svg import ExportError, confined, load_rgba

INT = rb"(-?\d{1,11})"
SIZE = rb"([1-9]\d{0,6})"
HEADER = re.compile(
    rb'<svg xmlns="http://www.w3.org/2000/svg" width="' + SIZE +
    rb'" height="' + SIZE + rb'" viewBox="' + INT + rb" " + INT +
    rb" " + SIZE + rb" " + SIZE + rb'" shape-rendering="crispEdges">\n'
)
RECT = re.compile(
    rb'  <rect x="' + INT + rb'" y="' + INT + rb'" width="' + SIZE +
    rb'" height="1" fill="#([a-f0-9]{6})"(?: fill-opacity="([01](?:\.\d{1,30})?)")?/>\n'
)

def verify(image, svg, *, preserve=True):
    """Check every decoded cell in the canonical, row-major output subset."""
    head = HEADER.fullmatch(svg.readline(257))
    if head is None:
        raise ExportError("invalid Pixel Eye SVG header")
    width, height, x0, y0, vb_w, vb_h = map(int, head.groups())
    if (width, height) != image.size or (vb_w, vb_h) != image.size:
        raise ExportError("SVG dimensions differ from input")
    if max(abs(x0), abs(y0)) > 2_147_483_647:
        raise ExportError("invalid SVG origin")
    cursor = covered = 0
    total = width * height
    pixels = image.load()

    def check_gap(end):
        nonlocal cursor
        while cursor < end:
            x, y = cursor % width, cursor // width
            if preserve or pixels[x, y][3]:
                raise ExportError(f"missing pixel at ({x}, {y})")
            cursor += 1

    while True:
        line = svg.readline(257)
        if line == b"</svg>\n":
            check_gap(total)
            if svg.read(1):
                raise ExportError("unexpected data after SVG")
            return {"decoded_pixels": total, "matched_rect_cells": covered,
                    "omitted_transparent_cells": total - covered, "mismatches": 0}
        rect = RECT.fullmatch(line)
        if rect is None:
            raise ExportError("invalid rectangle or missing SVG end")
        x, y, run = map(int, rect.groups()[:3])
        x, y = x - x0, y - y0
        if not (0 <= x < width and 0 <= y < height and 1 <= run <= width - x):
            raise ExportError(f"rectangle outside image at ({x}, {y})")
        start = y * width + x
        if start < cursor:
            raise ExportError(f"overlap or out-of-order cell at ({x}, {y})")
        check_gap(start)
        alpha = float(rect[5]) if rect[5] is not None else 1.0
        a = round(alpha * 255)
        if not 0 <= a <= 255 or abs(alpha - a / 255) > 1e-15:
            raise ExportError(f"not an exact alpha byte at ({x}, {y})")
        rgba = tuple(bytes.fromhex(rect[4].decode("ascii"))) + (a,)
        for col in range(x, x + run):
            if pixels[col, y] != rgba:
                raise ExportError(f"pixel differs at ({col}, {y})")
        cursor += run
        covered += run


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("svg")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--omit-transparent", action="store_true")
    args = p.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        image = load_rgba(confined(root, args.input))
        with confined(root, args.svg).open("rb") as svg:
            result = verify(image, svg, preserve=not args.omit_transparent)
    except (ExportError, OSError, RuntimeError) as exc:
        print(f"pixel-eye: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
