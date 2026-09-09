# Does the harness and do the trajectories reflect the method? (2026-09-09, 20:30)

The user's priorities, in order: (1) the result must be good; (2) the multimodal memory
must be useful -- the method's centre; (3) memory reuse must be useful -- the performance
lever; (4) the model's autonomy -- the reason for a coding agent on a strong LLM. Below,
what the code and the two comparable lives (of3r = gen 2, 16/24; of3g = gen 3, 9/24 at
step 11k, running) show for each, and where they contradict the priority.

Sources: turn_profile.py and look_cases.py over output/of3r_mfm and output/of3g_mfm;
gen3_vs_gen2_2026-09-09.md; the contract diff; logs.txt counts (this file's tables).

## 1. The result

| | of3r (gen 2) | of3g (gen 3) |
|---|---|---|
| milestones | 16/24 at 41.6k steps, 13 h | 9/24 at 11.2k steps, 7 h 20 (running) |
| steps per turn / turn interval | 83 / 68 s | 42 / 84 s |
| deaths | 1 (Nether) | 0 |

What serves the result in the harness: the milestone ledger and [STATE]/[INV]/[EVENT]
truth every entry; atoms with closed-loop aiming/walking; entry cut-short on break/hit;
reflexes (14 firings in of3r, 8 in of3g); the [RECALL] stall lines; OBSERVED vs EXPECTED.
What hurt it in gen 3: the contract (the false persistence sentence, the per-turn digest
feed, the wz1119 step rules) halved the steps per turn and doubled the turn time; fixed
in gen-3b (MCU cf86f15a), being smoked. The provider's speed (OpenRouter vs nyu) is
unmeasured. The wall (12 h) caps steps: at gen-3 pace a life ends at ~18k steps, of3r
needed 41k for 16/24; if gen-3b does not recover the pace, priority 1 argues for a longer
wall or the faster route before any further method work.
Alignment: partial. The harness has the machinery; the gen-3 contract worked against it.
Nothing in the harness measures the result's drivers per turn -- turn_profile.py now does.

## 2. Multimodal memory

What exists: every episode keeps its frame (episodes/ep_x/observation/image.png); the
hires record (640x360 JPEG per step, never shown); `view_image`, `tools/zoom.py`,
`episodes.py --then-now` (a THEN/NOW sheet against any recorded frame, this life's or a
previous one's), `--sheet`; the [RECALL] lines cite frames; the digest may cite frames.

| | of3r | of3g |
|---|---|---|
| look cells per turn | 0.01 | 0.60 |
| turns with a then-now sheet | 2 | 146 |
| digest lines citing a frame | 3 | 13 |
| notes lines citing a frame | 0 | 2 |

Gen 2 barely looked: 2 then-now sheets in 520 turns; its result came from text (logs,
coordinates). Gen 3 looks every other turn and the looks decided real things: the wolf
not attacked, the pink sheep taken for food, the rim-overlap diagnosis, life 1's iron
entrance matched by a then-now against a frame two lives old (7/24), "DIAMONDS CONFIRMED:
life2 step 17921 ep_000952 ... Frame viewed: diamond face at head level" in the digest.
But most of the 146 sheets are arrival checks on a one-hop walk (T053-T062, T118-T145:
"the comparison confirms a one-block grass rise"), where [STATE] already said it.
Contradictions with priority 2:
- The harness does not know which looks mattered. There is no read-out that ties a look
  to a changed plan or a banked milestone; look_cases.py (2026-09-09) scores that after the
  fact, nothing does it live.
- Frames are retrievable by step, place, tag and text only. Nothing describes a frame's
  content in the index (what was visible), so "where did I see lava / a cave mouth / an
  animal" is answered by opening frames one by one; the model's answer was to write
  step-notes with poses into the digest.
- The across-life channel is one operation (then-now). No "show me the frames of life 2
  between steps A and B as a sheet" for a stage (P1.4d wanted digest lines to cite
  frames; they do now, 13 of them).
- The multimodal claim is unmeasured: P3-C (text-only control, same seed) has not run.
Alignment: the channel exists and gen 3 uses it, sometimes decisively, mostly
ritually. Useful means "changed a decision"; that needs (a) the look budget in the
contract (gen-3b: one per plan), (b) a live counter of looks that preceded a plan change
or a milestone, (c) the text-only control.

## 3. Memory reuse

What exists: previous/life_i/ (complete records, hard-linked, index enriched with
events/inventory deltas), episodes.py --previous/--root with --grep/--ores/--y-profile,
the workshop turn, mine/ carried (procedures, reflexes, digest, notes), model-authored
skills carried.

| | of3r | of3g |
|---|---|---|
| turns querying previous/ | 3 | 85 |
| previous-life procedures copied / called | 0 / 0 | 2 / 0 |
| own procedures written / called | 6 / 105 | 2 / 0 |
| digest size | 2.1 KB (13 lines) | 122 KB (245 lines) |
| first ore via a recorded place | -- | iron at step 6565 via life 1's entrance |

Gen 2 reused little explicitly (3 previous queries in 520 turns) and still set the
record; gen 3 reuses constantly (85 query turns) and is slower. The reuse that
worked: the iron entrance; the digest's diamond line (life 2's y=11 face with a frame)
is the next test -- reaching it fast is what P3 pre-registered ("diamond < 5k steps
after the iron pickaxe"; of3g has the pickaxe since step 7880). The reuse that failed:
the digest as a per-turn log (fixed in gen-3b), copied procedures never called (the
stage has not come), the surface walk to a remembered place at one hop per turn
(a navigation problem: go_to over terrain with trees and ledges, not a memory problem).
Alignment: the store and the tools are right; the contract made the model spend the
reuse budget on re-confirming rather than on acting. Priority 3 is measured by the
pre-registered read-out (steps iron -> diamond, gen 2: 11.9k-22.4k) and of3g will give
its number tonight.

## 4. Autonomy

What exists: atoms instead of macros; the model's own procedures (stdin state, output
shapes), reflexes (tick layer, none installed), skills (catalog), working/digest/notes;
no harness-pushed facts.

