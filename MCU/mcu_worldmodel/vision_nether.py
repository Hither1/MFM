"""Frame detectors for the Nether stretch of the dragon chain: a fortress, a blaze.

Why a separate module. `vision.py` holds the ore, tree, screen and mob detectors that
every arm already runs; the two here are only ever asked for in the Nether, and both
are colour bands measured on THIS engine's frames in a staged scene, not read
off texture files:

- `fortress_fraction(frame)`: the share of the frame body that is nether-brick coloured,
  and the horizontal centre of that mass. Nether brick is a dark red-brown whose BLUE
  sits above its green (the texture averages ~(44, 22, 26)); netherrack, the ground
  everywhere in the Nether, is a brighter red-brown with green and blue EQUAL
  (~(97, 38, 38)), and so is a shaded netherrack pixel -- (b - g) / r is the band that
  separates them, red-over-blue by a wide margin separates both from blackstone
  (~(42, 35, 40), nearly grey), and a brightness cap separates them from lava and fire.
  A fortress is a MASS: corridors and pillars of hundreds of blocks, so the detector
  also needs one connected component of at least `FORTRESS_MIN_PX` pixels -- a crimson
  stem (whose shaded bark shares the band) is a thin column and never reaches it.
- `blaze_hint(frame)`: `vision.entity_hint(want="blaze")` cannot be trusted in the
  Nether, because its yellow-orange band is also LAVA's, and lava is everywhere a blaze
  is. A blaze carries its own negative: the dark grey rods that orbit its body. So a
  candidate blob in the blaze band is accepted only when the pixels inside its box
  include a grey (unsaturated, dark) share -- a lava pool's box holds bright orange and
  red-brown netherrack, neither of which is grey.

Both return coordinates in the full-frame convention `find_moving_blob` and
`entity_hint` use, so the fight loop steers on them without a branch.
"""
from __future__ import annotations

import numpy as np

from mcu_worldmodel import vision

#: Nether-brick colour band (see the module docstring); v is the max channel.
_NB_V_MIN, _NB_V_MAX = 18.0, 96.0
_NB_RB_LO, _NB_RB_HI = 0.22, 0.66     # (r - b) / r
_NB_RG_LO, _NB_RG_HI = 0.30, 0.75     # (r - g) / r
_NB_BG_MIN = 0.04                     # (b - g) / r  -- blue above green
#: A fortress in view: this share of the body, AND one component this big.
FORTRESS_FRAC_MIN = 0.012
FORTRESS_MIN_PX = 900
#: Horizontal degrees per pixel near the centre of a 640-wide frame (measured field of
#: view ~100 degrees; the same constant macros_entity aims with).
DEG_PER_PX = 0.213

#: Blaze body: YELLOW, measured on this engine (a probe, a blaze 3.5
#: blocks out at midday): (151, 112, 24) -- red 118+, green at ~0.74 of red, blue far
#: below both. `vision`'s blaze band asks for red > 160, which the shaded body never
#: reaches here, and it admits lava's ORANGE ((172, 72, 6): green at 0.42 of red);
#: the green-to-red window below is what separates the two.
_BZ_R_MIN = 118.0
_BZ_RB_MIN = 0.55                    # (r - b) / r
_BZ_RG_LO, _BZ_RG_HI = 0.05, 0.50    # (r - g) / r: yellow, not orange
_BZ_B_MAX = 110.0
_BZ_BR_MAX = 0.22                    # b / r per pixel: lava's yellow carries more blue
BLAZE_MAX_FRAC = 0.20
#: Three gates on a candidate, each measured on the probe frames (a blaze 3.5 and 7
#: blocks out vs a sunk lava pool at pitch 25) to separate the two on its
#: own: the blaze is TALLER than wide (0.67-0.83 vs a pool's 0.27-0.30), a quarter of
#: its box is the grey of its rods (0.22-0.42 vs 0.01-0.12 around a pool), and its
#: yellow has almost no blue (b/r 0.06-0.16 vs 0.20-0.25 for lava's yellow patches).
_BZ_AR_LO, _BZ_AR_HI = 0.5, 6.0
BLAZE_ROD_SHARE_MIN = 0.15
_BZ_BLUE_MED_MAX = 0.18
#: Coarse cell size (px) and the yellow share a cell needs to count as part of a blaze.
_BZ_CELL = 16
_BZ_CELL_MIN = 0.05
#: Blaze: the grey rods inside the blob's box. Saturation below this and brightness
#: in this window is "grey"; the box must hold at least this share of grey pixels.
_ROD_SAT_MAX = 0.32
_ROD_V_LO, _ROD_V_HI = 18.0, 130.0
BLAZE_MIN_PX = 60


def _split(frame: np.ndarray):
    f = np.asarray(frame)
    if f.ndim != 3:
        return None
    keep = vision._body_mask(f)
    body = f[: keep.shape[0]].astype(np.float32)
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    v = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    s = (v - mn) / np.maximum(v, 1.0)
    return keep, r, g, b, v, s


