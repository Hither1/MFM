# Plan: generation 3 of the carry-only mfm chain (decided 2026-09-09 ~04:40)

User decisions this morning, in order: (1) fold the process rules of
wz1119/Codex-Minecraft-Gameplay's SKILL.md and more Minecraft world knowledge into
AGENTS.md; (2) `SESSION_TURNS=1` (fresh codex thread every turn) so the model's only
continuity is the MFM; (3) make our skills codex-native so they trigger by description;
(4) rank everything from the six-life review (`analysis/systemic_of_2026-09-09.md`) into
one plan. The four things the work has to show: a top score, a framework without known
bugs, the multimodal memory doing work a text log cannot, the model improving itself
(scripts, reflexes, memory management), and memory reuse across lives.

Evidence behind the two reversals:
- One thread + compaction (Phase 2 protocol, 2026-09-07) was chosen to copy the "one
  context" advantage. The rollouts show codex compacted every 8-10 turns anyway (28-58
  `compacted` records per life, invisible to the harness); the model's durable state was
  its own `working.md` (40-68 KB, rewritten every turn) plus codex's summary. With
  `--session-turns 1` (already the launcher default; og-era arms ran it) nothing but the
  MFM carries state between turns, which is the claim we want to make.
- Our four `skills/<name>/SKILL.md` never reached codex's skill catalog: of3r's rollout
  has no `### Available skills` list, the codex home `skills/` holds only `.system`.
  AGENTS.md says "read all four in your first turn"; the triggers written inside them
  ("before you walk to a remembered place", "after YOU DIED", "a plan failed twice")
  were read once and lived in the compacted thread. After turn 1: digest re-read
  0/0/1, notes 0, previous-life frames 2/2/6.

## P0 -- close generation 2 (today, no API)

- [ ] Record of1r / of2r / of3r at their wall stops (05:10 / 06:08 / 07:13): milestones
      and steps, deaths with places, memory-use counters (previous/ reads after turn 1,
      digest re-reads, previous-life frames, `--then-now`), scripts carried/new. progress.md,
      commit, push. of3r's 15/24 (62.5) is the carry-only full-task record; obf2's 54.17
      ran with `--sites`.
- [ ] Stage the six lives with `scripts/stage_hf_mfm_era.py` (strip previous/, slim
      rollouts, anonymise). Upload is the user's gate.

## P1 -- the method changes that define gen 3 (all before any launch)

1. **`SESSION_TURNS=1`.** No code: `SESSION_TURNS=1` (drop `COMPACT=1`) in the launch env.
   Verify on a 5-turn smoke: turn wall time (of3r median 73 s, p90 207 s -- turn time is
   the budget, 107 steps/turn), tokens per turn, and that a fresh-session turn message
   carries `[WORKING]` (agent.py:4258), `[RECALL]`, `[STATE]/[INV]`/ledger/notes and the
   frame. If turn time rises materially, cut AGENTS.md (see 3e) before anything else.
2. **Native skills.** Per-arm codex home `skills/<name>` -> the workspace `skills/<name>`
   (symlink or copy at launch). Smoke first: does the catalog appear under
   `--ignore-user-config` (codex_backend.py:656)? If not, drop that flag or enable skills in
   the per-arm `config.toml`. Then rewrite each `description:` as a trigger ("Use when ...").
   Set: `memory` (workshop turn; death forensics; recall after damage/stall), `reflexes`,
   `procedures`, `harness`, new `minecraft` (world knowledge, version-matched: MineStudio is
   1.16.5-era generation -- lava lakes y10, diamonds found at y4-9 in this seed), new
   `mining` (search doctrine: branch mining y5-12 at 2-cell spacing, change y after N
   empty cells, torches/return access budgeted). Harness skills stay immutable.
   2b. **Model-authored skills.** A second root `mine/skills/` in the catalog: a skill the
   model writes this turn is listed from the next turn (fresh session), and carried to the
   next life. This is the self-improvement lever that codex triggers for us. Needs the same
   smoke.
