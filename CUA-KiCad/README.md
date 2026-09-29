# CUA-KiCad
Multimodal LM search framework

## KiCad (cua-bench) results

Official cua-bench score (`cua_bench.netlist_compare`: mean of three all-or-nothing checks --
components, nets, net names), mean over tasks. The benchmark has **25** tasks. Every run of the
2026-09-05..07 wave was launched with `--exclude-tasks a6414tw4` ("create an empty netlist file":
its reference netlist is empty; a saved blank schematic scores 1.0, nothing saved scores 0) and so
holds **24** tasks; those cells are marked **24/25** and the missing task is being backfilled
(one-task reruns from worktrees pinned to each arm's launch commits, `<run>_a6414tw4/`). A cell
is comparable across the row only in the wave setup: `--kicad-project-hint`, codex CLI 0.153.4, the
LN271->LD271 task patch, one arm per node, `EVAL_CONC=1`.

Runs live in `runs/cua_bench_codex/<run>/` (`results.jsonl`, `summary.json`, per-task
`kicad_project/` + `graded.net` for offline re-scoring with `gym_codex/kicad_rescore.py`).

| arm | gpt-5.6-sol | gpt-6-astra | Opus 5 |
|---|---|---|---|
| **direct** (memoryless, `--agent direct`) | **0.188** (high) -- 23/25: `kicad_direct_gpt56high_hint`, 733d278a lost to a screenshot failure, a6414tw4 excluded | **0.194** (low) -- 24/25: `kicad_direct_gpt6low_hint` | not run |
| **ProLong** (`--agent prolong-logonly`: the append-only log is the only memory; the model's own workspace files are taken back every turn) | (0.306) -- 24/25 of `kicad_prolong_v1` (09-01, gpt-5.6 low, `--agent prolong` with the workspace kept, **no hint, codex 0.149, before the LN271 patch**: not the wave setup; 0.293 on its 25) | **0.375** (low) -- 24/25: `kicad_pllogonly_gpt6hint` | not run |
| **VISTA** (`--agent vista`) | not run | **0.347** (low) -- 24/25: `kicad_vista_gpt6hint` | not run |
| **MFM** (`--agent mfm`) | (0.347) -- 24/25 of `kicad_mfm_projdir` (09-04, gpt-5.6 low, hint on, **codex 0.149, before the LN271 patch**: not the wave setup; 0.373 on its 25, a6414tw4 = 1.0) | **0.413** (low) -- **25/25**: `kicad_mfmcarry3design_gpt6hint` (`--agent mfm-carry --carry-outcomes --design-turn --conventions`) | not run |

Other gpt-6 (low, wave setup, 24/25) arms: prolong-carry 0.375, mfm-carry
0.361, mfm-carry+recall 0.375, mfm + `--netlist-readback` 0.347, arc 0.333. A 25/25 cell is not
directly comparable to a 24/25 one: a6414tw4 is worth +0.024 to any arm that saves a blank
schematic, which every memory arm with the project hint has done.

Runs still needed for a complete 25-task table:

- a6414tw4 for every 24/25 cell above (direct x2, prolong-logonly, vista; the ablations prolong,
  mfm and mfm-carry3; plus the other gpt-6 arms). Backfill launcher: `~/kicad25/launch_backfill.sh` (2026-09-13); the first
  attempt was cancelled when the hosted codex account's refresh token was revoked -- re-run after
  `codex login` against `$CODEX_EVAL_HOME`.
- 733d278a for `kicad_direct_gpt56high_hint`.
- gpt-5.6-sol in the wave setup: prolong-logonly, vista, mfm (the two bracketed cells are
  older-setup runs, not substitutes).
- Opus 5, all four arms (needs the Claude route: `--arc-agent claude` exists for arc; the
  prolong/mfm/vista arms are codex-only today).

Every cell is one `gym_codex/run_eval.py` invocation. `scripts/run_kicad_arm.sh` wraps it with
what a node needs (node-local podman storage, the codex sandbox, the model provider), and
[`docs/KICAD_RUNS.md`](docs/KICAD_RUNS.md) is the step-by-step for running the missing cells on
another cluster.

## PRO-LONG arm (BrowseComp-Plus)

`prolong_search/` ports the PRO-LONG programmatic-memory agent
([paper](https://arxiv.org/abs/2607.20064), [upstream](https://github.com/alexisfox7/PRO-LONG))
from the MineExplorer integration (`MineExplorer:codex/qwen35-27b-minecraft-0313-0544`,
`prolong_mc/` + `mc_agent/prolong_agent.py`) onto this repository's search benchmark.

The agent's memory is an append-only `logs.txt` it greps with real tools, with the bulky
part of each observation written to disk beside it as a file the log merely names, plus a
persistent workspace it may write notes and helper scripts into. Its output each turn is a
JSON artifact, not a message.

### Three axes, kept apart

Copied from the MineExplorer campaign, where conflating the first two cost a result.

| Axis | Flag | Values |
|---|---|---|
| **agent** | which script | `eval_direct_*` (no memory), `eval_hypothesis_*` (hypothesis memory), `eval_prolong_*` (PRO-LONG) |
| **scaffold** | `--use-codex` | codex CLI, or the local vLLM/HF backend |
| **ablation** | `--prolong-log-window`, `--prolong-stateless` | full log, last N sections, latest only; workspace kept or wiped |

There is no `prolong` + local-backend cell: PRO-LONG is built on `codex exec resume`, so
outside the CLI that agent does not exist. **That is why the scaffold axis matters** — a
`direct` vs `prolong` difference measured against a plain vLLM baseline is a difference
between two harnesses as much as between two memory architectures. `--use-codex` runs the
existing direct evaluators through the same Codex channel and is the control that
separates them. It is off by default; every existing invocation is unchanged.

### The sandbox

Upstream runs its agent in a Docker container on an `--internal` network whose only exit
is a squid allowlist proxy to the model API. Three properties come out of that, and each
one has a home here:

| upstream property | here |
|---|---|
| only the workspace is reachable | one unprivileged **mount namespace** per `codex exec` (`prolong_search/codex_sandbox.sh`, bubblewrap) |
| no network but the model API | **`--unshare-net`** plus an allowlisting CONNECT proxy on a unix socket (`prolong_search/sandbox_proxy.py`) |
| the agent's own commands are confined | codex's inner sandbox, `sandbox_mode="workspace-write"` |

bubblewrap rather than Docker because this host has no docker group and rootless podman
here has no CNI plugins for an internal network; the isolation is the same class of
primitive — upstream's container is in fact the *only* boundary in its setup, since it
runs codex itself at `danger-full-access`.

**Why reads have to be bounded.** Codex's own `workspace-write` bounds writes and the
agent shell's network but **not reads**, and neither `sandbox_workspace_write.readable_roots`
nor `sandbox_permissions=[]` changes that (all measured 2026-08-17). The answers sit on
the same filesystem as the run: `data/browsecomp_plus/queries_decrypted.jsonl` is the
gold answers in the clear. So the corpus, the datasets, the evaluator source, the
judge's transcripts and every other
episode's workspace are simply not mounted.

**A fourth property upstream gets for free, and we had to buy.** Upstream authenticates
with an API key, so its agent has no account behind it. Ours runs on a ChatGPT
subscription, and codex hands the model whatever that account carries — *before* any
sandbox applies, because these tools run server-side or inside the codex process, not in
the agent's shell. Measured through this wrapper, hosted, with a `CODEX_HOME` holding
nothing but `auth.json`:

- `web_search` defaults to `"cached"` (OpenAI's own web index) and **the model used it** —
  it returned a Wikipedia URL. On BrowseComp-Plus that is a second, larger corpus.
- ~250 account connectors were in the tool list (`mcp__codex_apps__github_*`, gmail,
  slack, google_drive, hugging_face…). The docs are explicit that their "traffic [is] not
  controlled by sandboxed-command network proxy".
- `spawn_agent` was offered, so one "analyzer turn" could fan out into threads the
  request and token accounting never sees.

`codex_backend.SAFE_CODEX_FLAGS` closes all three, on the first turn and on
`codex exec resume`, for the PRO-LONG turns and for the `--use-codex` control and the
judge alike. With them in force the model's whole tool surface is `apply_patch`,
`exec_command`, `update_plan`, `view_image`, `write_stdin` — and anything else that shows
up in a transcript raises `SandboxViolation` and stops the run, rather than being counted
in an audit nobody reads. (`--disable multi_agent` does *not* remove the sub-agent tools;
`agents.enabled=false` does. `--ignore-user-config` is load-bearing for a second reason:
it also suppresses a project-level `.codex/config.toml`, which codex would otherwise trust
in a workspace it auto-trusts.)

**One CODEX_HOME per episode.** `--ignore-user-config` skips `config.toml` only, so a
personal home's `AGENTS.md` is injected into every turn regardless (+3,866 tokens measured
on a one-word prompt) — hence a separate evaluation home. But a *shared* evaluation home
is worse than cosmetic: the judge is a codex call too and writes its rollouts, carrying
`[correct_answer]`, into the same home; `state_*.sqlite` keeps each thread's first user
message; and `codex exec resume` needs only `sessions/`. An agent that can read its own
`$HOME` can therefore read a previous question's gold answer. The wrapper now derives
`<workspace>.codexhome` per episode, mounts only that, seeds it with an empty
`skills/.system` (which suppresses the account's built-in skills), and bind-mounts
`auth.json` **read-only** from the master home, so no token is ever written to disk.
Because the token is read-only, codex cannot refresh it mid-campaign: run `codex login`
against `$CODEX_EVAL_HOME` before a campaign longer than the token's remaining life, which
`sandbox_selftest` prints.

**Checking it, rather than believing it.** "The agent did not read the answers" is an
audit of one run; "the agent could not" is a property of the harness, and a property has
to be re-checked. `sandbox_selftest.py` asserts each one *through the wrapper itself*, so
what it measures cannot drift from what the runs use:

```bash
python -m prolong_search.sandbox_selftest              # no model, no quota
python -m prolong_search.sandbox_selftest --with-model # + the live tool surface
```

Offline it covers the gold answers, the datasets, the evaluator source, a sibling
episode's workspace and *its home*, writes outside, `/tmp` privacy, the toolchain the
mechanism needs, loopback-only networking with no DNS, and the proxy admitting the API
host while refusing everything else. `--with-model` costs one call and asserts the live
`ALL_TOOLS` equals the whitelist, that no web fetch succeeds, and that the evaluator is
unreadable. Both fail if `CODEX_BIN` is not actually the wrapper — which is how a campaign
gets launched unsandboxed.

**What is still not owned here.** The proxy allowlist is by hostname over CONNECT, so it
cannot see inside the TLS session to the model API; upstream's squid has the same property.
And the account itself is still a subscription account — the flags remove the tools from
the model's hands, but an account with nothing installed remains the cleaner control, and
an API key (upstream's setup) removes the question entirely.

### What one episode is

| benchmark | episode | step | memory scope |
|---|---|---|---|
| BrowseComp-Plus | one question | one BM25 `search` | per question, matching `eval_hypothesis_browsecomp_plus.py` (the questions are deliberately disjoint) |

### Running

```bash
# The sandbox, for every command below. Without it the agent can read the gold answers,
# search the live web, and reach the account's connectors. See "The sandbox" above.
export CODEX_BIN="$PWD/prolong_search/codex_sandbox.sh"
export CODEX_EVAL_HOME="$HOME/.codex-eval"   # master auth; bound read-only per episode

# Offline assertions first -- an ablation that does not bind, or a sandbox that stopped
# binding, produces a number that looks fine and means something else. No GPU, no model.
python -m prolong_search.selftest
python -m prolong_search.sandbox_selftest
# Once per campaign, and before reporting: one model call that measures the live tool
# surface (the layer no local sandbox owns).
python -m prolong_search.sandbox_selftest --with-model

# BrowseComp-Plus. Needs the BM25 index built once (browsecomp_plus_data.py) and an
# interpreter with rank_bm25 -- on this machine that is venvs/qwen35, not base.
python eval_prolong_browsecomp_plus.py --limit 20 --codex-model gpt-5.6-sol

# The ablations, enforced in the filesystem rather than requested in the prompt.
python eval_prolong_browsecomp_plus.py --limit 20 --prolong-log-window 0
python eval_prolong_browsecomp_plus.py --limit 20 --prolong-stateless

# The scaffold control: the baseline agent, same channel.
python eval_direct_browsecomp_plus.py --limit 20 --use-codex --codex-model gpt-5.6-sol
```

Slurm: `slurm/prolong_browsecomp_plus.sh`. It needs outbound HTTPS to the Codex endpoint
from the compute node and a readable `CODEX_EVAL_HOME`; it does not need a GPU on the
hosted channel. On a node with no `/run/user/$UID`, the wrapper falls
back to `$TMPDIR` for the proxy socket (AF_UNIX caps the path at 108 bytes, so keep
`TMPDIR` short). A local-server arm (`--codex-base-url`) must add that server to
`CODEX_SANDBOX_ALLOW`, e.g. `CODEX_SANDBOX_ALLOW=".chatgpt.com:443,.openai.com:443,gh142:30000"`.

### Running a whole campaign, and how fast it goes

Three cells (three agents x one benchmark) against one shared vLLM server:

```bash
TAG=qwen35_v1 N=300 bash scripts/launch_campaign.sh   # DRY=1 prints instead
python scripts/campaign_status.py runs/qwen35_v1 --n 300
bash scripts/launch_full.sh                            # then take it to 830
```

`scripts/run_cell.sh` is one cell by hand and is what the launchers call. It supplies the
fourth thing a cell needs and no evaluator knows: where the shared server is, how many
questions may be in flight, and where the evidence goes.

**`--concurrency` is over questions.** BrowseComp-Plus questions are deliberately disjoint
and all three of its arms scope memory to one question -- a transcript, a
`HypothesisMemory`, or a PRO-LONG workspace/log/session -- so running several at once
changes the wall clock and nothing else. The same rule is what lets every cell resume
when `--limit` grows: see `scripts/launch_full.sh`.

Two things bound how fast this can go, both measured in `experiments/EVAL_SPEED.md`:

- **BM25.** `rank_bm25` scores by walking all 100,195 documents per query term -- 0.48 s a
  search, holding the GIL, so eight threads made it *slower*. `enable_fast_scoring` builds an
  inverted index instead (one-off ~3 min, cached as `bm25_postings.npz`, asserted
  bit-identical to `rank_bm25` and verified on 120 real queries): 4.1 s of a 33 s question
  down to 0.1 s. `BCP_FAST_BM25=0` restores the old path.
- **The KV cache.** One BrowseComp-Plus question peaks near 35k tokens, so a server's KV size
  divided by that is the real concurrency ceiling, and past it throughput *falls* -- eviction
  takes the prefix cache with it. Size `--concurrency` against the server's reported
  "GPU KV cache size", not against a request count, and watch
  `vllm:num_preemptions_total`.

On a227, keep a tensor-parallel group inside one NUMA island (GPUs 0-3 or 4-7): the box has
no NVLink, and a TP=4 group straddling the two ran 12x slower than TP=2 inside one.

### Reading the output

Each run's JSON carries an `arm` block (agent, channel, model, effort, judge, ablation)
so a score is never attributed by parsing a filename, and a `prolong` audit block with the
cost the score was bought at — analyzer turns, requests, tokens, searches, and
`compactions`, which **must be 0**. A nonzero count means codex compacted the conversation
and those episodes are not running the architecture the arm claims to run.

The workspaces are the primary evidence and are kept next to the results: one `logs.txt`
per episode, the documents or frames it names, and whatever the agent built for itself.