def nether_brick_mask(frame: np.ndarray) -> np.ndarray | None:
    parts = _split(frame)
    if parts is None:
        return None
    keep, r, g, b, v, s = parts
    rr = np.maximum(r, 1.0)
    m = ((v >= _NB_V_MIN) & (v <= _NB_V_MAX) & (r > g) & (r > b) & (b > g)
         & ((r - b) / rr >= _NB_RB_LO) & ((r - b) / rr <= _NB_RB_HI)
         & ((r - g) / rr >= _NB_RG_LO) & ((r - g) / rr <= _NB_RG_HI)
         & ((b - g) / rr >= _NB_BG_MIN))
    return vision._erode4(m & keep)


#: The largest component must be this wide (px) and no taller than this many times
#: its width: a fortress is walls and corridors, wide on screen; a crimson stem in the
#: same band is a column many times taller than wide.
FORTRESS_MIN_W = 20
FORTRESS_MAX_AR = 3.5


def fortress_fraction(frame: np.ndarray | None) -> tuple[float, int, float, int, int]:
    """(share of the body that is nether brick, largest component px, its centre x,
    its width, its height).

    The share is over the whole body so a wall filling the view reads ~1.0 and a
    corridor 30 blocks off reads a few percent; the component size is what says the
    mass is ONE thing and not scattered shaded pixels.
    """
    if frame is None:
        return (0.0, 0, 0.0, 0, 0)
    m = nether_brick_mask(frame)
    if m is None or not m.any():
        return (0.0, 0, 0.0, 0, 0)
    frac = float(m.mean())
    comps = vision._components(m)
    if not comps:
        return (frac, 0, 0.0, 0, 0)
    big = comps[0]
    return (frac, int(big["n"]), float(big["cx"]), int(big["w"]), int(big["h"]))


def fortress_in_view(frame: np.ndarray | None) -> tuple[float, float] | None:
    """(share, yaw offset in degrees to the mass's centre) when a fortress-sized
    nether-brick mass is in view, else None."""
    frac, n, cx, w, h = fortress_fraction(frame)
    if frac < FORTRESS_FRAC_MIN or n < FORTRESS_MIN_PX:
        return None
    if w < FORTRESS_MIN_W or h > FORTRESS_MAX_AR * max(w, 1):
        return None
    fw = np.asarray(frame).shape[1]
    return (frac, (cx - fw / 2.0) * DEG_PER_PX)


#: Enderman: near-black pixels (measured from the pit, a staged scene: the body renders
#: ~(20, 20, 20) against the sky), a tall blob. `vision.entity_hint` has the same
#: band but rejects any blob ringed by SKY as a cloud -- and from a 2-deep pit every
#: mob at the rim stands against the sky, so this one keeps the ring test (terrain
#: fills a ring, a mob leaves it empty) and drops the sky term.
_EN_V_MAX = 30.0
_EN_S_MAX = 0.40
EN_MIN_PX = 150
EN_MAX_FRAC = 0.30
_EN_AR_LO, _EN_AR_HI = 1.2, 9.0
#: Mean brightness (max channel) of the ring around the blob: sky ~200, lit
#: netherrack ~95, the inside of a shadowed pit ~30.
_EN_RING_V_MIN = 60.0


