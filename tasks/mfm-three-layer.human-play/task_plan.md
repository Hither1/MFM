# Task plan: human-play (2026-09-07 13:3x)

## Stable Anchor
- Question (user, 13:0x-13:3x): how far does the model get when it plays the way a person
  does -- little input, a multimodal memory, and the freedom to compose keys into skills
  while playing -- with no harness skills, advice or reflexes?
- Setting (`--human-play`, MCU spatial-grid-merge, mcu_worldmodel/human.py): KEEP the memory
  mechanism (logs.txt, episodes + frames, [RECALL], `mine/` carried across lives); GIVE what
  the environment feeds back and a player perceives (the 640x360 frame with HUD, [STATE]
  position/pitch/yaw, vitals, inventory, [EVENT]/[INV], damage, death, the ledger and the
  step clock); PROVIDE no built-in procedure beyond the GUI cursor primitives
  (open/close_inventory, cursor_to_slot/cell, gui_click/right_click) and `watch`; NO
  references/*.md, no harness advice (notes are cut to their first sentence), no reflexes,
  guards, governor refusals or nudges (damage and a milestone still end the plan and hand
  the turn back); `--own` implied: the model writes scripts under mine/procedures/ and the
  contract tells it to invent skills that way. No event sheet is pushed.
- Success criterion: milestones per step and per hour against og16 (thin, all built-ins),
  deaths, the number and reuse of its own scripts, when (if) it reaches diamond tools /
  iron / obsidian without any built-in skill.
- Non-goals: no coordinate-free variant here (that is `--visual-only`, og17); no hand-written
  world facts.

## Arm
og18_mfm: `--human-play --expect --frames --retrieval --frame-size 640x360`, gpt-6-astra
high, 60k steps, session-turns 0 + compaction, from scratch, 10h cap, from
MFM-grid-merge-mcu with MFM_ROOT and MCU_CODEX_ROOT set; ports 9120/9130.

## Verification
tests/test_human.py (4): feedback_only, HUMAN_ATOMS and the refusal wording, the chassis
(contract shape, no references, no governor notes over 24 identical plans, own script
called, first-sentence notes, report flag), mfm required. Full list: 102 pass.

## Next Action
Launch og18; watch the first hour: does it craft through the GUI primitives, does it write
scripts, do the raw walks work; at the cap compare with og16.

## Status 2026-09-07 23:0x
og18 at 16.6k steps (1.8k/h): 13/24 (flint_and_steel at 5727, its best-in-class kit
phase), 0 deaths, 22 own scripts under mine/procedures/ (break_stone/log/leaf/ore/soil/
gravel, walk_one/short/block, level_tunnel, pillar_one, place_table, place_wall_torch,
water_descend...), 1232 actions of ~13 steps each; health 2/20 since ~15.6k with no food;
saw a lava fall (mine/cave_lava.png) but never poured on it -- 11k steps without a
milestone. Cap 23:25; compare with og16 (15/24 at 41.8k, 2 deaths) at the cap.

## Final 2026-09-07 23:26 (wall cap)
og18: 17233 steps in 10 h (1.7k/h), 13/24 (flint_and_steel at 5727, then 11.5k steps
without a milestone), 0 deaths, health 2/20 for the last ~1.6k steps. Own harness: 24
scripts under mine/procedures/, 356 calls (report), 943 [ACTION] entries -- watch 309,
gui_click 88, walk_short 66, cursor_to_slot 66, cursor_to_cell 62, level_tunnel 60,
gui_right_click 50, step_up 40; 391 codex turns, 2.3 commands/turn, episodes.py in 3%.
Against og16 (thin, all built-ins, same code otherwise): og16 15/24 at 41.8k with 2
deaths; og18 reached flint 25k steps earlier than og16 (5727 vs 31383) but never got a
bucket to lava: the kit phase and the GUI are learnable from the frame + state text,
the lava-to-obsidian phase was not reached in 10 h at its pace (its walks are one block
at a time). Read: human-play is not a losing setting on milestones per step up to flint;
the wall clock is (1.7k steps/h vs og16's 4.3k).
