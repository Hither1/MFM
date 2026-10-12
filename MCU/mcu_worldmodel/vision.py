"""Find the GUI cursor in the frame, so the tracked position can be measured, not summed.

Why this exists. `CursorState` dead-reckons: it sums the camera deltas the runner emits at
4.17 px/degree. Run one run measured what that is worth over a long GUI session -- after
~50 one-tick nudges the tracked position read container (-29.5, 90.0), off the left edge
of the screen, while the rendered arrow sat 11 px above hotbar slot 0 (container ~(24,
147)). Sixty pixels of drift is three slots; every absolute address computed from it was a
miss, and the agent fell back to reading the frame by eye and correcting one click per
model turn. The game moves the pointer in integer pixels and the scale constant is an
endpoint fit, so the error per move is small and the sum is unbounded. The fix is not a
better constant: it is measuring the pointer in the frame the environment already sends
every tick, and overwriting the sum with the measurement.

How it measures. The arrow sprite is opaque: a black outline at value 0-4 and a white body
at 250-255, drawn over anything (verified over a grey panel, over a dark log icon, and
over a held stack -- the arrow stays on top). So a pixel the sprite covers is dark or
bright *regardless of the scene*, and matching needs no template image at all: score a
position by how many outline pixels are dark (< 70 mean) and body pixels are bright
(> 235 mean), take the argmax. The two thresholds straddle the GUI greys (~139-204), which
is what makes the sprite separable from the panel it floats over. An all-white region
matches the body trivially but scores zero on the outline, and the acceptance floor on
outline hits is what rejects it.

The sprite below was read out of a live frame (one run step 1929, arrow over the plain
panel at (358, 141)), classifying each pixel against those thresholds and keeping bright
pixels only where the same row has outline on both sides -- that enclosure test is what
kept the panel's own white bevel, which crosses the sprite's bounding box, out of the
mask. Tip of the arrow = the hotspot the game clicks with = offset (0, 0).
"""
from __future__ import annotations

import numpy as np

#: 'B' must be dark, 'W' must be bright, '.' is not part of the sprite (background shows
#: through around the arrow and between the tail barbs; those pixels prove nothing).
_SPRITE = """\
B.........
BB........
BWB.......
BWWB......
BWWWB.....
BWWWWB....
BWWWWWB...
BWWWWWWB..
BWWWWWWWB.
BWWWWWWWWB
BWWWWWBBBB
BWWWWWB...
BWBBWWB...
BB.BWWWB..
B...BWWB..
.....BBB..
"""

DARK_MAX = 70.0
BRIGHT_MIN = 235.0

_ROWS = _SPRITE.strip("\n").split("\n")
BLACK = [(dy, dx) for dy, r in enumerate(_ROWS) for dx, c in enumerate(r) if c == "B"]
WHITE = [(dy, dx) for dy, r in enumerate(_ROWS) for dx, c in enumerate(r) if c == "W"]
_H = len(_ROWS)
_W = max(len(r) for r in _ROWS)

#: Acceptance: nearly the whole sprite must agree, and the outline on its own must be
#: mostly present. JPEG ringing at the black/white boundary eats a few pixels per frame
#: (the wire format is JPEG; the thresholds sit far from the greys precisely so ringing
#: falls in the dead zone), so the floors are below 1.0 but not far below.
MIN_TOTAL = 0.85
MIN_BLACK = 0.60


def find_cursor(frame: np.ndarray) -> tuple[int, int] | None:
    """Screen (x, y) of the arrow tip, or None when no confident hit exists.

    Channel order does not matter -- the sprite is black-and-white and the test is on the
    channel mean. A frame that is not 360x640 is not resized here: the caller's container
    geometry is in 640x360 render coordinates, so a mismatched frame is a configuration
    error to surface, not to paper over.
    """
    if frame is None or frame.ndim != 3 or frame.shape[0] < _H or frame.shape[1] < _W:
        return None
    lum = frame.mean(axis=2, dtype=np.float32)
    # Pad with a value in neither class, so a sprite hanging off the bottom or right edge
    # (the pointer clamps at the window edge, not the container edge, and runs park it
    # over the HUD hotbar) can still match on its visible part. The acceptance floors are
    # divided by the full mask size, so a clip costs score and a mostly-hidden arrow still
    # fails -- which is right, there is not enough sprite left to trust.
    lum = np.pad(lum, ((0, _H - 1), (0, _W - 1)), constant_values=128.0)
    dark = lum < DARK_MAX
    bright = lum > BRIGHT_MIN
    h = frame.shape[0]
    w = frame.shape[1]
    score_b = np.zeros((h, w), dtype=np.int16)
    score_w = np.zeros((h, w), dtype=np.int16)
    for dy, dx in BLACK:
        score_b += dark[dy:dy + h, dx:dx + w]
    for dy, dx in WHITE:
        score_w += bright[dy:dy + h, dx:dx + w]
    total = score_b + score_w
    idx = int(total.argmax())
    y, x = divmod(idx, w)
    if (total[y, x] < MIN_TOTAL * (len(BLACK) + len(WHITE))
            or score_b[y, x] < MIN_BLACK * len(BLACK)):
        return None
    return (x, y)


# -- ore sighting ---------------------------------------------------------

#: Iron-ore speckles, as colour RATIOS, because absolute values do not survive block
#: shading (a side face renders at ~0.8x, a bottom at 0.5x; ratios are invariant under
#: that multiply). Measured from the game's own texture (mcprec-6.13.jar,
#: block/iron_ore.png): speckle pixels (188,153,128) and (216,175,147) both give
#: (R-B)/R = 0.319 and (R-G)/R = 0.186-0.190. The nearest confusable underground block
#: is dirt at (R-B)/R = 0.503, (R-G)/R = 0.281 -- outside both bands. Stone and coal ore
#: have no tan at all.
_ORE_RB_LO, _ORE_RB_HI = 0.28, 0.36
_ORE_RG_LO, _ORE_RG_HI = 0.15, 0.22
#: Local-contrast gate, replacing the old absolute `r > 150`. One run strip-mined for
#: ~7,700 steps without one sighting; its tunnel frames measured mean r 60.7 and 95th
#: percentile 68 -- the absolute gate made ore literally undetectable underground, where
#: all the ore is. The ratio bands are shading-invariant; brightness is judged against
#: a 33px local mean instead (speckles are brighter than the stone AROUND them at any
#: light level), with a floor for near-black noise.
_ORE_CONTRAST = 1.35
#: 38 admitted near-black scenes where nothing is verifiable: one run parked beside
#: a dark dirt face (mask mean r=43) and would have flagged it 7 times; ked_final1's
#: own world model records r~40 frames as "too dark to classify side-wall textures".
#: A sighting the model cannot confirm in a zoom is pure interruption cost, and the
#: torch doctrine means actionable ore is lit (r>=60). Still far below the old r>150
#: absolute gate that blinded one run's tunnels.
_ORE_FLOOR = 48.0
_ORE_MIN_CLUSTER = 12
#: Speckles are INTRA-block texture: many tiny blobs on a grey base. The two false-
#: positive families the corpus scan surfaced (306 underground frames) are
#: both block-scale tan -- sunlit dirt/villagers (dense fields) and dirt clumps beside
#: stone (few large blobs on a brown base). Hence: window density cap, blob-scale
#: bounds, and a grey-base majority requirement.
_ORE_MAX_DENSITY = 0.35
#: Blob bounds admit the whole approach: a far wall renders speckles at 2-6px, a face
#: one block away renders them at 10-15px a side. The cap only excludes single
#: block-scale masses (a dirt clump is ONE blob of hundreds of px).
_ORE_MIN_BLOBS = 3
_ORE_MAX_BLOB = 150
_ORE_MED_BLOB = 60
_ORE_GREY_SAT = 0.14
_ORE_GREY_FRAC = 0.55