def enderman_hint(frame: np.ndarray | None, near: tuple[float, float] | None = None
                  ) -> tuple[str, int, int, int, int, int] | None:
    """("enderman", x, y, n_px, w, h) of the tallest near-black blob, or None."""
    parts = _split(frame)
    if parts is None:
        return None
    keep, r, g, b, v, s = parts
    raw = (v <= _EN_V_MAX) & (s <= _EN_S_MAX) & keep
    if not raw.any():
        return None
    area = float(keep.sum())
    if float(raw.sum()) / max(area, 1.0) > 0.55:
        return None                              # a dark cave, not a mob
    # Dilate, never erode: the limbs are 2-4 px wide at 2-3 blocks and an erosion
    # cuts the silhouette into a 66x69 torso (aspect 1.05, a staged scene) -- the
    # tallness that makes an enderman recognisable is in the pieces the erosion drops.
    mask = raw.copy()
    mask[1:, :] |= raw[:-1, :]
    mask[:-1, :] |= raw[1:, :]
    mask[:, 1:] |= raw[:, :-1]
    mask[:, :-1] |= raw[:, 1:]
    h, w = mask.shape
    anchor = near if near is not None else (w / 2.0, h / 2.0)
    best = None
    for c in vision._components(mask):
        if c["n"] < EN_MIN_PX:
            break
        if c["n"] / max(area, 1.0) > EN_MAX_FRAC or c["w"] < 4 or c["h"] < 12:
            continue
        ar = c["h"] / max(c["w"], 1.0)
        if ar < _EN_AR_LO or ar > _EN_AR_HI:
            continue
        ok, inner, ring = vision._isolated(mask, c, None)
        if not ok or inner < 0.25:
            continue
        # The ring around a mob is LIT (sky, or ground in the light); a dark patch of a
        # shadowed pit wall is ringed by more shadow (a staged scene: the fight loop
        # steered down into the pit chasing one).
        x0, y0 = int(c["x0"]), int(c["y0"])
        bw, bh = int(c["w"]), int(c["h"])
        grow = max(6, int(vision._RING_GROW * max(bw, bh)))
        X0, Y0 = max(0, x0 - grow), max(0, y0 - grow)
        X1, Y1 = min(w, x0 + bw + grow), min(h, y0 + bh + grow)
        outer = v[Y0:Y1, X0:X1]
        ring_v = ((float(outer.sum()) - float(v[y0:y0 + bh, x0:x0 + bw].sum()))
                  / max(1.0, float(outer.size - bw * bh)))
        if ring_v < _EN_RING_V_MIN:
            continue
        off = ((c["cx"] - anchor[0]) ** 2 + (c["cy"] - anchor[1]) ** 2) ** 0.5
        score = c["n"] * inner * (1.0 - ring) / (1.0 + off / 220.0)
        if best is None or score > best[0]:
            best = (score, c)
    if best is None:
        return None
    c = best[1]
    return ("enderman", int(round(c["cx"])), int(round(c["cy"])), int(c["n"]),
            int(c["w"]), int(c["h"]))


def blaze_hint(frame: np.ndarray | None, near: tuple[float, float] | None = None
               ) -> tuple[str, int, int, int, int, int] | None:
    """("blaze", x, y, n_px, w, h) of a blaze-coloured blob whose box also holds the
    grey of its rods, or None. Lava shares the colour and fails the rod test."""
    parts = _split(frame)
    if parts is None:
        return None
    keep, r, g, b, v, s = parts
    rr = np.maximum(r, 1.0)
    yellow = ((r >= _BZ_R_MIN) & ((r - b) / rr >= _BZ_RB_MIN)
              & ((r - g) / rr >= _BZ_RG_LO) & ((r - g) / rr <= _BZ_RG_HI) & (b < _BZ_B_MAX)
              & (b / rr <= _BZ_BR_MAX))
    mask = yellow & keep
    if not mask.any():
        return None
    # The yellow shows in SLIVERS between the rods (a blaze 3.5 blocks out is ~1,400
    # yellow pixels in a 90x200 column, no piece of it wider than a few pixels), so a
    # per-pixel component census finds nothing. Coarse cells instead: the share of
    # yellow per 16x16 cell, connected over cells, and the rod test on the box.
    h, w = mask.shape
    C = _BZ_CELL
    hc, wc = h // C, w // C
    dens = mask[:hc * C, :wc * C].reshape(hc, C, wc, C).mean(axis=(1, 3))
    cells = dens >= _BZ_CELL_MIN
    if not cells.any():
        return None
    area = float(keep.sum())
    grey = (s <= _ROD_SAT_MAX) & (v >= _ROD_V_LO) & (v <= _ROD_V_HI) & keep
    anchor = near if near is not None else (w / 2.0, h / 2.0)
    ys_all, xs_all = np.nonzero(mask)
    best = None
    for c in vision._components(cells):
        if c["n"] < 2:
            break
        x0, y0 = int(c["x0"]) * C, int(c["y0"]) * C
        bw, bh = int(c["w"]) * C, int(c["h"]) * C
        sel = (xs_all >= x0) & (xs_all < x0 + bw) & (ys_all >= y0) & (ys_all < y0 + bh)
        n = int(sel.sum())
        if n < BLAZE_MIN_PX or n / max(area, 1.0) > BLAZE_MAX_FRAC or bh < 20:
            continue
        ar = bh / max(bw, 1)
        if ar < _BZ_AR_LO or ar > _BZ_AR_HI:
            continue
        box = grey[y0:y0 + bh, x0:x0 + bw]
        share = float(box.mean()) if box.size else 0.0
        if share < BLAZE_ROD_SHARE_MIN:
            continue
        blue = float(np.median((b / rr)[ys_all[sel], xs_all[sel]]))
        if blue > _BZ_BLUE_MED_MAX:
            continue
        cx, cy = float(xs_all[sel].mean()), float(ys_all[sel].mean())
        off = ((cx - anchor[0]) ** 2 + (cy - anchor[1]) ** 2) ** 0.5
        score = n * (1.0 + share) / (1.0 + off / 220.0)
        if best is None or score > best[0]:
            best = (score, cx, cy, n, bw, bh)
    if best is None:
        return None
    _, cx, cy, n, bw, bh = best
    return ("blaze", int(round(cx)), int(round(cy)), n, bw, bh)