3. **AGENTS.md rewrite** (prompts.py `minimal_contract`, test in tests/test_memory_v2.py):
   a. `Routines` block, ~6 one-liners, each a trigger + a file + an action: workshop turn;
      after YOU DIED -> death sheet + digest line before rebuilding; damage of unknown source
      -> view the frame at the hit; three plans with the same EXPECT and moved=0 -> stop,
      grep own logs.txt, re-plan; before descending below y40 -> food, torches, return route;
      when writing notes.md -> update digest.md; before walking to a remembered place ->
      `--then-now`.
   b. Process rules from the wz1119 skill (their words, our failures): "Stop a roll when
      terrain, inventory, or UI differs from assumptions"; "Do not replay resource-consuming
      sequences automatically after stalls"; "Budget tools, materials, lighting, and return
      access before committing to longer route"; "Verify clearance before advancing. Use
      appropriate tool for visible material"; before crafting "inspect ingredients, recipe
      layout, quantities, cursor contents, destination slots".
   c. World knowledge: a short section or the `minecraft` skill -- ore y-levels and branch
      mining, hunger/regeneration (no natural healing below 18 food; kill animals early),
      portal frame geometry (10 obsidian without corners, 2x3 interior, light inside), Nether
      (blaze in fortresses, netherrack pickup), enderman/pearls, eyes -> stronghold, End.
      Game rules only, no coordinates: carry-only stands.
   d. Self-improvement stated: a hazard that hurt you with no reflex -> write the class; a
      question asked of your record twice -> write the script; a composition that worked
      twice -> a procedure; a procedure that worked across a life -> a skill in mine/skills.
   e. Move the procedures list (half of the 13.9 KB) to references/procedures.md (exists);
      target AGENTS.md <= 8 KB so a fresh session per turn stays cheap.
4. **MFM as the long-term store.**
   a. Re-feed the model's own `mine/digest.md` each turn beside `[WORKING]` (<= 20 lines),
      and enforce the 40-line cap on `working.md` the memory skill already states (harness
      truncates with a note; of1r's reached 68 KB).
   b. `[RECALL]` at plan grain: "the same PLAN/EXPECT N times with moved=0" (of3 30x, of3r
      15+); drop hotbar-class noise (episodes.py RECALL_IGNORE_KINDS).
   c. `episodes.py --ores` / `--y-profile`: where ore was seen or mined and at which y,
      this life and `--previous`; the question the budget is spent on.
   d. Frames in the across-life channel: digest lines cite an episode/frame path (of3r did
      once); `--then-now` on arrival is a Routine (3a).

## P2 -- harness bugs, neutral to the science (each with one V1 test)

- [x] agent.py:1991 cut-short note names mine_forward/strip_mine/stair_down, absent in
      atoms mode (300-400 per gpt-6 life): name the atoms or say nothing.
- [x] skills.py:92 `hit` reflex text "a mob is at you" -> "damage source unknown: fire?
      air? mob?"; add drowning and burning example scripts; water-on-fire in survival.md.
- [x] Navigator queues `pillar_up(6)` inside a shaft (agent.py:3115-3143; of1 death 3, of1r
      death 1 within 6 blocks): no pillar inside own excavation, or hide `go_to` in atoms mode.
- [x] GUI atoms: settle (watch ~10) after open before reading slots (six lives rediscovered).
- [ ] Entities: check whether the observation carries nearby entities at all (agent.py:439
      "never on the wire"); if the green layer never sends them, record that food must come
      from vision, not out of scope work.
- [x] codex_backend.py:860 compaction counter (moot under session-turns 1; keep for the
      one-thread mode's honesty).

## P3 -- gen 3 experiments (API cost: user approval; equal wall 12h, STEPS=100000)

| arm | model | seeds | frames | purpose |
|---|---|---|---|---|
| A  of3 lineage gen 3 | gpt-6-astra high (nyu) | of3 + of3r (lives_of carries both) | on | the result and the reuse story: diamond at y4-9 and the lava/obsidian site are in life 2's record |
| B  from-scratch control | gpt-6-astra high | none | on | attributes gen-3 gains to memory vs the new contract (gen 1 ran the old contract) |
| C  text-only control | gpt-6-astra high | of3 + of3r | off (view_image + zoom disabled, text queries kept) | the multimodal claim: portal/geometry stages, then-now uses, deaths at remembered sites |
| D  optional | gpt-6 medium / sol | of2(+r) / of1(+r) | on | breadth; sol only after the navigator fix |

Pre-registered read-outs (scripts/compare.py + new memory_use.py, selfimprove.py, stall.py):
milestones and step of each at equal wall; deaths and their distance to a recorded death;
steps iron->diamond (gen 2: 11.9k-22.4k) and diamond->portal lit; previous/ reads after turn
1, digest/notes re-reads, previous-life frames, then-now uses; new reflex classes, scripts
over the record, model-authored skills; plan-grain repeats; turn wall time and steps/turn.
Expected: A reaches diamond < 5k steps after the iron pickaxe and lights the portal; B tells
whether the contract alone lifts 10/24; C < A on the geometry stage if frames matter.

## Non-goals (unchanged)

No `--sites`, no `--seed-mine`, no harness-pushed facts about this world, no change to the
benchmark's green/I-O/scoring layer, no coordinates in any skill or contract text.

## Order of work

P0 as the walls stop (05:10 / 06:08 / 07:13). P1.1 and P1.2 smokes first (they decide the
shape of P1.3). P1.3-P1.4 and P2 in one implementation day on MFM-grid-merge-mcu, fast-forward
into MFM-grid/MCU, tests in MFM-grid/tests. P3 launches only on the user's go.
