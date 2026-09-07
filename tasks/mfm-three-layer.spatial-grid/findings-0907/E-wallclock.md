# E. Where the wall clock goes (2026-09-07 12:0x, scratchpad turntime.py over codex_turns mtimes)

| run | contract | turns | steps | steps/turn | wall/turn median / mean / p90 | cmds/turn | reads per turn |
|---|---|---|---|---|---|---|---|
| og8  | full, carry | 266 | 34431 | 129 | 64 / 75 / 133 s | 3.0 | logs.txt 1.35, actions.json 1.03, AGENTS.md 0.25, episodes.py 0.16 |
| og9  | thin, carry | 251 | 30220 | 120 | 67 / 77 / 136 s | 3.5 | logs.txt 1.31, references/ 1.03 (procedures.md 0.71), actions.json 0.96, episodes.py 0.24 |
| og10 | full | 286 | 47812 | 167 | 67 / 78 / 139 s | 2.9 | logs.txt 1.14, actions.json 1.05, episodes.py 0.35, AGENTS.md 0.20 |
| og11 | thin | 335 | 29150 | 87 | 59 / 67 / 125 s | 2.7 | logs.txt 1.10, references/ 0.80 (procedures.md 0.49), actions.json 0.64 |
| og12 | full | 190 | 28364 | 149 | 65 / 72 / 122 s | 2.3 | actions.json 1.00, logs.txt 0.98, episodes.py 0.12 |
| og13 | thin | 196 | 19897 | 102 | 61 / 71 / 129 s | 3.0 | logs.txt 1.06, actions.json 1.03, references/ 0.90 (procedures.md 0.58) |
| og14 | thin+atoms+own | 113 | 5550 | 49 | 57 / 69 / 127 s | 2.8 | logs.txt 0.99, actions.json 0.96, references/ 0.48, mine/ 0.43, procedures.md 0.21 |

1. The wall clock per turn is the SAME for every contract: median 57-67 s, p90 122-139 s.
   A turn is gpt-6-astra high reasoning plus ~3 exec round trips; thin's reference reads
   (0.5-1.0 per turn) do not lengthen it measurably (og9 67 s vs og8 64 s, og13 61 vs og12 65).
2. Steps per hour differ ONLY through steps per plan: full 129-167, thin 87-120, atoms 49.
   The plan cap is 40 entries / 400 ticks (AGENTS.md line 176); plans use a quarter of it.
   Over time (windows of 30 plans): og13 109 118 163 114 84 57; og11 84 125 135 135 68 84
   122 95 62 55; og14 71 78 28 -- plans shrink in the precision phases (the pool, the
   shaft) and og14's atoms make every plan short by construction.
3. Milestones per HOUR still favour thin so far (og13 14/24 at 2h45 vs og12 14/24 at 3h52),
   so the shorter plans are not a net loss; they become one only where the 10h cap binds
   before the 60k steps: og11 (5.4k/h -> ~54k) barely, og14 (3.0k/h -> ~30k) clearly.
4. What the model runs each turn (og13, 60 turns sampled): its first command is almost
   always `rg -n -A 10 -B 3 'Step 13090|Step 13096' logs.txt` -- it re-reads the FULL log
   sections of the plan that just ran (the [STATE]/[INV]/[NOTE] lines), although the turn
   prompt already carries a compact per-entry summary and the notes. Then a python heredoc
   writes actions.json (1.0 per turn), then 0.5-1.0 reference lookups.
   Candidate (wall clock, not steps): put the last plan's verbatim log sections into the
   turn prompt (40-60 lines) and drop the "grep it" closing line -> one exec round trip
   fewer per turn, ~15-20 s of ~65 s. Not applied while the read-outs run (it changes the
   turn prompt for every arm); a candidate for the og15 launch, measured as wall/turn.
5. og14's structural cost is the atoms: a plan of raw ticks and small atoms is 30-80 ticks;
   the design's answer is its own procedures (north_stair = 246 ticks per call). Watch
   whether steps/plan rises as mine/procedures/ grows; if it does not by ~10k steps, the
   contract needs a line that names the cost ("a plan under 100 ticks spends a 60-second
   turn on nothing: batch, or write the procedure").
