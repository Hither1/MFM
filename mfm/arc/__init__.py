"""The arc-code baseline: a general coding-agent harness with one actuator.

Ported from github.com/jerber/arc-code @6b33c1f (2026-08-12, MIT). Upstream is three
files -- PROMPT.md (the method), act.py (the actuator), run.py (the launcher) -- and the
claim that none of them knows the game: the agent is stock Claude Code or Codex with a
shell and a filesystem, `./act do` is the only way it touches the environment, every
action and the state it produced go verbatim into `logs.txt`, and whatever machinery a
game needs (a parser, a simulator, a search) the model writes during the run and keeps
as files. The published pass was Opus 5 through Claude Code at 96.2 on ARC-AGI-3's 25
public games; Codex/gpt-5.6-sol scored 73.7 on the same harness.

What is ported here, and from where:

  prompt.py    PROMPT.md's method, sentence for sentence, with the ARC words replaced by
               the benchmark's (level -> milestone, board -> frame, action -> entry);
               upstream's TASK / RESUME_TASK one-liners.
  act.py       act.py's contract as the agent sees it: `do` plays a batch in order and
               stops as soon as the score moves, `--plan` is recorded beside the batch,
               `status` is one line, invalid input is refused with a reason. Upstream
               drove the ARC HTTP API from inside the actuator; here the actuator is
               upstream's rig/client.py shape -- a stdlib-only shim in the workspace that
               forwards to the harness -- because the environment is driven by the
               benchmark's own server, not by the agent (the inversion `mfm.vista`
               already handles: `mfm.vista.channel.ActionChannel`).
  mailbox.py   The forwarding transport: request and response files in the workspace,
               in place of upstream's broker over HTTP. Chosen because the coding
               agent's own sandbox gives its commands no network, and because the files
               are the record of every actuator call.
  session.py   run.py's session: one long `codex exec --json` (or `claude -p
               --output-format stream-json`) in the workspace with the task prompt,
               its event stream recorded verbatim, the counts upstream's rig/agents.py
               reads off it (turns, tool calls, compactions, tokens; here also image
               views), and upstream's `--resume` -- a session that exits before the
               budget is spent is replaced by a fresh one told to recover from the
               notes and the log.

Not ported: the E2B sandbox and the network fence (the cluster's codex sandbox and no
network is the same policy every arm here runs under), the Postgres record, ARC's
scoring, the audit for answer-seeking (nothing to look up for these tasks).

The benchmark adapters (MCU: `mcu_worldmodel/arc.py`) own the brief -- what this
environment is and what `./act do` accepts -- and the log format, which is the
chassis's own section format rather than upstream's hex boards: the sections carry the
same facts (the plan, the entry, the state, the events) and name the frame they
produced, so the model's scripts parse text and its image tool reads the frame.
"""
