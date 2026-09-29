# Where a mllm-search cell's time goes, and what to do about it (a219/a227, 2026-08-19)

Measured against Qwen3.5-27B on a227, from this repository's own evaluators (no synthetic
prompts): the TP=1 dev server on `:8004` (231,389-token KV, MTP k=3, prefix caching, thinking
off) and the shared TP=4 server on `:8010` launched for this campaign (3,043,945-token KV,
same flags). Per-question costs for the two PRO-LONG cells are read off `runs/qwen38_v0`,
the finished Qwen3.8 campaign.

Nothing here changes what any arm reads or writes. The BM25 change is asserted bit-identical
against `rank_bm25`, and `--concurrency` defaults to 1 everywhere.

## 1. What a campaign costs, per cell

| cell | per question | where the time is | concurrent over questions? |
|---|---|---|---|
| `bcp:default` | 33–63 s | 8–9 model calls, ~1,400 output tokens | **yes** |
| `bcp:hypothesis` | ~ the same, plus the memory block | same loop | **yes** |
| `bcp:prolong` | 197 s (qwen38_v0, n=29) | 4 analyzer turns, each a `codex exec` | **yes** |

BrowseComp-Plus questions are deliberately disjoint and all three of its arms scope memory
to one question, so questions are free to run side by side. An arm that accumulated
memory *across* questions would have no concurrency to take without becoming a different
agent.

## 2. The search was the thing that could not be run twice at once

`rank_bm25.BM25Okapi.get_scores` walks all 100,195 document dicts once per query term. On
this corpus that is 320–880 ms per search, and every millisecond of it holds the GIL:

| | 1 thread | 4 threads | 8 threads |
|---|---|---|---|
| `rank_bm25`, per search | 0.48 s | 0.56 s | 0.64 s |
| inverted index, per search | 4.8 ms | — | 0.9 ms |

Threads made it *slower*. So the first attempt at question-level concurrency bought nothing
at all -- C=8 measured 2.05 q/min against C=1's 2.01 -- because eight questions' worth of
BM25 simply queued up behind one GIL.

A document that does not contain the term contributes exactly 0.0 to the BM25 sum, so
leaving it out changes no arithmetic; what remains depends only on the term and the document
and is summed in the same query order. `browsecomp_plus_data.enable_fast_scoring` builds that
inverted index once (174 s, 1.24 GB, cached beside the pickle as `bm25_postings.npz`) and
`_verify_fast` asserts equality against `rank_bm25` on real corpus text before it is allowed
to serve a query. Measured: **bit-identical**, 283–1229× faster, and in the agent loop
**4.1 s of a 33 s question down to 0.1 s**. Checked again afterwards on **120 real
BrowseComp-Plus queries**, whole score vector and top-5 both: all bit-identical. `BCP_FAST_BM25=0` restores the old path.

## 3. Then the KV cache was, and it has a number

With the search out of the way, `bcp:default` on the TP=1 dev server:

| concurrency | throughput | per question (median) | server |
|---|---|---|---|
| 1 | 0.97 q/min | 63.5 s | KV 6–17 %, 42–56 gen tok/s |
| 4 | 1.93 q/min | 59.5 s | — |
| 8 | **2.71 q/min** | 104.7 s | KV 72–89 %, 104–208 gen tok/s, 0 preemptions |
| 16 | 1.62 q/min | 446.9 s | KV 92–98 %, **preemptions 6 → 16**, prefix hit **0 %** |

C=16 is not a plateau, it is a collapse: past the KV ceiling vLLM preempts and recomputes,
and the evictions take the prefix cache with them -- the hit rate that carries a ReAct
conversation from turn to turn goes to zero, so every turn re-prefills from scratch.

The ceiling is arithmetic, not luck. One BrowseComp-Plus question peaks at ~15 % of the
dev server's KV, i.e. ~35k tokens by its last turn:

| server | GPUs | KV | BCP-sized contexts that fit |
|---|---|---|---|
| dev, TP=1, `:8004` | 1 | 231,389 tokens | ~6.6 |
| **shared, TP=2, `:8010`** | 2 | **1,196,489 tokens** | **~34** |

So the case for one shared multi-GPU server over several TP=1 ones is not the extra compute,
which a single cell cannot use, but the KV headroom that lets every cell run at once without
any of them thrashing.

## 3a. And a tensor-parallel group must not cross a227's two NUMA islands

