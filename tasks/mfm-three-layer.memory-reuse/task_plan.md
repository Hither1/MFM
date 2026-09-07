# Task plan: memory reuse, digested by the model (2026-09-07 22:xx)

## Stable Anchor
- Question (user, 22:1x: "开始记忆reuse的线，但是不要用harness消化记忆，而是让模型自己消化记忆"):
  does a life that CARRIES earlier lives' records and digests them ITSELF reach the
  obsidian / portal / Nether milestones in fewer steps than a life from scratch -- with
  nothing about those lives computed or pushed by the harness?
- Protocol (see memory `mfm-carry-only-protocol`): earlier lives are hard-linked under
  `previous/life_<i>/` (logs.txt, episodes/, index.jsonl, grid.jsonl, mine/), the contract
  says where they are; NO `--sites`, no [KNOWN SITES], no corridor/frame pointers. New
  with this task (MCU `--own` + previous, `previous.MFM_DIGEST_NOTE`): the contract's
  one added instruction is that the model's FIRST act is to write its own
  `mine/digest.md` from the records (verified places, deaths, what its scripts assumed)
  and keep it current; `mine/` is carried on, so the digest compounds across lives.
  The harness makes no summary.
- Seeds allowed: lives that never saw pushed sites -- the 12 first-generation
  worldmodel/logbook lives, og3/og4 (spatial-grid, no sites), og8/og9 (carry, no
  sites), og12/og13/og14/og16/og17 (scratch). The ob1..obf3 chain is contaminated.
- Success criterion: steps to mine_obsidian, flint_and_steel, netherrack vs the scratch
  arms on the same code (og13 obsidian 13358, og12 6134 / Nether 30305, og16 41835,
  og17 18259, og14 15505); deaths; `prev` turns (compare.py) and previous/ reads
  (toolcalls.py); the digest itself (does it name the pool at (-2996, 11, -5553), the
  Nether lava sea, the flooded pocket og14 used).
- Non-goals: no harness digest of any kind; no seeding from the ob chain; the
  self-harness chain (og14 -> og15 -> og20) is its own task (self-harness).

## Arms
- og15_mfm (running since 21:49, self-harness task): thin + atoms + own, seeded with
  og14's life only; no digest instruction (it wrote "Prior-life evidence" into
  mine/notes.md on its own in turn 1: the digest happens unprompted, which is the
  baseline for this task's instruction).
- og19_mfm (this task): thin + own (the full thin library, mine/ kept) + the digest
  instruction + the Nether lock, seeded with the 12 first-gen + og3 og4 og12 og13 og14
  (GRID_SEEDS) + og8 og9 og16 og17 (EXTRA_SEEDS), 60k steps, gpt-6-astra high, 320x180,
  10h cap. Control: og16 (thin, scratch, 15/24 at 41.8k, obsidian 41835) and og13.

## Verification
tests/test_own_reflex.py::test_contract_carries_the_reflex_and_digest_notes (the digest
note is in the own+previous contract and the human contract, absent otherwise).

## Next Action
Launch og19 after the Nether-lock stage passes and MFM-grid/MCU is fast-forwarded;
at 1-2k steps read mine/digest.md and the turn-1 commands (toolcalls.py); at the cap
compare with og16/og13.

## Launch 2026-09-07 23:03
og19_mfm launched from the live MFM-grid/MCU at c972f3af: 23 lives under previous/ (the 12
first-gen + og3 og4 og12 og13 og14 via GRID_SEEDS + og8 og9 og16 og17 via EXTRA_SEEDS),
`--thin --own`, gpt-6-astra high, 320x180, 60k steps, session-turns 0 + compaction, 10h
cap (~09:03), ports 9123/9133, codex home under codex-homes/. Verified: no Traceback,
the contract carries the digest note and the own-files paragraph, references/survival.md
the Nether lock. First turn running at 23:05 (23 lives to read).
