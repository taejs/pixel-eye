# Pixel Eye · 원본 도트 복제기

원본 PNG/JPEG의 각 칸을 같은 좌표·색·투명도의 SVG 사각형으로 복제하는 픽셀 하네스 모듈입니다. 창작 에이전트와 분리되어 있고 모델을 호출하지 않습니다. 복제 후 각 픽셀을 다시 대조하고 불일치가 있으면 SVG를 발행하지 않습니다.

Export decoded PNG/JPEG pixels as editable SVG rectangles. The input is never resampled. The command reads an explicitly selected image and creates a new SVG, without overwriting existing output.

```sh
python -m pip install -r requirements.txt
python pixel_eye.py --root ./work original.png output.svg
python pixel_eye.py --root ./work --mode run --alpha omit-transparent original.png compact.svg
python pixel_eye.py --root ./work --origin 10 12 original.png positioned.svg
python verify_pixels.py --root ./work original.png output.svg
python -m unittest -v
```

Python 3.10+ and Pillow are required. Fixtures are generated entirely in the unit tests. The CLI accepts only relative paths under an existing `--root` (default: current directory); it rejects path traversal and symlinks that resolve outside that directory. The output folder must exist, and the filesystem must support hard links for no-overwrite publication. Run against a trusted working directory. Path resolution is not a sandbox against another process racing to change parent directories.

- `--mode rect`: one literal 1×1 SVG rectangle per cell. `--mode run`: merge only horizontally adjacent cells with identical decoded RGBA.
- `--alpha preserve` (default) retains RGB in the markup even for alpha-zero cells and encodes partial alpha via `fill-opacity`. `omit-transparent` skips only alpha-zero shapes. Renderers may premultiply and discard invisible RGB; file exactness is defined at the decoded RGBA-to-SVG geometry/attribute level, not a browser screenshot or physical display.
- `--origin X Y` sets viewBox origin and emitted integers. JPEG RGBA is defined by the current Pillow decoder's RGB values, not pre-compression values. No EXIF reorientation or ICC color conversion. Determinism is byte-for-byte for the same decoded cells and flags.
- Accepts only still PNG ≤8 bits/channel and JPEG that Pillow decodes into supported palette, luminance, or RGB-family modes. Corrupt, unknown, animated, and unsupported files fail. Both encoded size (32 MiB) and decoded area (1,048,576 pixels) are guarded; SVG is streamed using an on-disk temporary file. `--max-pixels` can lower the decoded limit.
- Treat image input and its rendered SVG as private unless the user owns the rights and explicitly chooses to share them. This tool contains no bundled art or fixtures from private uploads.

The verifier accepts the canonical row-major SVG subset emitted by Pixel Eye, not arbitrary SVG. It reports the first mismatching coordinate, missing or overlapping cells, or invalid geometry. This copies the supplied raster grid, including compression artifacts. It does not infer an underlying sprite grid, clean an outline, or create a different pose.
