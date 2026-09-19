# Running the three MFM ablation arms (2026-09-19)

Three arms that each remove ONE thing from the MFM memory arm on
`mine_diamond_from_scratch`. Everything else -- chassis, procedure set, caps, session
policy, model, frames -- is the reference arm's, so the difference against it is the
ablated mechanism and nothing else.

| arm name | flag | condition | what it removes | what it keeps |
|---|---|---|---|---|
| `g4_mfm_gpt6_diamond_noimg` | `--no-history-images` | without historical images | every frame of an earlier moment: no `episodes/*/observation/image.png`, carried lives arrive without frames, `--sheet`/`--then-now` refuse, `[RECALL]` cites no frame, the event sheet is off, `hires/` is written unreadable | the CURRENT view attached every turn and `tools/zoom.py` cropping it (perception is NOT ablated), all text, state, index, notes, consolidation |
| `g4_mfm_gpt6_diamond_flat` | `--flat-retrieval` | without structured episode retrieval | `tools/episodes.py` and the `[RECALL]` block | the same `episodes/`, frames and `index.jsonl` (one JSON line per entry, in order, with coordinates, action, outcome, note, events, paths), read with `rg`/`grep`; image inspection; consolidation |
| `g4_mfm_gpt6_diamond_nocons` | `--no-consolidation` | without long-term consolidation | persistence of anything under `mine/`: before every turn it is reset to what the life began with, plus `mine/working.md` and byte-identical copies of the harness example scripts. Notes, digests, edited or new procedures and reflexes are removed and never run | the complete episodic archive, structured retrieval, `working.md` (the current plan), the built-in action tools |

The comparator is the existing no-carry reference life
(`g4_mfm_gpt6_diamond_v7`, score 100, and its v1-v8 siblings, 90 x6 / 60 / 100).
No carry on any ablation arm: do NOT pass `--seed-memory`.

## 1. Code state (exact)

    MCU   git@github.com:Hither1/MCU.git   branch gen4-min-vista   commit b931052
    MFM   git@github.com:Hither1/MFM.git   branch kicad-results-0913  commit 8645742

`gen4-min-vista` is the branch that carries both the ablations and the v7 diamond
harness (shaft_down, aim_speckles, the raw-hold ore watcher). **Branch `gen4-min` and the
collab host's `MFM-grid-min-mcu` do NOT have the ablation flags** -- the purple agent
will reject `--no-history-images` as an unknown argument. Check the branch first.

    git -C <mcu> fetch origin && git -C <mcu> checkout gen4-min-vista && git -C <mcu> log --oneline -1   # b931052
    git -C <mfm> fetch origin && git -C <mfm> checkout kicad-results-0913 && git -C <mfm> log --oneline -1  # 8645742

Not pushed, and not needed for a 12,000-step diamond run: the streaming `RecordCallback`
and the `MCU_WORLD_SEED` plumbing live only in the FASRC working tree. The old recorder
buffers ~0.69 MB/step, which is ~8 GB over 12,000 steps -- fine inside 48 GB, and the
world seed is random in every run of this series anyway.

## 2. Prerequisites

- **A working model account.** gpt-6-astra high through **codex CLI 0.153 or newer**
  (0.149 refuses the model id). Either a ChatGPT-plan login or an OpenRouter key; see
  the MODEL line below. Our own FASRC credential is revoked, which is why this is being
  handed over -- please use your own.
- The MCU python env (`<mcu>/.venv`) and the MineStudio engine as that checkout's
  `mcu_worldmodel/setup_env.sh` builds it; java, xvfb.
- ~48 GB RAM and 12 CPUs per arm; about 1.5-2 h wall per arm at 12,000 steps.
- **One arm per node.** Two engines on one host race for the X display and
  `/tmp/lwjgl` and one of them silently scores 0.0 within 90 s.

## 3. Launch

`MFM_ROOT` must point at the MFM checkout: `run-arm.sh` puts it on `PYTHONPATH` so the
live `mfm` package is used. Without it the frozen copy inside `<mcu>/.venv` is imported
and the flat arm dies on a `TypeError` about `EpisodeStore(tool=...)`.

    export MCU_ROOT=/abs/path/to/MCU            # at gen4-min-vista b931052
    export MFM_ROOT=/abs/path/to/MFM            # at kicad-results-0913 8645742

The model channel, one of:

    MODEL="--model gpt-6-astra --reasoning-effort high"                                          # a ChatGPT-plan codex login
    MODEL="--model openai/gpt-6-astra --reasoning-effort high --base-url https://openrouter.ai/api/v1"   # an OpenRouter key