def _local_mean(x: np.ndarray, k: int) -> np.ndarray:
    """Box-filtered local mean with edge padding, via an integral image."""
    pad = k // 2
    ii = np.pad(x.astype(np.float32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    h, w = x.shape
    ys = np.clip(np.arange(h) - pad, 0, h); ye = np.clip(np.arange(h) + pad + 1, 0, h)
    xs = np.clip(np.arange(w) - pad, 0, w); xe = np.clip(np.arange(w) + pad + 1, 0, w)
    s = ii[ye][:, xe] - ii[ye][:, xs] - ii[ys][:, xe] + ii[ys][:, xs]
    return s / ((ye - ys)[:, None] * (xe - xs)[None, :])


def _blob_sizes(window: np.ndarray) -> list[int]:
    """Connected-component sizes (4-neighbour) of a small boolean window."""
    from collections import deque
    seen = np.zeros_like(window, dtype=bool)
    sizes: list[int] = []
    h, w = window.shape
    for i in range(h):
        for j in range(w):
            if window[i, j] and not seen[i, j]:
                q = deque([(i, j)]); seen[i, j] = True; s = 0
                while q:
                    y, x = q.popleft(); s += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and window[ny, nx]                                 and not seen[ny, nx]:
                            seen[ny, nx] = True; q.append((ny, nx))
                sizes.append(s)
    return sizes


#: Lava colour, from the frames of three runs that met it:
#: r 140-220 with g/r ~0.42 and b/r 0.03-0.15. A crafting-table top is the nearest
#: look-alike (g/r 0.49, b/r 0.27) and a torch flame the other (b/r 0.00), so the
#: band is closed on both sides. Fractions measured over the lower 65% of the frame
#: minus the hotbar and the held-item corner: distant lava 0.010-0.019, a lava lake
#: ahead 0.03-0.2, standing in it 0.2-0.4; 500 surface frames and every archived
#: underground frame without lava read 0.000-0.002.
_LAVA_R_MIN = 130.0
_LAVA_GR = (0.30, 0.50)
_LAVA_BR = (0.02, 0.18)
LAVA_FRAC_MIN = 0.010


#: The burning overlay: flames drawn over the lower half of the view while the avatar
#: is on fire (or in lava). Brighter and yellower than lava's band: r >= 150, g/r
#: 0.35-0.80, b/r <= 0.30, measured over the lower 45% of the frame minus the hotbar box
#: (bottom 10%, middle 46%) and the held-item corner (bottom 30%, right 25%). Measured
#: one run's burning frames 0.41-0.50, a staged scene's burning frames in a 1x1
#: lava pit 0.20-0.30 (the chat overlay hides part of the flames), the same avatar one
#: hit earlier with no flames yet 0.000, 138 ordinary frames of five arms max 0.001.
#: The band is lava's too, so a lake AHEAD reads here as well: the seven LAVA AHEAD frames
#: of four runs read 0.018-0.116 while not yet burning (lava_fraction
#: 0.011-0.099), and 36 mob-hit frames of the other arms max 0.062. The threshold sits
#: between the lakes (<= 0.12) and the flames (>= 0.20): a hit taken beside a lava lake
#: is the mob's, not the lava's (audit pass 15).
#: Used with lava_fraction: standing IN lava at eye level shows no lava below the
#: crosshair, only the flames.
_FIRE_R_MIN = 150.0
_FIRE_GR = (0.35, 0.80)
_FIRE_BR_MAX = 0.30
FIRE_FRAC_MIN = 0.16


def fire_fraction(frame: np.ndarray) -> float:
    """Share of the lower band of the view covered by the burning overlay's flames."""
    if frame is None or frame.ndim != 3:
        return 0.0
    h, w = frame.shape[0], frame.shape[1]
    f = frame.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    rr = np.maximum(r, 1.0)
    m = ((r >= _FIRE_R_MIN) & (g / rr >= _FIRE_GR[0]) & (g / rr <= _FIRE_GR[1])
         & (b / rr <= _FIRE_BR_MAX))
    m[int(h * 0.90):, int(w * 0.27):int(w * 0.73)] = False
    m[int(h * 0.70):, int(w * 0.75):] = False
    low = m[int(h * 0.55):int(h * 0.98)]
    return float(low.mean()) if low.size else 0.0


#: Still water in daylight, measured on the live corpus: one run step 481 (a
#: pond 2-6 blocks ahead: 15% of the frame), one run step 2400 (a river: 25% of the
#: lower view), one run steps 457/597 and another step 3780 (a pond glimpsed through
#: spruce leaves: 0.1-5%). Blue over green over red, mean (62, 84, 130), blue 115-147
#: (10th-90th percentiles), (B-R)/B >= 0.40. The open sky keeps the same order but is
#: brighter (blue >= 210 by day) and sits above the horizon: the callers measure from one
#: degree below it (the horizon row is 0.5 - pitch/70 of the height in a 70-degree view),
#: which at pitch 12 is the 34% line; 78 other frames of the corpus read <= 0.018 there.
_WATER_B = (70.0, 210.0)
_WATER_BR_MIN = 0.40
#: A glimpse worth walking toward: ~300 px of the lower view (one run's pond through the
#: spruce leaves at pitch 35 read 0.0014; 130 of 200 corpus frames read exactly 0 and 49
#: below 0.001; the readings of 0.001-0.002 were the night sky seen at pitch 0 with the
#: inventory open -- the macro pitches 12-15 down, which puts the sky above the 35% line).
WATER_SEEN = 0.002
#: The lower-centre window (rows 55-85%, columns 25-75%) at the shore: the pool 2.5-3.5
#: blocks ahead at pitch 15 fills a third of it (the sweep's aims reach 1.5-5 blocks); a
#: distant pond stays above the window.
WATER_NEAR = 0.30


def water_mask(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    bb = np.maximum(b, 1.0)
    return ((b >= _WATER_B[0]) & (b <= _WATER_B[1]) & (b > g) & (g > r)
            & ((b - r) / bb >= _WATER_BR_MIN))


def water_view(frame: np.ndarray, rows_from: float = 0.35) -> tuple[float, float, float]:
    """(fraction, cx, bottom) of the water in the view below `rows_from` of the height:
    `cx` is the mass's column centre as -0.5..0.5 of the width (negative = left of the
    crosshair), `bottom` its lowest row as 0..1 of the height (1 = the frame's bottom)."""
    if frame is None or frame.ndim != 3:
        return 0.0, 0.0, 0.0
    h, w = frame.shape[0], frame.shape[1]
    m = water_mask(frame)
    m[int(h * 0.90):, int(w * 0.27):int(w * 0.73)] = False       # the hotbar
    m[int(h * 0.70):, int(w * 0.75):] = False                     # the held item
    low = m[int(h * rows_from):]
    n = int(low.sum())
    if n == 0 or low.size == 0:
        return 0.0, 0.0, 0.0
    ys, xs = np.nonzero(low)
    return (float(n) / float(low.size), float(xs.mean()) / float(w) - 0.5,
            (float(ys.max()) + int(h * rows_from)) / float(h))


def water_near(frame: np.ndarray) -> float:
    """Share of the lower-centre window (rows 55-85%, columns 25-75%) that is water."""
    if frame is None or frame.ndim != 3:
        return 0.0
    h, w = frame.shape[0], frame.shape[1]
    win = water_mask(frame)[int(h * 0.55):int(h * 0.85), int(w * 0.25):int(w * 0.75)]
    return float(win.mean()) if win.size else 0.0


def lava_mask(frame: np.ndarray) -> np.ndarray:
    """The lava-coloured pixels of the whole frame, with the two overlays that wear
    lava's own colours cut out: the hotbar strip (bottom 14%) and the held item in the
    lower-right corner. `lava_fraction` and `lava_view` both read this."""
    h, w = frame.shape[0], frame.shape[1]
    f = frame.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    rr = np.maximum(r, 1.0)
    m = ((r >= _LAVA_R_MIN) & (g / rr >= _LAVA_GR[0]) & (g / rr <= _LAVA_GR[1])
         & (b / rr >= _LAVA_BR[0]) & (b / rr <= _LAVA_BR[1]))
    m[int(h * 0.86):] = False
    m[int(h * 0.55):, int(w * 0.60):] = False
    return m


#: Head under lava: the view is lava's fog edge to edge, a flat deep red that is neither
#: the lava texture (`lava_fraction` reads 0.000-0.048 there) nor, between flickers, the
#: flames (`fire_fraction` 0.000-0.58). Measured on the upper 55% of the frame (above the
#: flame band and the hotbar): the 22 frames of three deaths in the Nether's lava sea
#: read 0.76-1.00; 4,957 other frames of six lives -- the Nether's netherrack, a lava
#: lake from its bank, a lit portal, the burning overlay, a forest on fire -- at most 0.29.
_SUBMERGED_R_MIN = 90.0
_SUBMERGED_GR_MAX = 0.40
_SUBMERGED_BR_MAX = 0.12
LAVA_SUBMERGED_MIN = 0.5


def lava_submerged(frame: np.ndarray) -> float:
    """Share of the upper view that is the red fog seen from inside lava."""
    if frame is None or frame.ndim != 3:
        return 0.0
    h = frame.shape[0]
    f = frame[:int(h * 0.55)].astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    rr = np.maximum(r, 1.0)
    m = (r >= _SUBMERGED_R_MIN) & (g / rr <= _SUBMERGED_GR_MAX) & (b / rr <= _SUBMERGED_BR_MAX)
    return float(m.mean()) if m.size else 0.0


def lava_fraction(frame: np.ndarray) -> float:
    """Share of the lower view that is lava-coloured (see the constants above)."""
    if frame is None or frame.ndim != 3:
        return 0.0
    h = frame.shape[0]
    low = lava_mask(frame)[int(h * 0.35):]
    return float(low.mean()) if low.size else 0.0


def lava_view(frame: np.ndarray, rows_from: float = 0.35
              ) -> tuple[float, float, float, float]:
    """(fraction, cx, bottom, top) of the lava below `rows_from` of the height.

    The reading `lava_fraction` throws away: where the mass IS. `cx` is its column
    centre as -0.5..0.5 of the width (negative = left of the crosshair, so the bearing
    is yaw + cx * the horizontal view); `bottom` and `top` are its lowest and highest
    rows as 0..1 of the height (1 = the frame's bottom), so `bottom` is the depression
    of the mass's NEAR edge and `top` that of its far edge. `fraction` at the default
    `rows_from` is exactly `lava_fraction`.

    `bottom` saturates at 0.86: the hotbar cut removes the bottom 14% of the frame, so
    lava that reaches the frame's lower edge reads 0.86 and its distance estimate is an
    UPPER bound on how near it is (macros_nether.lava_cells says so in its note)."""
    if frame is None or frame.ndim != 3:
        return 0.0, 0.0, 0.0, 0.0
    h, w = frame.shape[0], frame.shape[1]
    cut = int(h * rows_from)
    low = lava_mask(frame)[cut:]
    n = int(low.sum())
    if n == 0 or low.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    ys, xs = np.nonzero(low)
    return (float(n) / float(low.size), float(xs.mean()) / float(w) - 0.5,
            (float(ys.max()) + cut) / float(h), (float(ys.min()) + cut) / float(h))


#: Diamond-ore speckles, measured in the standalone sim (a probe:
#: torch-lit stone tunnel, the block 2/4/6 blocks ahead): the cyan pixels
#: average (87, 191, 182) at every distance -- (B-R)/B 0.33-0.73 and (G-R)/G 0.38-0.73
#: (10th-90th percentiles), with blue and green EQUAL: |(B-G)/B| <= 0.08. That last band
#: is what separates them from everything else blue underground: lapis (16,53,125:
#: (B-G)/B 0.52-0.67), water (41,68,124: 0.38-0.48), ice/packed ice (0.22-0.32); and
#: emerald (18,177,78) is green-led ((B-G)/B -1.3). The cyan blocks that DO share the
#: hue -- diamond block, prismarine, cyan/light-blue wool -- are block-scale masses,
#: which the density cap and the blob census below reject exactly as they reject dirt
#: clumps for iron. Speckles cover 13-15% of the ore face; the base stays grey.
#: Their RED is below the stone's, so the local-contrast test reads the blue channel.
#: Bands sit just inside the measured 10th percentiles (0.33 / 0.38 / +-0.08); the
#: blue-green cap at 0.10 is what rejected the one confusable that fired on the probe
#: frames, light-blue wool at 6 blocks ((B-G)/B 0.15-0.27).
_DIA_BR_LO, _DIA_BR_HI = 0.30, 0.80
_DIA_GR_LO, _DIA_GR_HI = 0.36, 0.80
_DIA_BG_MAX = 0.10


def _ore_mask(body: np.ndarray, kind: str) -> tuple[np.ndarray, np.ndarray]:
    """(speckle mask, the channel the speckles lead in) for one ore kind."""
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        if kind == "iron":
            rb = (r - b) / np.maximum(r, 1.0)
            rg = (r - g) / np.maximum(r, 1.0)
            band = ((rb > _ORE_RB_LO) & (rb < _ORE_RB_HI)
                    & (rg > _ORE_RG_LO) & (rg < _ORE_RG_HI))
            lead = r
        else:
            br = (b - r) / np.maximum(b, 1.0)
            gr = (g - r) / np.maximum(g, 1.0)
            bg = (b - g) / np.maximum(b, 1.0)
            band = ((br > _DIA_BR_LO) & (br < _DIA_BR_HI)
                    & (gr > _DIA_GR_LO) & (gr < _DIA_GR_HI)
                    & (np.abs(bg) <= _DIA_BG_MAX))
            lead = b
    local = _local_mean(lead, 33)
    return band & (lead > _ORE_FLOOR) & (lead > _ORE_CONTRAST * local), lead


def find_iron_ore(frame: np.ndarray) -> tuple[int, int, int] | None:
    """Screen (x, y, n_pixels) of the most iron-ore-like speckle cluster, or None."""
    return _find_ore(frame, "iron")


def find_diamond_ore(frame: np.ndarray) -> tuple[int, int, int] | None:
    """Screen (x, y, n_pixels) of the most diamond-ore-like speckle cluster, or None
    (cyan dots on grey; see the _DIA bands)."""
    return _find_ore(frame, "diamond")


def find_ore(frame: np.ndarray) -> tuple[str, tuple[int, int, int]] | None:
    """(kind, hit) for the first ore kind whose speckles are on screen, iron first."""
    for kind in ("iron", "diamond"):
        hit = _find_ore(frame, kind)
        if hit is not None:
            return kind, hit
    return None


def _find_ore(frame: np.ndarray, kind: str) -> tuple[int, int, int] | None:
    """Screen (x, y, n_pixels) of the most ore-like speckle cluster of `kind`, or None.

    A sighting aid, not a verdict: it interrupts a mining macro so the agent can zoom /
    `aim_at_ore` the spot, and a false positive costs one interrupted entry (plus the
    100-step cooldown). The HUD rows are excluded. Iron here means: tan speckles (the
    ratio bands), brighter than their immediate surroundings (local contrast -- works in
    cave darkness where the old absolute gate was blind), arranged as several TINY blobs
    (intra-block texture, not a dirt clump), sitting on a mostly GREY base (stone, not a
    dirt or grass field).
    """
    if frame is None or frame.ndim != 3:
        return None
    h = frame.shape[0]
    body = frame[: int(h * 0.82)].astype(np.float32)
    mask, _lead = _ore_mask(body, kind)
    if int(mask.sum()) < _ORE_MIN_CLUSTER:
        return None
    dens = _local_mean(mask.astype(np.float32), 17)
    capped = dens * (dens < _ORE_MAX_DENSITY)
    cy, cx = np.unravel_index(int(capped.argmax()), capped.shape)
    if int(dens[cy, cx] * 289) < _ORE_MIN_CLUSTER or dens[cy, cx] >= _ORE_MAX_DENSITY:
        return None
    y0, x0 = max(0, cy - 24), max(0, cx - 24)
    window = mask[y0:cy + 24, x0:cx + 24]
    if int(window.sum()) < _ORE_MIN_CLUSTER:
        return None
    ys, xs = np.where(window)
    if ys.std() < 2.0 or xs.std() < 2.0:
        return None
    # Single-pixel mask hits are texture noise, not speckle: the sweep of
    # all 1,118 saved frames found 29 fires -- granite grain, near-black dirt faces,
    # water edges, the inventory player model -- and every one had median blob size 1.
    # Ore speckles are >=2px structures at any distance worth stopping for, so salt
    # does not count toward the blob census or the cluster mass.
    sizes = [s for s in _blob_sizes(window) if s >= 2]
    if (len(sizes) < _ORE_MIN_BLOBS or sum(sizes) < _ORE_MIN_CLUSTER
            or max(sizes) > _ORE_MAX_BLOB
            or int(np.median(sizes)) > _ORE_MED_BLOB):
        return None
    nonmask = ~window
    if int(nonmask.sum()) < 50:
        return None
    wr = body[..., 0][y0:cy + 24, x0:cx + 24]
    wb = body[..., 2][y0:cy + 24, x0:cx + 24]
    sat = np.abs(wr - wb) / np.maximum(wr, 1.0)
    if kind == "diamond":
        # Grey means grey in BOTH differences here: leaves (43,58,40) are r~b and
        # passed the iron test's r-b reading, and sky seen through a canopy fired the
        # cyan band once in the 1,300-frame corpus sweep (one run step 967).
        wg = body[..., 1][y0:cy + 24, x0:cx + 24]
        sat = np.maximum(sat, np.abs(wr - wg) / np.maximum(wr, 1.0))
    if float((sat[nonmask] < _ORE_GREY_SAT).mean()) < _ORE_GREY_FRAC:
        return None
    return (int(xs.mean() + x0), int(ys.mean() + y0), int(sum(sizes)))


# -- tree trunks ----------------------------------------------------------

#: Bark, as colour ratios like the ore bands, but WIDE: oak (109,85,50) gives
#: (R-B)/R=0.54, spruce shadow (60,40,25) gives 0.58 lit up to ~0.72, and the bands
#: must admit both. Dirt (134,96,67 -> 0.50) falls inside them too -- colour cannot
#: separate a trunk from a dirt slope. What can is SHAPE: a trunk is a narrow, tall,
#: well-filled COLUMN of bark with non-bark on both sides; a dirt field is wide and a
#: dirt clump is short. The column tests below carry the discrimination; the colour
#: mask only proposes.
_TRUNK_RB_LO, _TRUNK_RB_HI = 0.30, 0.75
_TRUNK_RG_LO, _TRUNK_RG_HI = 0.15, 0.50
_TRUNK_R_LO, _TRUNK_R_HI = 35.0, 190.0
_TRUNK_SAT_MIN = 12.0
#: Column acceptance: at least this many bark px in a column, filling at least this
#: fraction of the column's vertical extent, which must itself be tall. At 640x360 a
#: trunk one block away is ~90px wide and full height; at ~12 blocks it is ~8px wide
#: and ~60px tall -- the floors admit that whole approach range.
_TRUNK_COL_MIN_PX = 40
_TRUNK_COL_FILL = 0.50
_TRUNK_COL_EXTENT = 55
#: Run (contiguous trunky columns) bounds: narrower than 5px is not worth walking to,
#: wider than 130px at this resolution is terrain, not a tree.
_TRUNK_RUN_MIN_W, _TRUNK_RUN_MAX_W = 5, 130
#: Run-width limit for harvest_tree's walk-in once its trunk has been seen close
#: (see find_tree_trunk): a one-block trunk spans ~265 px at 1.3 blocks and ~400 px
#: at 0.8 in a 640-px, ~102-degree view.
TRUNK_NEAR_MAX_W = 440
#: At least one flank of a trunk is mostly non-bark. The two-sided version of this rule
#: rejected half the real trunks (a forest trunk often has a barky branch or a second
#: trunk on one side), so the dirt-wall family is handled by the two scene tests below
#: instead of by the flanks.
_TRUNK_FLANK_RATIO = 0.5
#: Scene tests, from the calibration corpus (129 wood / 139 underground frames):
#: a frame whose body is more than ~30% bark-coloured is terrain filling the view (a
#: dirt wall face-on), not a tree standing in it -- no aim target exists in such a
#: frame anyway. And a tree carries GREEN: leaves above, grass at its foot. The dirt
#: shoulders that defeat the flank test (one run step 5354) sit in green-free tunnels.
_TRUNK_MAX_MASK_FRAC = 0.30
_TRUNK_GREEN_MARGIN = 8.0
_TRUNK_GREEN_MIN_FRAC = 0.08
#: The held item/hand occupies the lower right of the first-person frame and is
#: skin-toned -- inside the bark bands. Its home region is excluded from the mask.
_HAND_X_FRAC, _HAND_Y_FRAC = 0.58, 0.50



def _bark_mask(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(body, mask): the frame above the hotbar as float32 and its bark-coloured pixels,
    with the held-item corner blanked."""
    h = frame.shape[0]
    body = frame[: int(h * 0.82)].astype(np.float32)
    bh, bw = body.shape[0], body.shape[1]
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = (r - b) / np.maximum(r, 1.0)
        rg = (r - g) / np.maximum(r, 1.0)
    mask = ((r >= _TRUNK_R_LO) & (r <= _TRUNK_R_HI) & (r - b >= _TRUNK_SAT_MIN)
            & (rb > _TRUNK_RB_LO) & (rb < _TRUNK_RB_HI)
            & (rg > _TRUNK_RG_LO) & (rg < _TRUNK_RG_HI))
    mask[int(bh * _HAND_Y_FRAC):, int(bw * _HAND_X_FRAC):] = False
    return body, mask


def find_tree_trunk(frame: np.ndarray, prefer_x: float | None = None,
                    max_w: int | None = None) -> tuple[int, int, int, int] | None:
    """Screen (x, y, n_pixels, run_width) of the most trunk-like bark column, or None.

    `prefer_x`: when given, runs near that screen x win ties against a slightly
    better-scoring run elsewhere -- harvest_tree tracks ONE trunk across ticks and
    must not be steered to a neighbour that scores higher in one frame.

    `max_w`: widest bark run accepted (default `_TRUNK_RUN_MAX_W`, sized for a trunk
    a few blocks off). harvest_tree's walk-in passes `TRUNK_NEAR_MAX_W`: within ~1.5
    blocks a trunk is 150-400 px wide and the stock limit made it vanish exactly when
    the servo had to hold it -- the walk then steered to the next detected trunk and
    drove past the one it had reached (one run's second call, replayed in the sim).

    An aiming aid for the wood phase -- the largest remaining variance source on both
    tasks (four runs lost 1,900-3,000 steps re-finding trees). Invoked
    deliberately by the model (`aim_at_tree`), not as an autonomous sentinel, so a
    false positive costs a look, not an interrupt: the bar is set for daylight scenes
    with a tree somewhere in view. The y returned is biased toward the lower part of
    the visible trunk -- that is the block a chop can reach.
    """
    if frame is None or frame.ndim != 3:
        return None
    body, mask = _bark_mask(frame)
    bh, bw = body.shape[0], body.shape[1]
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    if float(mask.mean()) > _TRUNK_MAX_MASK_FRAC:
        return None
    green = ((g > r + _TRUNK_GREEN_MARGIN) & (g > b + _TRUNK_GREEN_MARGIN))
    counts = mask.sum(axis=0)
    ys_any = mask.any(axis=0)
    first = np.where(ys_any, mask.argmax(axis=0), 0)
    last = np.where(ys_any, bh - 1 - mask[::-1].argmax(axis=0), 0)
    extent = np.where(ys_any, last - first + 1, 0)
    trunky = ((counts >= _TRUNK_COL_MIN_PX) & (extent >= _TRUNK_COL_EXTENT)
              & (counts >= _TRUNK_COL_FILL * np.maximum(extent, 1)))
    if not trunky.any():
        return None
    # Contiguous runs of trunky columns (gaps of 1-2 px bridged: leaf pixels cross a
    # trunk without splitting it in half visually, and should not split it here).
    filled = trunky.copy()
    for i in range(1, bw - 1):
        if not filled[i] and filled[i - 1] and (trunky[i + 1] or
                                                (i + 2 < bw and trunky[i + 2])):
            filled[i] = True
    best = None
    i = 0
    while i < bw:
        if not filled[i]:
            i += 1
            continue
        j = i
        while j < bw and filled[j]:
            j += 1
        width = j - i
        if _TRUNK_RUN_MIN_W <= width <= (max_w or _TRUNK_RUN_MAX_W):
            run_mean = float(counts[i:j].mean())
            flanks = []
            for lo, hi in ((max(0, i - 18), max(0, i - 4)), (min(bw, j + 4),
                                                             min(bw, j + 18))):
                if hi - lo >= 6:
                    flanks.append(float(counts[lo:hi].mean()))
            ctx = green[:, max(0, i - 20):min(bw, j + 20)]
            green_ok = float(ctx.mean()) >= _TRUNK_GREEN_MIN_FRAC if ctx.size else False
            if green_ok and (not flanks
                             or min(flanks) < _TRUNK_FLANK_RATIO * run_mean):
                score = width * run_mean
                if prefer_x is not None:
                    score /= 1.0 + abs((i + j) / 2.0 - float(prefer_x)) / 120.0
                if best is None or score > best[0]:
                    best = (score, i, j)
        i = j
    if best is None:
        return None
    _, i, j = best
    ys, xs = np.where(mask[:, i:j])
    if ys.size == 0:
        return None
    aim_y = int(np.percentile(ys, 65))
    return (int(xs.mean()) + i, aim_y, int(ys.size), int(j - i))



# -- which screen is open ---------------------------------------------

#: Container-pixel probes that separate the three screens this agent opens. All
#: three draw the same 176x166 centred container: a light bevel at (2,2) (~254), the
#: flat #C6C6C6 body (~198) at (4,4) and to the right of the output slot
#: (150..170, 60..80), a dark bevel at (173,163) (~85). Where the crafting table's
#: 3x3 grid has its cells 0 and 6 (31..45 x 18..32 / 54..68), the furnace screen
#: shows plain body (~198) and the survival inventory shows the player-model box
#: (dark, ~0-30); a cell's inner grey is ~139, and an item in it only lowers that.
#: Measured over 160 archived GUI frames: cell means 0-29 (inventory),
#: 64-139 (table), 186-198 (furnace); nothing between 30 and 60 or 150 and 185.
#: Container top rows the engine can draw at 640x360: 166-tall screens (inventory,
#: table, furnace/smoker/blast furnace, brewing stand, enchanting table, stonecutter,
#: anvil) at 97, a 3-row chest or barrel (168) at 96, a double chest (222) at 69.
#: Ordered widest container first so a partial match cannot claim a taller screen.
_CONTAINER_TOPS = (69, 96, 97)

#: (kind, required slots, forbidden slots, misses allowed) in container pixels, each
#: (x, y) or (x, y, pad) the top-left of a slot's 16x16 item area. Measured on the sim
#: frames of every container screen: these four are exactly the 166-tall
#: layouts the cell probes below cannot name, and each one's forbidden list carries the
#: slot that would otherwise let a furnace or another of the four match it. The three
#: legacy kinds are deliberately absent -- they are still decided by the cell probes.
_SLOT_SIGNATURES = (
    ("brewing", ((17, 17), (79, 17), (56, 51), (79, 58), (102, 51)),
     ((56, 17),), 1),
    ("enchanting", ((15, 47), (35, 47)), ((56, 17), (20, 33), (27, 47)), 0),
    ("stonecutter", ((20, 33), (143, 33, 4)), ((15, 47), (56, 17)), 0),
    ("anvil", ((27, 47), (76, 47), (134, 47)), ((56, 17),), 1),
)

_SCREEN_BG = (150, 60, 170, 80)
_SCREEN_CELLS = ((31, 18, 45, 32), (31, 54, 45, 68))
_SCREEN_INV_MAX, _SCREEN_TABLE_MAX = 45.0, 168.0


def _container_top(f: np.ndarray, render: tuple[int, int]) -> int | None:
    """Screen row of the open container's top border, or None when no container is drawn.

    The container is CENTRED, so this one reading gives its `backgroundHeight`
    (`render_h - 2*oy`) and therefore which family of screen is open before a single
    slot is probed. The border pattern is the same on every container the engine draws
    and was measured on the sim's own frames: one near-black row, two
    near-white bevel rows, then the flat #C6C6C6 body -- e.g. a chest reads
    0, 253, 255, 197 at rows 96-99 of the centre column and the survival inventory
    reads 2, 255, 254, 199 at 97-100.
    """
    x = render[0] // 2
    if f.shape[0] < render[1] or f.shape[1] <= x:
        return None
    col = f[:, x].astype(np.float32).mean(-1)
    for oy in _CONTAINER_TOPS:
        if oy + 3 >= col.shape[0]:
            continue
        if (col[oy] < 45.0 and col[oy + 1] > 225.0 and col[oy + 2] > 225.0
                and 170.0 < col[oy + 3] < 220.0):
            return oy
    return None


def _is_slot(lum: np.ndarray, x: int, y: int, pad: int = 0) -> bool:
    """Is a slot drawn with its 16x16 item area at container (x, y)?

    Reads the four mid-points of the slot's BORDER, never its interior: Minecraft draws
    a slot as a dark top/left bevel (~55) and a white bottom/right one (~255) in the
    background texture, and an item icon is drawn inside that ring. So this answers
    "is there a slot here" for a full slot exactly as well as for an empty one, which
    is what telling a brewing stand from a furnace needs -- their contents change, their
    slot layouts do not. `pad` widens the ring for a big result slot (the furnace's and
    the stonecutter's are drawn as a 26x26 frame around the same 16x16 item area).
    Three of the four is enough: the cursor arrow is 9x16 and can sit on one edge.
    """
    h, w = lum.shape
    top, left = y - 1 - pad, x - 1 - pad
    bottom, right = y + 16 + pad, x + 16 + pad
    if top < 0 or left < 0 or bottom >= h or right >= w:
        return False
    cx, cy = x + 8, y + 8
    # int() each test: numpy booleans add as logical OR, so summing them raw counts
    # one hit however many there are.
    hits = (int(lum[top, cx] < 100.0) + int(lum[cy, left] < 100.0)
            + int(lum[bottom, cx] > 200.0) + int(lum[cy, right] > 200.0))
    return hits >= 3


def _slot_signature(f: np.ndarray, ox: int, oy: int) -> str | None:
    """The 166-tall screen whose slot layout the frame shows, or None.

    Only the four kinds the legacy body below cannot name. Nothing here can return
    inventory/table/furnace, so those three keep exactly the classification (and the
    exact failure modes) they had before this function existed.
    """
    lum = f.astype(np.float32).mean(-1)

    def here(spec):
        return _is_slot(lum, ox + spec[0], oy + spec[1], spec[2] if len(spec) > 2 else 0)

    for kind, required, forbidden, allow_miss in _SLOT_SIGNATURES:
        if any(here(s) for s in forbidden):
            continue
        misses = sum(0 if here(s) else 1 for s in required)
        if misses <= allow_miss:
            return kind
    return None


def screen_kind(frame: np.ndarray | None,
                render: tuple[int, int] = (640, 360)) -> str | None:
    """The container drawn in `frame`, else None.

    'inventory', 'table' and 'furnace' (smoker and blast furnace share the furnace's
    layout and are reported as one) come from the cell probes below, unchanged. The
    container screens added come first: 'chest' (single chest, barrel,
    shulker box -- a 3-row 176x168 container), 'chest2' (double chest, 6 rows,
    176x222) and, among the 166-tall screens, 'brewing', 'enchanting' and
    'stonecutter'. An 'anvil' is recognised but has no macro.

    The runner's cursor model knows WHERE it clicked but not WHAT screen it was on:
    the same container pixels are a 3x3 cell on a crafting table and the fuel slot on
    a furnace, and the [GRID] line listed every reading at once. Worse, the close
    guard counted a furnace's in/fuel/out contents as "off-inventory, would drop on
    the floor": every smelt ended in a refused close, a forced close and a note that
    sent the model sweeping the floor for ore that sat in the furnace (8-45 refusals
    and 9-17 such notes per landed z arm).
    """
    if frame is None or getattr(frame, "ndim", 0) != 3:
        return None
    from mcu_worldmodel import gui
    f = np.asarray(frame)
    ox, oy = gui.container_origin(*render)
    ox, oy = int(ox), int(oy)
    top = _container_top(f, render)
    if top is not None:
        height = render[1] - 2 * top
        if height in (168, 222):
            # A chest-shaped container: 3 or 6 rows. Confirmed on the player hotbar
            # row, which every one of these screens draws at its own offset -- a
            # height reading alone would call a half-drawn frame a double chest.
            kind = "chest" if height == 168 else "chest2"
            hot = [gui.player_slot_topleft(s, kind) for s in range(9)]
            lum = f.astype(np.float32).mean(-1)
            if sum(_is_slot(lum, ox + tl[0], oy + tl[1]) for tl in hot) >= 6:
                return kind
        elif height == 166:
            k = _slot_signature(f, ox, oy)
            if k is not None:
                return k
    h, w = f.shape[0], f.shape[1]
    if oy + gui.CONTAINER_H > h or ox + gui.CONTAINER_W > w:
        return None
    lum = f[oy:oy + gui.CONTAINER_H, ox:ox + gui.CONTAINER_W].astype(np.float32).mean(-1)
    x0, y0, x1, y1 = _SCREEN_BG
    bg = lum[y0:y1, x0:x1]
    if not (abs(float(bg.mean()) - 198.0) <= 8.0 and float(bg.std()) < 6.0):
        return None
    if not (abs(float(lum[2, 2]) - 254.0) <= 8.0 and 70.0 <= float(lum[163, 173]) <= 100.0
            and abs(float(lum[4, 4]) - 197.0) <= 14.0):
        return None
    cells = [float(lum[cy0:cy1, cx0:cx1].mean()) for cx0, cy0, cx1, cy1 in _SCREEN_CELLS]
    m = sum(cells) / len(cells)
    if m <= _SCREEN_INV_MAX:
        return "inventory"
    if m <= _SCREEN_TABLE_MAX:
        return "table"
    return "furnace"

# -- grid occupancy -------------------------------------------------------

#: An empty slot renders as flat grey (luminance std 0.0-2.7 measured over one run's
#: GUI frames); any item icon is texture (std 28.8-57.1 over the same frames). The gap
#: is an order of magnitude, so the threshold sits comfortably between.
_SLOT_STD_MIN = 12.0


def slot_occupied(frame: np.ndarray, screen_x: int, screen_y: int) -> bool:
    """True when the 16px slot box at screen (x, y) top-left holds an item icon.

    This is what makes crafting-grid state observable at all: MineRL's inventory
    observation covers the 36 player slots and nothing else, so two sticks left behind
    in a grid cell were invisible to every channel -- one run spent its endgame lifting
    and replacing a cobblestone stack around a grid it could not read, and lost the
    ingredients to an out-of-range screen close. The frame has the answer at a known
    coordinate.
    """
    box = frame[screen_y + 1: screen_y + 15, screen_x + 1: screen_x + 15]
    if box.size == 0:
        return False
    return float(box.astype(np.float32).std()) > _SLOT_STD_MIN


# == entities: motion and colour ==========================================
#
# Why a detector at all. `info['mobs']` is ALWAYS empty for this agent (the `mobs`
# action region is never set, and the evaluation forwards no entity channel either),
# so "combat and kill zombies", "hunt pigs with a sword", "shear sheep", "hook a
# chicken with a fishing rod" and "trap a spider with a boat" have no ground truth to
# aim at before the swing lands. What the frame carries is two independent signals:
# a mob MOVES against a world that does not, and a mob is COLOURED unlike terrain.
#
# Motion is primary because it needs no per-mob knowledge: any entity that breathes,
# steps or swings changes pixels where nothing else does, so `find_moving_blob` finds
# a phantom, a witch and a wolf with the same code. Its precondition is that the two
# frames were taken with the camera still -- the caller (macros_entity) holds a still
# tick before every diff and counts the run of still ticks, because one camera nudge
# changes every pixel in the frame and the diff becomes meaningless.
#
# Colour is the label, and the fallback where motion is unavailable: a `/summon`ed
# NoAI mob is perfectly rigid (measured in a staged scene: two still frames of a
# NoAI zombie 3 blocks ahead differ in 0 pixels above the threshold), which is exactly
# the case a stage prepares and never the case in a live world.
#
# Both return the blob in FULL-frame pixel coordinates so the caller can steer the
# crosshair with the same px -> degrees gains `_aimtree_tick` uses.

#: The HUD (hotbar, health, hunger, XP bar) occupies the bottom of the frame and
#: repaints on every hit and every item change; it is never an entity.
_ENT_HUD_FRAC = 0.82
#: The held item and the avatar's arm live in the lower right and swing on attack.
#: Measured on staged-scene frames: a bare arm covers x 455-640 / y 255-360,
#: a drawn bow x 540-640 / y 195-330. The mask is deliberately the SMALLER of those:
#: an over-wide corner mask hid two thirds of a zombie standing at the right of the
#: view (a staged scene) and face_entity turned the wrong way.
_ENT_HAND_X_FRAC, _ENT_HAND_Y_FRAC = 0.84, 0.70
#: Advancement / recipe toasts stack down the upper-right corner (measured x 490-640,
#: y 0-70 for two of them). They are game UI drawn over the scene, like the hotbar,
#: and a white toast box read as a sheep on an empty platform until this went in.
_ENT_TOAST_X_FRAC, _ENT_TOAST_Y_FRAC = 0.75, 0.22
#: Per-channel difference (0-255) a pixel must move to count as changed. Set well above
#: the JPEG and lighting noise of two consecutive frames and well below a silhouette
#: sliding across terrain. What was actually measured (a staged scene): two still
#: frames of an empty stone platform under a forest horizon produce NO blob at this
#: threshold, and a live pig 3 blocks ahead produces a 95 px one. The mob is what
#: moves; the ambient animations that could compete (water, lava, fire) are gradual
#: enough per tick that the erosion below removes what survives the threshold.
_MOTION_THRESH = 30.0
#: A changed pixel must have changed neighbours (4-erosion). Chat text, particles and
#: the odd JPEG speckle are one or two pixels wide and vanish; a mob's silhouette at
#: 12 blocks is still ~10 px across and survives.
#: Blobs smaller than this are not worth turning toward. 40 px is a mob at ~10 blocks
#: shifting its weight; a skeleton across a gap has to be findable, or the bow has no
#: target (a staged scene measured one at 8 blocks that a 60 px floor missed entirely).
_MOTION_MIN_PX = 40
#: And a silhouette is TALL: chat text fading out and an arrow stuck in the ground are
#: wide 5-6 px slivers (measured 43x5 and 29x6 in a staged scene). A mob 40 blocks away is
#: still 13 px tall, so the floor costs nothing real.
_MOTION_MIN_SIDE, _MOTION_MIN_H = 5, 12
#: A change covering more than this fraction of the searched body is the whole scene
#: moving (the camera was not still after all, or the avatar is in water/lava).
_MOTION_MAX_FRAC = 0.35
#: Runs cap: a mask this fragmented is noise, not a silhouette.
_MAX_RUNS = 6000


def _erode4(m: np.ndarray) -> np.ndarray:
    """4-neighbour erosion: a pixel survives only with all four neighbours set."""
    e = m.copy()
    e[1:, :] &= m[:-1, :]
    e[:-1, :] &= m[1:, :]
    e[:, 1:] &= m[:, :-1]
    e[:, :-1] &= m[:, 1:]
    e[0, :] = False
    e[-1, :] = False
    e[:, 0] = False
    e[:, -1] = False
    return e


def _components(mask: np.ndarray) -> list[dict[str, float]]:
    """8-connected components of a boolean mask, largest first.

    Row-run union-find rather than a per-pixel flood fill: a mob silhouette is a few
    hundred runs where it is a hundred thousand pixels, and this runs inside a per-tick
    macro loop. Each entry is {n, cx, cy, x0, y0, w, h}; coordinates are the mask's own.
    """
    h, w = mask.shape
    parent: list[int] = []
    runs: list[tuple[int, int, int]] = []          # (y, x0, x1) indexed by run id

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    prev: list[tuple[int, int, int]] = []          # (x0, x1, id) of the row above
    for y in range(h):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        d = np.diff(row.astype(np.int8))
        starts = (np.flatnonzero(d == 1) + 1).tolist()
        ends = (np.flatnonzero(d == -1) + 1).tolist()
        if row[0]:
            starts.insert(0, 0)
        if row[-1]:
            ends.append(w)
        cur: list[tuple[int, int, int]] = []
        for x0, x1 in zip(starts, ends):
            rid = len(parent)
            parent.append(rid)
            runs.append((y, x0, x1))
            cur.append((x0, x1, rid))
        if len(parent) > _MAX_RUNS:
            return []
        for x0, x1, rid in cur:
            for px0, px1, prid in prev:
                if px0 - 1 < x1 and x0 - 1 < px1:   # 8-connected: one pixel of slack
                    ra, rb = find(rid), find(prid)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
        prev = cur
    agg: dict[int, list[float]] = {}
    for rid, (y, x0, x1) in enumerate(runs):
        r = find(rid)
        n = x1 - x0
        a = agg.get(r)
        if a is None:
            agg[r] = [n, (x0 + x1 - 1) * 0.5 * n, y * n, x0, x1 - 1, y, y]
        else:
            a[0] += n
            a[1] += (x0 + x1 - 1) * 0.5 * n
            a[2] += y * n
            a[3] = min(a[3], x0)
            a[4] = max(a[4], x1 - 1)
            a[5] = min(a[5], y)
            a[6] = max(a[6], y)
    out = [{"n": a[0], "cx": a[1] / a[0], "cy": a[2] / a[0], "x0": a[3], "y0": a[5],
            "w": a[4] - a[3] + 1, "h": a[6] - a[5] + 1} for a in agg.values()]
    out.sort(key=lambda c: -c["n"])
    return out


def _body_mask(frame: np.ndarray) -> np.ndarray:
    """A boolean of the frame region an entity can occupy: above the HUD, outside the
    held-item corner."""
    h, w = frame.shape[0], frame.shape[1]
    keep = np.zeros((int(h * _ENT_HUD_FRAC), w), dtype=bool)
    keep[:] = True
    bh = keep.shape[0]
    keep[int(bh * _ENT_HAND_Y_FRAC):, int(w * _ENT_HAND_X_FRAC):] = False
    keep[:int(bh * _ENT_TOAST_Y_FRAC), int(w * _ENT_TOAST_X_FRAC):] = False
    return keep


def find_moving_blob(prev: np.ndarray | None, cur: np.ndarray | None,
                     min_px: int = _MOTION_MIN_PX, thresh: float = _MOTION_THRESH
                     ) -> tuple[int, int, int, int, int] | None:
    """(x, y, n_px, w, h) of the largest region that changed between two frames.

    THE CALLER GUARANTEES the camera did not move and the avatar did not step between
    the two frames: this is a pixel difference, and one degree of yaw changes every
    pixel in the frame. `macros_entity` holds still ticks and counts them before it
    asks. The returned (x, y) is the blob's centroid in full-frame coordinates -- the
    point to steer the crosshair onto, and for a mob the middle of its hitbox, which
    is where a melee swing has to land (aiming at a pig's head from 3 blocks missed;
    a pig's hitbox is 0.9 blocks high, probe).

    Rejects: everything below the HUD line and the held-item corner (both repaint on
    their own); single-pixel changes (chat text strokes, particles, JPEG noise) via a
    4-erosion; and a change covering more than a third of the body, which means the
    camera moved after all rather than that a mob filled the view.
    """
    if prev is None or cur is None:
        return None
    prev = np.asarray(prev)
    cur = np.asarray(cur)
    if prev.ndim != 3 or cur.ndim != 3 or prev.shape != cur.shape:
        return None
    keep = _body_mask(cur)
    bh = keep.shape[0]
    d = np.abs(cur[:bh].astype(np.int16) - prev[:bh].astype(np.int16)).max(axis=2)
    mask = _erode4((d >= thresh) & keep)
    if not mask.any():
        return None
    if float(mask.mean()) > _MOTION_MAX_FRAC:
        return None
    # Among qualifying blobs, prefer the one nearest the crosshair rather than simply
    # the largest: the caller is already looking roughly at what it wants, and the two
    # standing false positives are game UI that is drawn AWAY from the centre -- the
    # chat log in the lower left (a new line scrolls the whole block) and the toast
    # stack in the upper right (an advancement popping in). Neither can be masked out
    # without also blinding the detector to a mob standing there.
    h, w = mask.shape
    best, best_score = None, 0.0
    for c in _components(mask):
        if c["n"] < min_px:
            break
        if c["w"] < _MOTION_MIN_SIDE or c["h"] < _MOTION_MIN_H:
            continue
        off = ((c["cx"] - w / 2.0) ** 2 + (c["cy"] - h / 2.0) ** 2) ** 0.5
        score = c["n"] / (1.0 + off / 300.0)
        if score > best_score:
            best, best_score = c, score
    if best is None:
        return None
    return (int(round(best["cx"])), int(round(best["cy"])), int(best["n"]),
            int(best["w"]), int(best["h"]))


#: Colour signatures for the mobs the task suite names. These are MEASURED off the
#: staged-scene calibration corpus (each mob summoned alone 3-6 blocks ahead on a stone
#: platform in a forest), not read off the wiki, and two of them were
#: wrong when read off the wiki:
#:   * a zombie's identity is its CYAN SHIRT (0,120,120 / 0,144,144 -- 13% of its
#:     silhouette) and its blue-purple trousers, NOT the green skin, which is almost
#:     entirely hidden behind the body and matches every leaf in a forest;
#:   * a sheep's wool renders at 144-190, not the 231 of the texture file, so a
#:     "bright white" band missed every sheep.
#: The other measured values: witch robe 24,0,48 (23% of it); enderman pure black
#: 0-23, where every shadow in the scene sits at 24-47; pig 168,96,96; cow 48,24,24;
#: wolf 192,192,192; blaze orange; phantom 144,168,240 -- which is also the SKY it
#: flies against, and is the one mob colour cannot separate from its background.
#: A skeleton's bone is 96-135 grey, i.e. exactly the stone it stands on: colour
#: cannot see a skeleton at all, and only the isolation test below and MOTION can.
#:
#: Each entry is (predicate, min_px, max_body_fraction, min_aspect_h/w, max_aspect).
_MOB_BANDS: dict[str, tuple] = {}
#: Isolation: a mob is a silhouette with a BOUNDARY -- the band that matches its body
#: must stop at its edge. Terrain does not: a leaf canopy, a dirt slope and a stone
#: floor all continue past any box drawn on them. So the ring around a candidate's
#: bounding box must match far less than the box itself. This one test is what makes
#: a grey sheep on a grey floor findable and a green forest not a zombie.
_RING_GROW = 0.35
_RING_MAX_ABS = 0.30
_RING_MAX_REL = 0.45
#: Sky, measured on the same corpus (168,192,240 and up): blue over green over red and
#: bright. A blob floating in it is a CLOUD, not an animal -- the empty-platform frame
#: scored a cloud as a sheep until this test went in. The two mobs that legitimately
#: fly (a phantom, a blaze) are exempt.
_SKY_RING_MAX = 0.55
_FLYERS = ("phantom", "blaze")


def _mob_band(label: str, fn, min_px: int = 120, max_frac: float = 0.30,
              ar_lo: float = 0.25, ar_hi: float = 6.0) -> None:
    _MOB_BANDS[label] = (fn, min_px, max_frac, ar_lo, ar_hi)


def _r(a, b):
    """(a - b) / max(a, 1): a shading-invariant channel ratio."""
    return (a - b) / np.maximum(a, 1.0)


# Cyan shirt: green and blue together, well above red, and equal to each other --
# water is the only other blue-green in a Minecraft scene and it has b well above g.
_mob_band("zombie", lambda r, g, b, v, s: (
    (g > r + 32) & (b > r + 32) & (np.abs(g - b) <= 0.20 * np.maximum(g, 1.0))
    & (g >= 55) & (v <= 225)), min_px=70, max_frac=0.22)
_mob_band("pig", lambda r, g, b, v, s: (
    (r > g) & (r > b) & (_r(r, g) > 0.22) & (_r(r, g) < 0.58)
    & (np.abs(g - b) < 0.13 * np.maximum(r, 1.0)) & (v > 105)), min_px=80, max_frac=0.25)
_mob_band("creeper", lambda r, g, b, v, s: (
    (g > r) & (g > b) & (_r(g, r) > 0.66) & (_r(g, b) > 0.66) & (v > 95)),
          min_px=90, max_frac=0.22)
# Measured hide: 48,32,16 / 32,32,16 / 32,16,16 -- a dark OLIVE brown, with blue well
# below green, not the red-brown the texture file suggests. Bark, dirt and dead grass
# all fall in the same band, so the SHAPE gate carries the discrimination: a cow is a
# compact body (0.9 x 1.4 blocks, so taller than it is wide on screen), where the
# forest floor that kept being read as a cow was a flat 67x37 band.
_mob_band("cow", lambda r, g, b, v, s: (
    (r >= g) & (g >= b) & (_r(r, b) > 0.30) & (_r(r, b) < 0.78) & (v > 26) & (v < 122)),
          min_px=400, max_frac=0.22, ar_lo=0.70, ar_hi=2.4)
_mob_band("witch", lambda r, g, b, v, s: (
    (b > g) & (b > r) & (r > g) & (_r(b, g) > 0.50) & (b >= 26) & (v <= 110)),
          min_px=90, max_frac=0.20)
_mob_band("blaze", lambda r, g, b, v, s: (
    (r > 160) & (_r(r, b) > 0.58) & (_r(r, g) > 0.02) & (_r(r, g) < 0.58) & (b < 120)),
          min_px=70, max_frac=0.20)
_mob_band("phantom", lambda r, g, b, v, s: (
    (b > g) & (g > r) & (_r(b, r) > 0.22) & (_r(b, r) < 0.58) & (v > 60) & (v < 215)),
          min_px=80, max_frac=0.18)
_mob_band("enderman", lambda r, g, b, v, s: (v <= 22),
          min_px=90, max_frac=0.18, ar_lo=1.1, ar_hi=9.0)
_mob_band("spider", lambda r, g, b, v, s: (v <= 48) & (v >= 6) & (s < 0.55),
          min_px=130, max_frac=0.18, ar_lo=0.18, ar_hi=1.9)
_mob_band("sheep", lambda r, g, b, v, s: (s <= 0.10) & (v >= 138) & (v <= 232),
          min_px=140, max_frac=0.22, ar_lo=0.30, ar_hi=1.8)
_mob_band("wolf", lambda r, g, b, v, s: (s <= 0.11) & (v >= 150) & (v <= 236),
          min_px=110, max_frac=0.18, ar_lo=0.30, ar_hi=1.9)
_mob_band("chicken", lambda r, g, b, v, s: (s <= 0.13) & (v >= 145),
          min_px=45, max_frac=0.09, ar_lo=0.5, ar_hi=2.8)
_mob_band("skeleton", lambda r, g, b, v, s: (s <= 0.11) & (v >= 96) & (v <= 200),
          min_px=110, max_frac=0.14, ar_lo=1.2, ar_hi=8.0)
# Not a mob: a BOAT floating in front of you is an entity you right-click to get in,
# and three tasks in the suite ride or trap with one. Measured off a placed oak boat
# (a staged scene): bright tan planks, 151-185 / 114-150 / 67-94, and a hull that is much
# wider than it is tall. Sand and bare planks fall in the same band, which is why this
# label is only ever reached through `want="boat"`.
_mob_band("boat", lambda r, g, b, v, s: (
    (r > g) & (g > b) & (_r(r, b) > 0.36) & (_r(r, b) < 0.64)
    & (_r(r, g) > 0.10) & (_r(r, g) < 0.34) & (v > 110) & (v < 220)),
          min_px=350, max_frac=0.30, ar_lo=0.15, ar_hi=1.2)

#: The order a tie is broken in: a hue only one mob has beats the neutral band, which
#: three mobs and the stone floor share.
_MOB_ORDER = ("zombie", "blaze", "creeper", "witch", "pig", "cow", "phantom",
              "enderman", "spider", "wolf", "sheep", "chicken", "skeleton")


def _sky(r, g, b, v) -> np.ndarray:
    """Open sky: blue over green over red, and bright."""
    return (b > g) & (g > r) & (v >= 172)


def _isolated(mask: np.ndarray, c: dict[str, float],
              sky: np.ndarray | None = None) -> tuple[bool, float, float]:
    """(passes, inner_fill, ring_fill) for one candidate component.

    The ring is the band around the candidate's bounding box. Terrain fills it as
    densely as the box; a mob leaves it nearly empty.
    """
    h, w = mask.shape
    x0, y0 = int(c["x0"]), int(c["y0"])
    bw, bh = int(c["w"]), int(c["h"])
    grow = max(6, int(_RING_GROW * max(bw, bh)))
    X0, Y0 = max(0, x0 - grow), max(0, y0 - grow)
    X1, Y1 = min(w, x0 + bw + grow), min(h, y0 + bh + grow)
    outer = mask[Y0:Y1, X0:X1]
    inner_area = bw * bh
    ring_area = outer.size - inner_area
    inner = c["n"] / max(inner_area, 1)
    if ring_area <= 0:
        return (True, inner, 0.0)
    ring_n = float(outer.sum()) - float(mask[y0:y0 + bh, x0:x0 + bw].sum())
    ring = max(0.0, ring_n) / ring_area
    ok = ring <= _RING_MAX_ABS and ring <= _RING_MAX_REL * inner
    if ok and sky is not None:
        sky_n = (float(sky[Y0:Y1, X0:X1].sum())
                 - float(sky[y0:y0 + bh, x0:x0 + bw].sum()))
        ok = max(0.0, sky_n) / ring_area <= _SKY_RING_MAX
    return (ok, inner, ring)


def entity_hint(frame: np.ndarray | None, want: str | None = None,
                min_px: int | None = None, near: tuple[float, float] | None = None
                ) -> tuple[str, int, int, int, int, int] | None:
    """(label, x, y, n_px, w, h) of the most mob-like coloured blob, or None.

    The label half of entity detection, and the whole of it where motion is not
    available: a `/summon`ed NoAI mob is rigid (measured: zero changed pixels between
    two still frames), and the very first thing a fight macro must do in a stage is
    find one. `want` restricts the search to one mob's bands -- far more reliable than
    the open scan, and the normal call, because the model knows from the task text what
    it is hunting. `near` (a screen point) makes a blob close to the last detection win
    a tie, so a loop tracking ONE mob is not steered to a different candidate that
    scores higher in a single frame -- the same job `find_tree_trunk`'s `prefer_x` does.

    (x, y) is the blob's centroid in full-frame coordinates, the same convention
    `find_moving_blob` returns, so a caller can steer on either without branching.
    """
    if frame is None:
        return None
    frame = np.asarray(frame)
    if frame.ndim != 3:
        return None
    keep = _body_mask(frame)
    bh = keep.shape[0]
    body = frame[:bh].astype(np.float32)
    r, g, b = body[..., 0], body[..., 1], body[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    area = float(keep.sum())
    sky = _sky(r, g, b, mx)
    anchor = near if near is not None else (frame.shape[1] / 2.0, frame.shape[0] / 2.0)
    labels = ([want] if want else list(_MOB_ORDER))
    best = None
    for label in labels:
        band = _MOB_BANDS.get(label)
        if band is None:
            continue
        fn, band_min, max_frac, ar_lo, ar_hi = band
        floor = band_min if min_px is None else int(min_px)
        mask = _erode4(fn(r, g, b, mx, sat) & keep)
        if not mask.any() or float(mask.sum()) / max(area, 1.0) > 0.55:
            continue
        for c in _components(mask):
            if c["n"] < floor:
                break
            if c["n"] / max(area, 1.0) > max_frac or c["w"] < 4 or c["h"] < 6:
                continue
            ar = c["h"] / max(c["w"], 1.0)
            if ar < ar_lo or ar > ar_hi:
                continue
            ok, inner, ring = _isolated(
                mask, c, None if label in _FLYERS else sky)
            if not ok or inner < 0.25:
                continue
            off = ((c["cx"] - anchor[0]) ** 2 + (c["cy"] - anchor[1]) ** 2) ** 0.5
            score = c["n"] * inner * (1.0 - ring) / (1.0 + off / 220.0)
            rank = _MOB_ORDER.index(label) if label in _MOB_ORDER else 99
            if best is None or (score, -rank) > (best[0], -best[1]):
                best = (score, rank, label, c)
            break
    if best is None:
        return None
    _, _, label, c = best
    return (label, int(round(c["cx"])), int(round(c["cy"])), int(c["n"]),
            int(c["w"]), int(c["h"]))
