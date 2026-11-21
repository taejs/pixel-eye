"""Copy raster cells to a new SVG and verify them before writing the destination."""
from exact_svg import main
from verify_pixels import verify

if __name__ == "__main__":
    raise SystemExit(main(verifier=verify))