The shared flag set (the reference arm's, verbatim):

    BASE="--expect --frames --retrieval --no-event-sheet --frame-size 320x180 --thin --minimal --atoms --own --own-reflexes --no-harness-reflexes --skills"

### Direct (any host, no scheduler)

Ports must differ between concurrently running arms.

    cd "$MCU_ROOT"
    # 1. without historical images
    scripts/run-arm.sh --arm g4_mfm_gpt6_diamond_noimg --agent mfm \
      --task mine_diamond_from_scratch --steps 12000 --green-port 9870 --purple-port 10870 \
      --cli codex --session-turns 0 --compact \
      --wm-extra "$MODEL $BASE --no-history-images"

    # 2. without structured episode retrieval  (NOTE: --retrieval is removed; it is
    #    computed from the index this arm takes away, and the agent refuses the pair)
    scripts/run-arm.sh --arm g4_mfm_gpt6_diamond_flat --agent mfm \
      --task mine_diamond_from_scratch --steps 12000 --green-port 9871 --purple-port 10871 \
      --cli codex --session-turns 0 --compact \
      --wm-extra "$MODEL ${BASE/--retrieval /} --flat-retrieval"

    # 3. without long-term consolidation
    scripts/run-arm.sh --arm g4_mfm_gpt6_diamond_nocons --agent mfm \
      --task mine_diamond_from_scratch --steps 12000 --green-port 9872 --purple-port 10872 \
      --cli codex --session-turns 0 --compact \
      --wm-extra "$MODEL $BASE --no-consolidation"

Run a 150-step smoke of one arm first (`--steps 150`, a throwaway `--arm` name): it
exercises the contract, the skills package and the model channel in ~10 minutes.

### SLURM

`tasks/mfm-three-layer.spatial-grid/scripts/launch_g4_fasrc.sh` wraps the above with a
wall cap and job-id-derived ports:

    ABL=noimg  ACCOUNT=nyu bash .../launch_g4_fasrc.sh mfm diamond
    ABL=flat   ACCOUNT=nyu bash .../launch_g4_fasrc.sh mfm diamond
    ABL=nocons ACCOUNT=nyu bash .../launch_g4_fasrc.sh mfm diamond

It is written for FASRC: partition `sapphire` in `arm_wall.sbatch`, the codex binary at
`$LAB_USER_ROOT/codex-node-0.153/bin/codex`, the OpenRouter key at
`~/.codex-eval/openrouter.env`, `ACCOUNT=nyu` reading `~/.codex/runtime-home/auth.json`.
Edit those for another cluster, or use the direct commands above inside your own batch
script. `EXCLUDE=n1,n2` keeps a job off given nodes; `DRY=1` prints the sbatch line.

## 4. Check it is really running (do this at +3 minutes)

The failure that cost us this wave: every codex turn returned a revoked-token error in
under five seconds, the world kept stepping, and nothing in the arm's own log said
"error". Check the first turn's event stream, not the purple log:

    head -5 "$MCU_ROOT/output/<arm>/episode_001/codex_turns/turn_0001.events.jsonl"

It must contain `turn.completed` / assistant content. If it contains `turn.failed` with
an auth message, **kill the job**: the arm is stepping with no model behind it.

Two more, from the purple log `$MCU_ROOT/logs/<arm>_purple.log`:

    grep -o 'no_history_images=[A-Za-z]* flat_retrieval=[A-Za-z]* no_consolidation=[A-Za-z]*' <log> | head -1
    grep -c 'produced no actions.json' <log>      # a handful is normal; hundreds means the model is not answering

Exactly one of the three must be `True`, matching the arm name.

## 5. What to send back

The whole `"$MCU_ROOT/output/<arm>/"` directory per arm (it holds `result.json`,
`worldmodel_report.json`, `episode_001/memory/` and the copied `codex_sessions/`
rollouts), plus `"$MCU_ROOT/logs/<arm>_purple.log"`. The rollouts are what the retrieval
and image-use measures are computed from -- they are node-local during the run and are
copied beside the output on exit, so please do not prune them.

Beside each score, record: the chassis commit (`git -C $MCU_ROOT rev-parse --short HEAD`,
expect b931052), the model id and reasoning effort, the account route, and the CLI
version (`codex --version`). The CLI version is a known wave-level confound.

## 6. Reading the result

`result.json` carries the score (10 milestones, 10 points each).
`worldmodel_report.json` carries the ablation's own accounting:

    mfm_options.ablations              ["no_history_images"] | ["flat_retrieval"] | ["no_consolidation"]
    mfm.history_images                 false on arm 1
    mfm.structured_retrieval           false on arm 2
    mfm.history_image_views            past frames the model opened -- must be 0 on arm 1
    mfm.record_search_calls            greps over the record -- the flat arm's retrieval cost
    mfm_options.consolidation          {turns, removed, restored} on arm 3
    mfm_options.history_image_sweeps   images the model saved and the harness removed, arm 1

`tasks/mfm-three-layer.spatial-grid/scripts/image_age.py <output/arm>` classifies every
`view_image` call and reports the age of the episode frames that were reopened (the
reference lives: 30-40 past-frame looks each, median age 14-146 steps, p90 up to 4,222).

## 7. Caveats to carry into the write-up

- The codex thread persists across turns with a 4 MB frame budget, so the last ~8 turns'
  attached views are in the conversation in **every** condition, ablated or not. That is
  the model's context window, not the memory system; state it rather than claiming the
  no-images arm saw no past frames at all.
- Arm 3 bundles written knowledge and learned procedures **and reflexes** under one rule.
  If it shows a large effect, the follow-up that separates them is a variant that exempts
  `mine/reflexes/`.
- The diamond is partly a dice roll: diamond ore is ~0.09% of blocks at y<=15 and the
  reference lives scored 90 six times out of eight with 100 twice. Read the milestone
  timings (iron pickaxe step, first step at y<=12, blocks mined at depth) alongside the
  final score, not the score alone.