The first shared server was TP=4 on a227 GPUs **2,3,4,5**, and it was ~10× slower than one
GPU: 55–57 concurrent requests at **16–33 generation tok/s aggregate**, against 45–56 tok/s for
a *single* request on one TP=1 GPU and 104–208 tok/s for eight. KV was 24 % used and
preemptions were 0, so it was neither capacity nor scheduling.

`nvidia-smi topo -m` says why. a227 has **no NVLink at all**; GPUs 0–3 are NUMA 0 and GPUs 4–7
are NUMA 1, `NODE` (PCIe through the host bridge) within an island and `SYS` (across the
sockets) between them. GPUs 2,3,4,5 straddles the boundary, so every all-reduce crossed the
inter-socket link -- and MTP `num_speculative_tokens=3` makes four forward passes per step,
so four times as many of them.

Valid groups are subsets of {0,1,2,3} or {4,5,6,7}, which is what the campaign's own run files
(`qwen35-s{1,2,3}.sh`: `2,3` / `4,5` / `6,7`) have always used. Moved to TP=2 on GPUs 2,3, the
same server under the same six cells:

| | TP=4 across the boundary (2,3,4,5) | TP=2 island-local (2,3) |
|---|---|---|
| generation | 16–33 tok/s @ 55–57 reqs | **383 tok/s @ 30 reqs** |
| prefill | 830–1,205 tok/s | **3,700–4,500 tok/s** |

Roughly 12× on both, from moving two GPUs.

## 3b. And TP=4 is wrong here even inside one island

When a227 later freed GPUs 4–7 — one island, every pair `NODE` — a TP=4 server there
served **one** request at 40.9 tok/s, which is healthy (the TP=1 dev server does 45–56).
Then the three BrowseComp-Plus cells were pointed at it, and 46–49 concurrent requests ran
at **29–111 generation tok/s**, with KV at 25 % and no preemptions. A TP=2 server on the
same box at 18 requests was doing **660 tok/s** at that moment.

The shape fits the hardware rather than the placement. With no NVLink every all-reduce is
PCIe, and its payload is hidden_size × batch: at batch 1 that is latency-bound and four
ranks cost almost nothing, but at batch 48 with MTP drafting 3 it is ~250 MB per forward
pass, four passes per step, and communication swallows the run. TP=2 halves the payload
and makes it one peer exchange instead of a four-way ring.

**So the box is three identical TP=2 servers, not one big one:** `(2,3)` `:8010`,
`(4,5)` `:8011`, `(6,7)` `:8012`. Identical settings mean an identical reduction order, so
a comparison may be split across them — what may not be split across is two servers with
*different* TP degrees, which is the distinction `SERVER_BCP` / `SERVER_BCP_PROLONG`
exist to keep.

Read together with §3: **size concurrency by the KV, and the TP degree by the batch.** It is worth checking `nvidia-smi` before claiming a
pair: a227 is shared with the MineExplorer campaign, which took GPUs 6,7 in the middle of this
measurement, which is why the shared server is a pair and not a quad.

## 4. The contract this campaign runs under

Server (`qwen35-serve/run/qwen35-shared.sh`, a227 GPUs 2,3, tmux `qwen35-shared`):

```
--tensor-parallel-size 2 --max-model-len 131072 --max-num-seqs 128
--max-num-batched-tokens 8192 --gpu-memory-utilization 0.90
--limit-mm-per-prompt '{"image":128,"video":1}'
--speculative-config '{"method":"qwen3_5_mtp","num_speculative_tokens":3}'
--enable-prefix-caching
--override-generation-config '{"temperature":0.7,"top_p":0.8,"top_k":20,"max_new_tokens":1024}'
--default-chat-template-kwargs '{"enable_thinking":false}'
--enable-auto-tool-choice --tool-call-parser qwen3_xml
```

`--tool-call-parser` is what the codex-driven arms need to see tool calls at all (without it
the model's calls come back as raw text and the turn fails silently with rc=0).

Cells (`scripts/launch_campaign.sh`): concurrency 6 for the two BrowseComp-Plus ReAct arms,
5 for `bcp:prolong` -- each of its episodes is a `codex exec` in its own mount and network
namespace, not just a request. Sized against the KV, not against the request count: 2x6
ReAct contexts at ~35k and 5 PRO-LONG episodes at ~50k, well inside 1,196,489.

## 5. What is left

- The judge now runs on the shared server for all three BrowseComp-Plus arms
  (`--judge local --server-url`), which both removes a codex call per question from
  `bcp:prolong` and makes the three arms poolable. `judge_endpoint` in each result's `arm`
  block records it. Scores taken under the old per-channel judges (`runs/qwen38_v0`) are not
  poolable with these.
