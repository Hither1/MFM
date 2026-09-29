"""Stage 14: the obsidian chain from the LIP of a floor-level lake.

ob3_mfm (2026-09-06) reached the 52% lake with the water bucket, the guard fired on a
2% sliver at the bottom of the view and put the pool "at most 3 blocks off"; the lava
was in fact the next cell. make_obsidian() poured from the lip, the flow carried the
avatar off the ledge and it died in the lava 40 ticks later. Stage 12's lake starts 4
blocks ahead; this one starts two cells ahead -- the lip, as ob3 stood (one cell nearer and the
hitbox itself overlaps the lava) -- and the same checks must hold:
make_obsidian() now backs the avatar off the pool before the pour, and mine_obsidian()
walks the cell back into reach (never nearer than 4 blocks) afterwards.
"""
from __future__ import annotations

from mcu_worldmodel.stages import s12_obsidian as S
from mcu_worldmodel.stages.rig import main_guard

S.LAKE_DZ = 2

if __name__ == "__main__":
    main_guard(S.stage)
