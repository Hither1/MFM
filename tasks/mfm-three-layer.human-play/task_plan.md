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
