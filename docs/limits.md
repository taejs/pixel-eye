# Output contract and limits

## What is preserved?

Exactness is defined by **the original grid and the RGBA values decoded by Pillow**. JPEG and lossy WebP artifacts remain. The tool does not apply EXIF orientation or ICC color transforms.

- In `rect` mode, every cell has a 1×1 rectangle.
- In `run` mode, only consecutive cells with identical RGBA are merged, within one row.
- Default mode preserves the hidden RGB values of fully transparent cells. Use `--alpha omit-transparent` to skip them, and `--omit-transparent` when verifying that output.
- The independent checker accepts the canonical row-major SVG subset this tool emits, not arbitrary SVG. Display rendering is outside the contract; renderers may discard invisible RGB during premultiplication.

## Inputs and filesystem

Still PNG (at most 8 bits per channel), JPEG, and still WebP are accepted where the local Pillow build supports the codec. The limits are 32 MiB encoded and 4,194,304 decoded pixels. Large per-cell SVGs may be expensive to edit in a browser; try `run` for long flat rows.

The CLI only opens the selected local input. Supply relative paths inside a trusted working root. The output folder must already exist, and the filesystem must support hard links. The tool never overwrites a destination. Path checks are not a security boundary against another process changing parent directories concurrently.

This is a copier and verifier, not a retoucher, art generator, pose editor, or reconstruction tool.
