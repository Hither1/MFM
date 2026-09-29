"""Stage 17: the obsidian chain from a sighting made 8 blocks short of the lake.

ob5_mfm (2026-09-07) met the 52% lake down a tunnel: the guard fired at 1% with the
pool 'about 8 blocks off', make_obsidian() backed off one more block and the pour was
refused as out of reach. From an UNCLIPPED sighting the distance is measured, so the
standoff tick now walks up to the pool's 3.5-4.2 block band instead. Stage 12's lake
starts 4 blocks ahead (the guard fires at ~2, the avatar backs off); this one starts 8
ahead, and the same checks must hold.
"""
from __future__ import annotations

from mcu_worldmodel.stages import s12_obsidian as S
from mcu_worldmodel.stages.rig import main_guard

S.LAKE_DZ = 8

if __name__ == "__main__":
    main_guard(S.stage)
