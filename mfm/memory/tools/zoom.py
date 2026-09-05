#!/usr/bin/env python
"""Crop a region of a saved frame and magnify it, for reading detail a full frame hides.

    ./tools/zoom.py <frame.png> <x> <y> <w> <h> [out.png]

x,y = top-left of the region in the frame's own pixels; the crop is scaled 4x
nearest-neighbour (pixel-accurate, no smoothing) into out.png (default ./zoom.png).
Then open the result with view_image. Compare two frames by zooming the same region in
both and viewing them in sequence.
"""
import sys


def main(argv):
    if len(argv) < 6:
        print(__doc__.strip())
        return 2
    try:
        from PIL import Image
    except ImportError:
        print("zoom.py needs Pillow; run it as `python tools/zoom.py ...` (the sandbox's "
              "`python` has it)", file=sys.stderr)
        return 1
    frame, x, y, w, h = argv[1], *map(int, argv[2:6])
    out = argv[6] if len(argv) > 6 else "zoom.png"
    img = Image.open(frame).convert("RGB")
    x = max(0, min(img.width - 1, x))
    y = max(0, min(img.height - 1, y))
    w = max(1, min(img.width - x, w))
    h = max(1, min(img.height - y, h))
    img.crop((x, y, x + w, y + h)).resize((w * 4, h * 4), Image.NEAREST).save(out)
    print(f"wrote {out}: {w}x{h} region at ({x},{y}) of {img.width}x{img.height}, 4x")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
