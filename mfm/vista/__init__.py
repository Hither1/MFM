"""VISTA, as a memory arm on the MCU and KiCad benchmarks.

VISTA ("A Visual Harness for Reasoning in an Interactive World", Han, Hu, Qiu, Wu, He;
MIT, 2026; https://github.com/joshhhhhan/VISTA, commit 900aa33, MIT licence) is the
harness that took a general multimodal model to 100% on ARC-AGI-3. Its memory story is
the opposite of PRO-LONG's and of MFM's, which is why it is the right third baseline:

    PRO-LONG / MFM     the filesystem is the memory. Every call is a fresh (or short)
                       conversation; the model greps an append-only log, opens frames
                       by path, runs a query tool; the harness writes the record.
    VISTA              the conversation is the memory. One long codex thread drives the
                       environment through tools -- `play` executes exactly one action
                       and returns the objective result with the resulting frame steered
                       into the thread -- and the model has NO shell and no filesystem:
                       what it keeps outside the conversation is two agent-authored
                       notes (`GUIDE.md`, durable; `WORKING.md`, scratch), and what the
                       harness keeps for it is a lossless archive of every frame,
                       revisited through `inspect` (crop + nearest-neighbour magnify)
                       and `read_pixels`, plus `history`, the record of every play.
                       When the context fills, the model is asked to write a checkpoint
                       (`save_compact_checkpoint`: a replacement GUIDE and the
                       continuation state) and a FRESH thread starts from the current
                       observation, the last result, the recent history and the two
                       notes -- a handoff, not a summary.

What is ported, and from where (`src/vista_arc3/codex/` in the upstream tree):

    tools.py        the tool contracts, with the ARC `play` schema replaced by one the
                    benchmark supplies and the 1024x1024 display replaced by the frame's
                    own WxH pixels (640x360 on MCU, the screenshot's size on KiCad)
    archive.py      the frame archive and the `inspect` / `read_pixels` readers
                    (controller.py upstream)
    controller.py   the controller: play validation and the invalid-action budget, the
                    event record `history` reads, the checkpoint markers and the
                    recovery snapshots. The ARC game is replaced by a `Bridge` the
                    benchmark implements (validate, execute, the present state)
    dispatcher.py   the tool router and the checkpoint gate
    recovery.py     the recovery prompts
    runner.py       the codex app-server driver (`DockerCodexRunner` upstream), running
                    the local codex binary instead of a container, with one addition
                    (below)
    session.py      the segment loop (`run_task_with_compact_checkpoints` upstream), in
                    a background thread

What is NOT ported: RESET / level semantics and the `attempts` view of `history`
(ARC-specific), the Docker player image and the ARC scorecard plumbing.

The one addition. On ARC a frame is a few KB; here it is 130-500 KB, and codex re-sends
every image in the thread on every call, which on this cluster stalls the call near
5-6 MB on the wire (measured on MCU and again on KiCad). A token-based
compaction trigger never fires that early, so the runner counts the bytes it has sent
into the thread and, past `thread_bytes_budget` (4 MB by default), requests the SAME
checkpoint-and-fresh-thread handoff VISTA's PreCompact hook requests. The audit reports
every checkpoint with its reason, so a run says how many of its handoffs were the
model's context and how many were the wire.

Inversion of control. VISTA's harness is agent-driven: the model calls `play` and the
game steps inside the call. Both benchmarks here are environment-driven: the green
server (MCU) or `run_eval` (KiCad) calls the agent once per step and expects an action
back. `channel.ActionChannel` is the rendezvous: the codex thread blocks in `play`
until the environment has run the action and handed back the outcome; the environment
thread blocks in its step until the model has called `play`, up to the same per-turn
ceiling the other arms give a codex call, then runs a no-op tick and keeps waiting.
"""
