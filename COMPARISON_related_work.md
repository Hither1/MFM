# MFM against MrSteve, WISE and MineEvolve (2026-09-07)

Three papers, all Minecraft, all about memory for long-horizon agents:

| | paper | venue | what the memory is |
|---|---|---|---|
| **MrSteve** | *Instruction-Following Agents in Minecraft with What-Where-When Memory* (Park et al.) | ICLR 2025, [openreview `CjXaMI2kUH`](https://openreview.net/forum?id=CjXaMI2kUH), [arXiv 2411.06736](https://arxiv.org/abs/2411.06736) | **Place Event Memory**: 20K frames of (MineCLIP embedding, pose, timestamp), hierarchically clustered place → event |
| **WISE** | *A Long-Horizon Agent in Minecraft with Why-Which Reasoning* (Cheng & Chen, HKUST-GZ) | [arXiv 2606.12852v1](https://arxiv.org/abs/2606.12852v1), 11 Jun 2026 | **Causal Event Graph**: VLM-extracted entity nodes with `CAN_OBTAIN` / `CO_OCCURS_WITH` edges and coordinates, on top of PEM |
| **MineEvolve** | *Self-Evolution with Accumulated Knowledge for Long-Horizon Embodied Minecraft Agents* (Xie, Chen, Weng et al.) | [arXiv 2603.13131v3](https://arxiv.org/abs/2603.13131), 10 May 2026, [code](https://github.com/xzw-ustc/MC-MineEvolve) | **Curated knowledge bank** of typed *skills* and *remedies* induced from typed execution feedback |

Two of the three are already load-bearing here. MrSteve is the source of our A-B-A tasks
(`tests/test_aba.py`) and of the recall probes' framing (`tests/test_recall_probes.py`,
`DESIGN_recall_probes.md`). WISE positions itself explicitly against MrSteve, so it is the
next move on the branch we already ported from. **MineEvolve evaluates on MCU** — the same
benchmark this campaign runs — and is therefore the only one of the three whose numbers sit
in nominally the same units as ours.

---

## 1. The one-paragraph difference

All three papers put memory *inside a trained control stack* and force retrieval on every
decision. MrSteve and WISE sit under a Steve-1/VPT policy in MineRL, retrieve by CLIP
task-alignment score, and navigate with a fine-tuned VPT-Nav. MineEvolve sits above
STEVE-1 as an LLM planner's knowledge store, retrieved under a token budget before every
planning call.

MFM puts memory *in the filesystem around a frozen model* and, until recently, only
**offered** it. There is no trained component anywhere in `mfm/`, no embedding index, and
no learned policy: an episode is a plan entry, the store is a directory, the index is
JSONL, and retrieval is `grep`. The chassis under it is symbolic macros, a cursor and a
hand-written vision stack, not Steve-1.

That single structural difference — *forced* retrieval into a learned controller versus
*offered* retrieval into a shell — explains most of what follows, including our largest
negative result.

---

## 2. Side by side

| dimension | MrSteve | WISE | MineEvolve | **MFM** |
|---|---|---|---|---|
| level of the stack | low-level controller | low-level controller | LLM planner + STEVE-1 | harness around a frozen frontier model, symbolic macro chassis |
| trained components | VPT-Nav (LoRA), MineCLIP, Steve-1 | + GPT-4o as VLM extractor (~16 calls/episode, $0.48) | STEVE-1 / GOAP; planner backbones swapped | **none** |
| unit of storage | one experience frame | one keyframe → entity node | one subgoal execution | one **plan entry** (a macro call, median ~40 ticks) |
| what is stored | video embedding + (x,y,z,yaw,pitch) + t | entity, causal edges, coordinates | `e_i = (z_i, y_i, Δs_i, Δv_i, f_i, p_i, ℓ_i)` | `observation/image.png` (hard link), `state.json`, `action.json`, `outcome.json`, an `index.jsonl` row with tags and x/y/z |
| lossy at write? | yes — DP-Means clustering, dedupe at cos > 0.9, evict oldest of largest cluster at 20K | yes — distilled to a graph by a VLM | yes — distilled to skills/remedies, `Curator` filters | **no** — full frames and per-tick state kept; the only lossless store in the four |
| retrieval | hierarchical: top-k event clusters by `CLIP_t(τ)·CLIP_v(e)`, then frames above h=0.3 | `λ·sim + (1−λ)·CausalMatch`, λ=0.5 | relevance under a fixed prompt budget `Σ tokens(k) ≤ B` | `tools/episodes.py` (`--last/--steps/--grep/--near/--tag`), plus `grep logs.txt` |
| who initiates retrieval | harness (Mode Selector, every decision) | harness (scheduler, every decision step) | harness (Curator, before every plan) | **the model, optionally** — plus three harness pushes we added later |
| revision of stored beliefs | eviction only | node status via VLM | `Curator`: schema / matchability / executability / specificity / conflict checks | none in `mfm` (the retired `worldmodel` arm had a confirmed/refuted/stale DAG) |
| across tasks | n/a | n/a | knowledge bank accumulates across episodes | `mfm/memory/carry.py`: `previous/<task>/`, merged index, `notes/` |
| benchmarks | MineRL, 100×100 and 200×200 maps | MineRL 1.11.2, 128×128 and 384×384 | **MCU**, 70-task tech-tree subset | **MCU** (diamond, dragon, ported A-B-A) **and CUA-KiCad** (GUI) |
| seeds / episodes | 100 episodes per agent | 50 episodes per condition | not clearly stated | **2 seeds per arm**, and we know that is not enough (§5) |

---

## 3. Where we already agree, having got there the hard way

**Push, don't offer.** Every one of the three papers makes retrieval unconditional. We
started from the opposite premise — give the model an addressable store and a query tool —
and the corpus says it declines:

- `tools/episodes.py` called in 25 of 89 turns on `lad2_mfm`, and **twice in the entire
  KiCad corpus** of ~2,000 turns, despite `AGENTS.md:95` advertising it.
- `--near` (spatial), `--tag` (semantic-ish), `--action`: **0 uses, ever**, in any run.
- Stored images opened by the model's own initiative: **0** on MCU; 0–8 `view_image`
  attempts per 24 KiCad tasks, and that counter is an upper bound (it counts attempts —
  `mfm-text` showed 8 with zero PNGs on disk).
- Log grepping outnumbers episode queries 5:1, and the *logbook control greps just as
  often* (129 vs 126), so the tool is additive, not a substitute.

Everything that has since shown any effect here is a push, not a pull: the `[RECALL]`
block (`mfm/memory/retrieve.py`), `[SEEN BEFORE]`, the `--refuse` governor vetoes. That is
the three papers' architecture, reached empirically. **This is the single most transferable
finding we have and none of the three papers reports it**, because none of them could —
their agents cannot decline.

**Stagnation detection is the same object in all four.** MineEvolve's

```
p_i = λ_x·Var(x)/(ε_x+Var(x)) + λ_v·‖Δv_i‖/(ε_v+‖Δv_i‖) + λ_g·p_i^goal
ℓ_i = 1[p_i < ε_p ∧ y_i = 0]
```

is, field for field, our `outcome.json` tags: coordinate variance ≈ `moved`/`stuck`,
inventory change ≈ `inventory_changed`, task-specific progress ≈ `milestone_transition`.
Their remedy trigger — failure rate over a window `h` above `η_fail` — is our streak rule
("an entry kind that changed nothing in its last 5 calls **anywhere**"). Their `Adaptor`
keeping the completed prefix `z_{1:i}` and repairing the suffix is our plan-queue veto.

The difference is provenance: **their remedies are induced by an LLM and validated by the
Curator; ours are hand-written and pure.** `test_descent_guard_is_a_pure_rule`,
`test_light_guard_is_a_pure_rule` exist precisely to keep them that way. Theirs scale to
failures we did not anticipate; ours are auditable and replayable over recorded runs
(the light guard was validated by replaying every descent in lad2–lad5 before it shipped).

---

## 4. Where we are genuinely different, and should say so

**4.1 We keep the pixels, and we have the only measurement that they matter.**
All three papers compress at write time. MrSteve's memory ablations (FM / EM / PM) vary
the *clustering structure*, not the modality — every variant still stores MineCLIP
embeddings, never frames. Nothing in the three papers asks whether the raw image carries
information the abstraction threw away.

Our channel test (`DESIGN_recall_probes.md` §11) does, and answers it. Twelve archived
frames, question computed arithmetically from the PNG (which half is brighter, HUD
excluded, ≥10 grey levels apart), so no text field can encode it and grading is not a
judgement:

| arm | correct | accuracy | p vs chance |
|---|---|---|---|
| `prior` (no store) | 5/11 | 45% | 0.73 |
| `mfm-text` (store, images deleted) | 6/9 | 67% | 0.25 |
| `mfm` (store with images) | **12/12** | **100%** | **0.0002** |

Pooled text arms 11/20, 55%, p = 0.41 — indistinguishable from chance. And the pixels were
*cheaper*: 18 s median per question against 70 s for the blind arm, which spends its budget
searching for something that is not there.

This is an existence proof no one in this literature has. It licenses exactly one claim —
the archived frame is a real retrievable channel the structured text does not duplicate —
and we should be careful not to over-claim it (§6).

**4.2 We compare memory *architectures*, not memory against no-memory.**
Each paper compares its own memory against a weaker one or against none. The MFM chassis
runs five paradigms under one controller with byte-identical prompts and pinned baselines:

- `logbook` — one append-only `logs.txt` (the PRO-LONG protocol)
- `mfm` — the episode store beside the log
- `vista` — the *conversation* is the memory; no shell, no filesystem, compaction to a fresh thread
- `arc` — the *workspace* is the memory; a coding agent whose only actuator is `./act`
- `worldmodel` / `wmlite` — a belief DAG with confirmed / refuted / stale status

That comparison is the thing this campaign can produce and none of the three can, because
their memory is welded to a trained controller. It also cuts the other way, honestly: it is
why our per-arm n is 2 seeds and theirs is 50–100 episodes.

**4.3 Two benchmarks, one memory package.** `mfm/` is shared between MCU (Minecraft) and
CUA-KiCad (a GUI/EDA benchmark). All three papers are Minecraft-only. The KiCad results are
also where the campaign's least comfortable finding lives: within a task, four memory arms
tie (official 0.361–0.389), and the log alone roughly doubles the memoryless baseline while
the store adds nothing — because a fresh per-task workspace with a screen that changes
every step gives the index nothing the log's last 15 lines do not have.

**4.4 The A-B-A port adds a control MrSteve does not need and we do.**
MrSteve's A-B-A is 20 task combinations (sparse A ∈ {water, beef, wool, milk}, dense
B ∈ {log, dirt, leaves, seeds, sand}), 100×100 map, 12,000 steps, 100 episodes. Our port is
six configs on MCU with two additions:

- an **ordering gate** (`after:` in the milestone rule): a goal banks nothing before its
  turn, or one trip to the pond scores both and the return journey the task exists to
  measure never happens;
- **sequential reveal**: the agent is not told at step 0 that the return is coming.

Neither matters for MrSteve, because Steve-1 is a policy conditioned on the current
instruction and cannot be told anything at step 0. Both matter enormously for an LLM agent,
where forewarning turns incidental encoding into deliberate encoding and voids the probe.
Three of our six configs are *inverted* (log first) because MrSteve's own three all put
`log` on the B slot. These are real methodological contributions to their task design.

**4.5 The probes go past MrSteve's §4.3 memory tasks.**
MrSteve's Find Water / Find Zombies' Death Spot / Find First-Visited House constrain memory
capacity (2,000 frames against a 3,000-step exploration) but leave the evidence in the
world. Our five probes (`vista`, `ledge`, `cavein`, `pantry`, `doppel`) add three rules:

1. **The evidence is destroyed before the query** — the tower collapses, the wall caves in,
   the chest is robbed, the water drains. Otherwise the probe measures navigation. A run
   where the agent was within 40 blocks when the alteration landed is **void**.
2. **Score the plan, not only the act** — the agent must *state* the coordinates / the wall
   and depth / the two rows before it moves. MCU's traversal is poor enough that an
   arrival-only score mostly measures walking.
3. **The query must not contain its answer** — enforced by tests, not by care
   (`test_reveal_states_no_coordinates`, `test_cavein_reveal_does_not_name_the_pattern`, …).

And one lesson the build probes taught that generalises to *their* memory tasks: **when you
destroy the evidence, enumerate everything else that correlates with the answer and
survives.** Our four "identical" cabins were discriminable by the hillside on the horizon
behind one of them and by the phase of the floor glowstone grid — both surviving the
drought, both found only by photographing the world. Find First-Visited House has the same
exposure and the paper does not say how it is controlled.

---

## 5. Where they are ahead of us

**Sample size.** MrSteve 100 episodes per agent, WISE 50 per condition. We run 2 seeds, and
lad4/lad5 — *the same arm, same code* — scored 90 and 60. Twenty-plus points between
identical arms means our single runs cannot be read at all, and our four-pair ladder result
(logbook 72.5 vs mfm 67.5 mean over lad8–lad11) is inside that noise. Any claim we make
about arm differences on MCU currently fails on n.

**Retrieval that is actually semantic.** We have no embedding index anywhere. Our
`[RECALL]` block retrieves by *recency and streak*, not by relevance to the current
subgoal — which is exactly why lad3's block, present in 67 of 68 prompts, **cannot be
credited**: no briefing cites an episode id or a streak, and a flagged action was used in
43% of following turns against 27% unflagged (confounded, since a flag marks a phase the
model is already in). WISE's whole contribution over MrSteve is this: retrieve by causal
relevance rather than feature similarity. We do not yet retrieve by either.

**Knowledge that improves.** MineEvolve's `Curator` validates, merges, deduplicates and
conflict-filters, and their `V_spec` explicitly rejects "try again" / "be more careful".
Our `EVIDENCE_capabilities.md` records that in the MFM arms nothing ever revised anything —
`hypotheses.n = 0` in all three ladder arms, belief revision **absent**, and the
`[unverified: …]` mark defined in both `discipline.py` files appears in **zero** artefacts
across the whole corpus.

**The ablation that separates accumulation from adaptation.** MineEvolve §4.4 freezes the
knowledge base at M ∈ {0, 50, 100, 200, 400} accumulated episodes and evaluates on held-out
hard tasks with no further updates. That is the clean way to show a memory *accumulates*,
and our carry arms have no equivalent: `mfm-carry` ran one task order, once, so its 0.542
relaxed against `prolong-carry`'s 0.556 is a single confounded ordering.

---

## 6. Two claims of theirs that our own history says to distrust

**Ablations attribute chassis bugs to the memory module.** WISE reports removing the Causal
Event Graph costs −46 points on ABC-Sparse. That number is measured against their own
exploration and control stack. We spent six waves (lad2–lad7) attributing a 2,650-step
"one plank short" loop to memory failure. It was a **vision bug**: shadowed spruce bark has
r median 33–42 and (r−b)/r ≈ 0.70, outside `find_tree_trunk`'s `r ≥ 35, rb < 0.75` bands,
so 92 of 97 recorded `harvest_tree` first frames ended "no trunk detected" while the model's
own view showed a full-height trunk one block left of the crosshair. Fixing it (MCU
`4aa167c`, then `10c7a51`) moved first-frame detection 38/92 → 68/92 and **invalidated the
baseline the whole ladder had been read against**. No ablation in any of the three papers
would have surfaced that, and every one of them is exposed to the same failure.

**"Memory helped" needs the encoding check, not just the score.** Our probe pilot
(§10 of `DESIGN_recall_probes.md`) found three of ten questions answerable with **no memory
at all** — a prior-only arm scored 3/10 — and that the store's own text leaks the answer
whenever the feature is task-relevant, because the action record describing the task
implies the scenery. Step 0 of any probe here is now: ask the questions with an empty
workspace and delete every question the prior arm gets right. None of the three papers
reports a no-memory-but-same-prompt control on its memory tasks.

---

## 7. What to take from each, concretely

**From MrSteve — an embedding index, and hierarchical place→event query.**
The cheapest real fix for §5's "retrieval is not semantic". We already store pose on every
index row (x/y/z on 426/426 rows in `lad2_mfm`) and a frame per episode; adding CLIP over
archived frames keyed by that position gives MrSteve's place→event structure with no
training. The corresponding harness change is the important half: make it a **Mode Selector
push**, not a flag on `tools/episodes.py`, because `--near` has never once been typed.

**From WISE — outcome-linked edges and opportunistic reordering.**
Our KiCad recall rows already carry `perception → intent → effect` with `dhash`/`next_dhash`
confirmation (`mfm/memory/recall.py`), which is a two-node causal chain. The MCU store has
no equivalent; the `broke` tag added in MCU `03a386b` is the first outcome-typed edge there.
WISE's `CAN_OBTAIN` is the generalisation. Separately, their Opportunistic Task Scheduler
(re-prioritise the subgoal queue when a causally relevant entity comes into view) is
near-free on our chassis — we already own a plan queue and a governor that can veto it —
and it targets a failure we have measured: lad3 placed the crafting table at y68, descended
without it, and burned 27 turns and 4,800 steps climbing 56 blocks back.

**From MineEvolve — the Curator, and the accumulation curve.**
Two things. (a) Induce remedies instead of hand-writing them, but keep the *validation*
gate: schema completeness, executability against the actual procedure set, and a `V_spec`
that rejects generic advice. Our five guards took a wave each to write and validate; a
Curator-shaped inducer would let the store propose the sixth. (b) Run their §4.4 design on
our carry arms — freeze `previous/` at M ∈ {0, 5, 10, 20} finished tasks and evaluate on
held-out KiCad tasks. It is the only clean way to show carry accumulates, and it is a few
hours of re-running, not new machinery.

---

## 8. The comparison we cannot yet make, and how to get it

MineEvolve reports on **MCU**: a 70-task subset of the tech-tree benchmark, seven groups,
weighted overall SR. Best overall 54.93 (GPT-5.5 planner), Hard Avg 40.23, Diamond group
17.06 for the full system. Ours are not comparable to those numbers today, for three
reasons, in increasing order of difficulty:

1. **Different metric.** They score binary success over 70 tasks. We score milestone
   fraction on one long task (8/10 = "80" on diamond). Fixable by scoring their way.
2. **Different task set.** We run `mine_diamond_from_scratch`, dragon, and six ported A-B-A
   tasks. Their 70-task subset is public with the code. Fixable by running it.
3. **Different controller.** They use STEVE-1 (or GOAP) as the low-level executor; we use a
   symbolic macro chassis with hand-written vision. A head-to-head number would compare
   controllers, not memories. **Not** fixable — and it is the reason to report the
   comparison as "same benchmark, different stack" rather than as a leaderboard row.

The honest move: run their 70-task subset on our ladder (`logbook`, `mfm`, `vista`, `arc`)
with their weighted-SR metric, and report it beside their table with the controller
difference stated. That gives the campaign its first externally-anchored number, which it
currently does not have, and it is the single highest-value experiment on this list.

Two confounds to clear first, both already known: the `codex exec`
`project_doc_max_bytes` truncation (32 KiB of an ~80 KB brief — every codex-exec arm on the
ladder has been running without the procedures reference, while `vista` saw all of it), and
the trunk-detector re-baseline. Neither is a memory question and both change every number.

---

## 9. One-line positioning

> Prior work makes agent memory a trained, compressed, always-queried component inside a
> learned controller. MFM makes it an uncompressed, addressable, model-facing filesystem
> around a frozen model — which is what lets us measure that the model does not query it,
> that the archived pixels carry a channel the text does not, and that four memory
> architectures tie on task score while a single vision bug moved every number in the
> campaign.

---

*Sources: [MrSteve (OpenReview)](https://openreview.net/forum?id=CjXaMI2kUH) ·
[MrSteve (arXiv)](https://arxiv.org/abs/2411.06736) ·
[WISE](https://arxiv.org/abs/2606.12852v1) ·
[MineEvolve](https://arxiv.org/abs/2603.13131) ·
[MineEvolve code](https://github.com/xzw-ustc/MC-MineEvolve).
Internal evidence: `EVIDENCE_capabilities.md`, `DESIGN_recall_probes.md`,
`PLAN_episodic_memory.md`, `tests/test_aba.py`, `tests/test_recall_probes.py`.*
