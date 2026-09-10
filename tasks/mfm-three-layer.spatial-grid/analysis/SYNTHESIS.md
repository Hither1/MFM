# Systematic problems across all mfm arms (og1-og22) -- checked synthesis, 2026-09-08

The five sub-reports in this directory (memory-usage, failure-taxonomy, memory-reuse, timelines,
recall-usage) were written by read-only subagents in ~5 min each and contain errors; only the
numbers below were re-checked. Corrections: RECALL is NOT off (3,906 blocks in 3,938 turns since
og6; the sub-report grepped logs.txt, the block lives in codex_turns/turn_*.prompt.txt);
deaths are NOT 80% lava (11/20 by the death frame, see B); the digest IS re-read (og19 32 of
177 turns); og9/og12/og13 DID enter the Nether. Death-frame numbers come from
`vision.fire_fraction/lava_fraction` on `episodes/ep_*/observation/image.png` at the death step.

## A. Multimodal memory: what the frames are used for

| Fact | Number | Source |
|---|---|---|
| view_image per turn, all arms | ~0.1 | vision_use.py over codex-homes rollouts |
| share of looks that zoom the current view (GUI, inventory, trunk) | ~75% | same |
| looks at this life's episode frames, all arms together | 32 | same (og14 12, og18 11, og19 6, og15 3) |
| looks at a previous life's frame, all arms together | 3 | same (og15 only) |
| looks BEFORE a walk to a remembered place | 0 found | memory-usage.md §5d, recall-usage.md §3 |
| RECALL block present | 3,906 / 3,938 turns | worldmodel_report.json mfm.recalls; prompt files |
| plans that re-target a place RECALL cited (within 8 blocks) | 0 / 30 sampled | recall-usage.md §2 |
| plans that mention the recall at all | ~13% sampled | same |
| streak warnings ("changed nothing") heeded implicitly | ~60-80% (estimate) | same |
| turns touching mine/digest.md after writing it | og19 32/177, og20 30/212, og21 18/128, og22 5/111 | grep digest codex_turns/*.events.jsonl |

Reading: the frame store works as a **post-hoc diagnostic** (after several null turns) and as a
**GUI magnifier**; it is never a **memory** (recognise a place, check what a cited entry saw,
compare then/now). RECALL is read for "what to stop doing", never for "where to go".

## B. Deaths (20 across 20 arms): the frame knew, the text did not act

Death frame classification (fire overlay >= 0.30 or lava >= 0.17 at the death step):

| Kind | Deaths | Arms |
|---|---|---|
| lava / fire | 11 | og16#2, og8#2, og8#3, og9#1, og9#3, og10#1-#3, og11#1, og12, og13#1 |
| melee (sword/flee/fight notes, no fire) | 5 | og16#1, og8#1, og13#2, og19#1, og19#2 |
| no fire, no fight note (fall/unknown) | 4 | og6, og9#2, og11#2, og3 |

- First fire frame -> death: og13#1 18777->18818, og11#1 10289->10326, og9#3 26903->26939
  (~40 steps, inside one turn). The model cannot act; only the runner or the approach can.
- **Repeat deaths at recorded places**: og10 died 3x within 5 blocks of (-2958, 9, -5511) at
  8870 / 35834 / 45621 with 44 log lines naming that pool in between ("Water was poured at the
  old lava site near (-2958, 9, -5511)"); og8 died twice 1 block apart (14349, 18261); og9#1,
  og13#1, og12 died at the same Nether lake by the portal landing (7-60 blocks apart, different
  lives). The place was in the text memory; nothing turned it into avoidance.
- Runner lava branch (agent.py:776-930, since 2026-09-07) already says "you are BURNING ...
  DOUSING"; three escapes failed for want of a bucket ("no water bucket in your hotbar":
  og16 1, og13 3, og10 1, og8 1).
- LAVA AHEAD guard fired 0 times in every atoms/own arm (og14, og15, og19-og22) vs 6-25 in the
  macro arms; og19 still got 2 DOUSED. Coverage of the guard under atoms is unverified.

## C. Cross-life reuse: coordinates transfer, nothing else does

- Carry arms read previous/ as text in 12-35% of turns; digests are written at turn 1.
- Used: og19 iron at the recorded vein within 1 block (logs.txt:1007), og9 obsidian at the
  recorded cell (-2990, 11, -5560).
- Not transferred: procedures (every life rewrote its own: og14 7 scripts, og15 9 new, og20 6
  with one copied `gravel_cycle`, og21 6 new, og22 3; `north_stair` rewritten in og14/og21/og22
  with 55/46/27 calls), routes (grid.jsonl never read), recognition (3 previous-frame looks).
- Outcome: no carry arm reached obsidian faster than the from-scratch og12 (6,134): og9 8,675,
  og4 11,883, og15 13,251; og14 (scratch) 15,505.

## D. Where the step budget goes (timelines.md, ledger)

- diamond -> flint_and_steel median ~8k steps (worst 31k, og16); flint -> obsidian median
  ~3.5k (worst 34k); og10 19k steps after obsidian without a portal; og9 12k steps after
  entering the Nether without a blaze rod; best arm 16/24 (og9).
- Standing-still churn: governor "changing nothing" 8-23 per 1k steps; ~100 refusals per arm;
  searching/orientation 35-47% of actions.
- Steps per turn fell 158 (og10) -> 41 (og22); milestones per turn rose 0.043 -> 0.118; API
  cost per step x4. og22 (gpt-5.6-sol xhigh) leads og21 at equal steps.

## E. Plan (priority order; each item names its metric)

1. **Frames into decisions** (text + tools, no new arm design)
   a. `[OBSERVED]` lines carry the frame path of the entry's end and of the event that stopped
      it; the compare line must name a visible change (VISTA's observe step).
   b. RECALL here-before lines become actionable: bearing + distance + what happened + frame;
      drop the milestone line (redundant with [STATE]).
   c. `tools/episodes.py --then-now <ep>`: remembered frame beside the current view, labelled.
   Metrics: episode/previous-frame looks per 1k steps (now 35 total across all arms); RECALL
   re-target rate (now 0/30); remembered-site re-open misses.
2. **Hazard memory -> avoidance** (the runner within a life; the model across lives)
   a. Within-life: cells of deaths, LAVA AHEAD and DOUSED become forbidden for go_to /
      dig_down / mine_forward / moving atoms; a plan aimed within 6 blocks gets "you died here
      at step X" + the death frame path.
   b. Cross-life: the memory skill gives a template `mine/reflexes/known_hazards.py` the model
      fills from its digest (no harness push of previous-life facts).
   c. Stage: LAVA AHEAD under atoms/own (0 fires in six arms).
   d. Reflex note: below y 40 near recorded lava without a water bucket in the hotbar.
   Metrics: repeat deaths within 8 blocks of a recorded death (now 3); deaths per 10k steps.
3. **Death episode**: frames of the last 8 ticks + last 20 notes + cause (fire/lava vs melee vs
   fall, from fire_fraction/lava_fraction) written as a `death` episode, attached at respawn,
   listed in the digest. The classifier above is the prototype.
4. **Reuse beyond coordinates**: an offline distiller pass by the model between lives (previous
   logs + episodes + death episodes -> GUIDE.md, procedures kept under their names with call
   stats, candidate reflexes); previous-life frames indexed by milestone/place in the digest.
   Metrics: steps to obsidian vs 6,134; procedures reused vs rewritten; previous-frame looks.
5. **Phase bottlenecks** (not memory): water/gravel/flint, portal -> Nether, blaze. Own track.
6. **Evaluation**: fixed model (gpt-5.6-sol xhigh), same seed; og23 = og21 + (1), og24 = +(2)(3),
   og25 = +(4); pairs against og21/og22. Prediction-match rate from `OBSERVED vs EXPECTED` lines
   (94-426 per arm available) as the world-model metric.
