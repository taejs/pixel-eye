# Contributing to Pixelify Anything

Pixelify Anything is a local raster-to-SVG copier with a separate verifier. Keep changes within the [output contract](docs/limits.md) unless a new contract is explicitly discussed.

## Run the tests

Use Python 3.10 or later, in a virtual environment:

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest -v
```

For encoder or verifier changes, cover both a passing and a failing case. Check coordinates, alpha, run boundaries, and existing-file preservation as applicable.

## Report a bug or propose a change

- Include OS, Python and Pillow versions, the exact command, and expected versus actual output. For a mismatch, include the first affected coordinate and RGBA.
- Use a small, self-authored image to reproduce the problem. Do not attach private or third-party images, derived SVGs, or sensitive logs.
- Keep one change per PR. Include tests and flag changes to verification behavior, the format contract, or network access.
- The repository does not yet include an explicit license. This guide does not itself grant rights to use, distribute, or relicense the code or assets.

## Reproduce a one-pixel failure

This creates a 2×1 image, checks the original SVG, then changes one pixel. Use macOS or Linux shell commands:

```sh
WORK=$(mktemp -d)
python - "$WORK" <<'PY'
from pathlib import Path
import sys
from PIL import Image
root = Path(sys.argv[1])
im = Image.new("RGBA", (2, 1), (48, 112, 208, 255))
im.putpixel((1, 0), (240, 192, 48, 255))
im.save(root / "fixture.png")
PY
python pixel_eye.py --root "$WORK" fixture.png good.svg
python verify_pixels.py --root "$WORK" fixture.png good.svg
python - "$WORK" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
svg = (root / "good.svg").read_text()
assert svg.count("#f0c030") == 1
(root / "bad.svg").write_text(svg.replace("#f0c030", "#f0c031"))
PY
python verify_pixels.py --root "$WORK" fixture.png bad.svg
```

The last command must report `pixel differs at (1, 0)` and exit with code 2.

Structure references: [GitHub contributor guidelines](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors) and [Pillow test instructions](https://github.com/python-pillow/Pillow/blob/main/Tests/README.rst).