| | of3r | of3g |
|---|---|---|
| own procedure calls | 105 | 0 |
| raw-key entries vs atom calls | 940 vs 1721 (35% raw) | 584 vs 344 (63% raw) |
| model-authored skills | 0 | 0 |
| reflexes written / firing | 4 / 14 | 4 / 8 |

Gen 2 shows autonomy paying: six procedures (west_stairs, west_level, obsidian_hold,
torch_west_relay...) called 105 times, i.e. the model built its own macro layer. Gen 3
so far plays with raw keys (63%), calls no procedure of its own, wrote no skill. The
gen-3 contract told it, in 7 rules and 7 routines, how to play -- which is the
opposite of priority 4 -- and the model obeyed. Gen-3b removes the step rules, keeps
the atoms, and attaches "improve yourself" to the milestone moment.
Alignment: the harness design (atoms, own code, no facts) is right for priority 4; the
gen-3 contract text was not. Missing: any signal to the model that a composition it
just ran twice is a procedure candidate (the harness knows the repeat; it could say so
in one [NOTE]).

## What contradicts the ordering today

1. Priority 1 is currently lost to the contract, not to the method: pace. Gen-3b is the
   fix; if the smoke does not show >= 80 steps per turn, the next change is the contract
   again (fewer words), not the memory.
2. Priority 2 is exercised but not measured; the text-only control (P3-C) and a live
   "look -> decision" counter are the two missing pieces. Ritual looks cost turns
   (priority 1) without serving priority 2.
3. Priority 3 works where a place was recorded with a frame and coordinates (iron,
   diamonds); the digest discipline decides whether the next life inherits facts or
   a 122 KB log.
4. Priority 4 was reduced by the gen-3 contract; of3r is the evidence that the model
   builds its own layer when left to.

## Concrete next steps, in priority order

1. Read the gen-3b smoke by turn_profile.py: steps/turn, cells/turn by kind, digest
   size; launch of3g2 (same seed) only if pace recovered.
2. Add the live look read-out: in the report, per look turn, whether the next plan's
   target changed or a milestone banked within 3 turns (look_cases.py logic, moved into
   the harness audit).
3. Run P3-C (text-only, seed of3r) once gen-3b is stable: the multimodal claim needs it.
4. A [NOTE] when the same composition ran twice: "this is a procedure candidate" -- the
   autonomy lever the harness can pull without prescribing play.
