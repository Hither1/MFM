# Plan: multimodal memory v2 (2026-09-08, draft for the user's approval)

Evidence: `analysis/SYNTHESIS.md` (checked numbers over og1-og22). References: VISTA
(vista-research.github.io; expect/observe, inspect-with-question, GUIDE/WORKING, compaction
checkpoint, minimal prompt) and arXiv 2606.00579 (coding agents on omni tasks; "insufficient
exploration of modal content"; log-driven self-distillation by a separate agent beats human-written
skills; process-level judge; reasoning effort matters).

Anchor (unchanged): can the mfm arm turn its filesystem memory (log + frames + previous lives) into
decisions -- fewer repeat failures, fewer steps to obsidian/portal -- with the model, not the
harness, digesting memory. Non-goals: benchmark green/I-O/scoring layer; `--sites`; harness-pushed
previous-life facts into the prompt.

Priority = (problem size in the data) x (1 / cost), dependencies respected.

| # | Item | Fixes (evidence) | Source | Change surface | Metric |
|---|---|---|---|---|---|
| 1 | Metrics kit + process judge | nothing measured yet: 35 memory looks total, 0/30 recall re-targets, no match-rate parser | paper (judge) | `scripts/`: match-rate parser, recall re-target, repeat-death, procedures reused/rewritten; judge prompt over codex_turns, calibrated on 30 hand-labelled turns | the kit runs on og14-og22 and reproduces SYNTHESIS numbers |
| 2 | Frames into decisions | frames used as GUI magnifier / post-hoc only; RECALL never re-targets | VISTA (observe visible changes, inspect question) | `_expect_block` carries end/event frame paths + "name a visible change"; RECALL here-before -> bearing, distance, outcome, frame; drop milestone line; `episodes.py --then-now <ep> --q "..."` (question logged) | memory looks per 1k steps; recall re-target rate; re-open misses |
| 3 | Session continuation checkpoint | re-testing after resets; VISTA blocks compaction until WORKING.md holds plan/prediction/contradictions/frame refs | VISTA | last turn of a session: write `mine/working.md`; first turn of the next: attach it; GUIDE (digest) vs WORKING split named in the memory skill | first-turn-after-reset re-tests (judge label) |
| 4 | Hazard memory -> avoidance | 3 repeat deaths at recorded places (og10 x2, og8), Nether lake x3 across lives; 5 escapes without bucket; LAVA AHEAD 0 fires under atoms | our data | runner: within-life forbidden cells (deaths, LAVA AHEAD, DOUSED) for go_to/dig_down/mine_forward/moving atoms, note + death frame when a plan aims within 6 blocks; skill template `mine/reflexes/known_hazards.py` for cross-life (model fills from digest); stage for LAVA AHEAD under atoms; bucket-in-hotbar reflex note below y40 near recorded lava | repeat deaths within 8 blocks (now 3); deaths per 10k steps |
| 5 | Death episode + classifier | 11/20 deaths fire/lava by frame, 40 steps to death; text never turned into avoidance | our data + paper taxonomy; VISTA lossless frames (local) | `death` episode: last 8 frames sheet, last 20 notes, cause from fire/lava fraction; attached at respawn; listed in digest | every death classified; digest cites it |
| 6 | Separate distiller pass between lives | coordinates transfer, procedures/routes/recognition do not; every life rewrites `north_stair`; no carry arm beat scratch og12 to obsidian | paper Finding 4 (separate agent over raw traces > self-iteration > human) | model-run pass with no game context: previous logs + episodes + death episodes -> `mine/GUIDE.md`, procedures kept under their names with call stats, candidate reflexes, frame index by milestone/place; player reads GUIDE at life start | steps to obsidian vs 6,134; procedures reused vs rewritten; previous-frame looks |
| 7 | Phase bottlenecks (non-memory) | diamond->flint median ~8k, flint->obsidian ~3.5k, 19k after obsidian w/o portal, 12k in Nether w/o blaze | our data | separate track: water/gravel/flint, portal->Nether (Nether lock untested), blaze | segment steps |
| 8 | Minimal-prompt ablation | contract keeps growing; VISTA wins with 5 sentences + memory tools | VISTA | thin + expect + skills, most rules removed; safety by runner reflexes only | milestones/step vs og21; deaths |

Protocol: fixed model gpt-5.6-sol xhigh, same seed, pairs against og21/og22. Arms: og23 = og21 +
(2)(3); og24 = og23 + (4)(5); og25 = og24 + (6). Item 1 runs before og23 and on every arm after.
Item 7 is its own track; 8 last.

Decisions assumed unless the user objects: within-life hazard cells are a runner reflex (allowed);
cross-life hazards reach the runner only through the model's own reflex file; the distiller is the
same model family as the player, its cost counted in the arm's budget.

## Decision 2026-09-08 03:3x (user)

Do items 1, 2, 3, 6, 8; build them all, then launch (not one arm per change). Items 4, 5, 7 are
NOT harness work: the model writes them itself; the harness only supplies examples and meta-level
hints in the skills package (hazard-memory reflex template, death-forensics example, phase-bottleneck
hint with the data). Arms after the build: og23 = og21 setting + (2)(3)(6) + the new skill examples on
gpt-5.6-sol xhigh; og24 = og23 + (8) minimal prompt. Item 1's parsers run before launch; the judge
calibration runs while the arms run.
