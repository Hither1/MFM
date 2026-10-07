#!/usr/bin/env python3
"""One icon per skill-reuse probe task (cook_meat, coal_torches, iron_shield) and per
milestone those tasks add, cut from the Minecraft 1.16 assets inside the engine jar, as
build_rung_icons.py does for the dragon rungs.

    python scripts/build_probe_icons.py --jar <mcprec-6.13.jar> [--out figures/icons/minecraft]

Written at native size (16x16, the shield 22x22) and at 128x128 under 128px/, scaled by
whole pixels so the edges stay crisp, with a labelled contact sheet beside them.
"""
import argparse
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = "assets/minecraft/textures/"
OUT = Path(__file__).resolve().parent.parent / "figures" / "icons" / "minecraft"

# key -> (texture, crop box or None). The three tasks first, then alternates and the
# milestones that are not dragon rungs.
ICONS = {
    "cook_meat": ("item/cooked_beef.png", None),
    "coal_torches": ("block/torch.png", None),
    # The shield has no flat item texture: its model is a 12x22x1 plate at texOffs(0, 0),
    # whose front face is (1,1)-(13,23) of the entity sheet.
    "iron_shield": ("entity/shield_base_nopattern.png", (1, 1, 13, 23)),
    "cook_meat_alt_porkchop": ("item/cooked_porkchop.png", None),
    "coal_torches_alt_coal": ("item/coal.png", None),
    "mine_coal_ore": ("block/coal_ore.png", None),
    "cobblestone": ("block/cobblestone.png", None),
    # A cow's head is 8x8x6 at texOffs(0, 0): the front face is (6,6)-(14,14).
    "kill_animal": ("entity/cow/cow.png", (6, 6, 14, 14)),
}


def square(im: Image.Image) -> Image.Image:
    side = max(im.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", type=Path, required=True, help="mcprec jar holding the assets")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    big = args.out / "128px"
    big.mkdir(parents=True, exist_ok=True)
    tiles = []
    with zipfile.ZipFile(args.jar) as z:
        for key, (rel, box) in ICONS.items():
            im = Image.open(BytesIO(z.read(ROOT + rel))).convert("RGBA")
            if box:
                im = im.crop(box)
            im = square(im)
            im.save(args.out / f"{key}.png")
            scale = 128 // im.width
            up = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
            canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            canvas.paste(up, ((128 - up.width) // 2, (128 - up.height) // 2))
            canvas.save(big / f"{key}.png")
            tiles.append((key, canvas))
    cols, cell, pad, label = 4, 128, 16, 22
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * (cell + pad) + pad, rows * (cell + label + pad) + pad),
                      (255, 255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, (key, im) in enumerate(tiles):
        x = pad + (i % cols) * (cell + pad)
        y = pad + (i // cols) * (cell + label + pad)
        sheet.alpha_composite(im, (x, y))
        d.text((x, y + cell + 4), key, fill=(0, 0, 0, 255))
    sheet.save(args.out / "probe_icons_sheet.png")
    print(f"{len(tiles)} icons -> {args.out}")


if __name__ == "__main__":
    main()
