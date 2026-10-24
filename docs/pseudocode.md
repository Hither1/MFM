# MFM (Multimodal Filesystem Memory): the method in pseudocode

The `mfm` arm on the Minecraft chassis, as `MCU/mcu_worldmodel/arms.py` configures it
and `scripts/run-arm.sh --memory mfm` runs it (one model session for the life), read
off `MCU/mcu_worldmodel/{agent,previous,own,episodes}.py` and `mfm/{memory,backend}`.
The KiCad arm (`CUA-KiCad/gym_codex/prolong_agent.py`) keeps the same record and
retrieval on `mfm/memory`; what it carries between tasks is in `mfm/memory/carry.py`.

The idea in one line: the agent's memory is a directory. The harness writes an immutable
record into it (log, episodes, frames), the model writes its own files into it (guide,
working note, procedures, reflexes), and every model call is one turn of a single long
conversation whose working directory is that record.

```
────────────────────────────────────────────────────────────────────────────
DATA
────────────────────────────────────────────────────────────────────────────
W : workspace directory of this life = the model's cwd = its whole memory
    AGENTS.md              the standing contract, written once before turn 1
    logs.txt               append-only log of sections: [STATE] [EVENT] [INV] [NOTE] [PLAN]
    episodes/ep_N/         one directory per plan entry:
                             observation/image.png  frame the entry started from
                             state/state.json       structured state at its first tick
                             action.json            the entry, its place in the plan, the plan text
                             outcome.json           moved, descended, inventory delta, events, notes, tags
    index.jsonl            one row per closed episode
    tools/episodes.py      query CLI over index.jsonl:
                             --last N | --steps A B | --near X Z | --tag T | --grep TEXT | --action A
                             --sheet out.png (tile frames)  --then-now EP --q "..." (then/now pair)
                             --previous (query every earlier life at once)
    skills/                harness reference: memory / procedures / reflexes / harness SKILL.md,
                           example reflex scripts (lava_ahead, fell, hit, starving)
    references/            long reference docs read on demand (skills.md, survival.md, own.md)
    mine/                  THE MODEL'S OWN FILES, carried to the next life unchanged:
                             GUIDE.md      what is true of this world across lives
                             working.md    the continuation note, served back every turn
                             notes.md      what worked, what each script assumes
                             procedures/*.py   scripts that expand to raw actions
                             reflexes/*.py     scripts run on the live state every 4 ticks
    previous/life_i/       every earlier life's workspace, hard-linked, oldest first
    previous/index.jsonl   all earlier lives' episodes, paths rewritten
    actions.json           the artifact one turn must produce

T : one resumable codex thread rooted at W (sandbox: workspace-write, view_image, shell)
    auto-compacts at 100k tokens; cold-started on overflow or on two failed turns in a row
Q : deque of (env_action, entry_index)        the plan being executed
L : milestone ledger (rules, achieved set, stat stream)
(no built-in procedure: every plan entry is a raw action or one of the model's own
 scripts under mine/procedures/)
```

```
────────────────────────────────────────────────────────────────────────────
procedure RUN_LIFE(task, seeds)                       # one life = one MCU episode
────────────────────────────────────────────────────────────────────────────
    W ← fresh directory
    SEED_PREVIOUS(W, seeds)
    write W/AGENTS.md ← CONTRACT(task, previous = seeds ≠ ∅)
    write W/skills/*, W/references/*, W/tools/episodes.py
    T ← new codex thread with cwd W
    for each environment step s with observation o:
        OBSERVE(o, s)                                 # ground truth into memory, no model
        a ← NEXT_ACTION(o, s)                         # a model turn only when Q is empty
        env.step(a)
    close the open episode; write the report
    return W                                          # the next life's seed


procedure SEED_PREVIOUS(W, seeds)                     # the carry
    lives ← every life reachable from the seeds (a seed may itself hold previous/), deduplicated
    for i, src in enumerate(lives, 1):
        hard-link src/* → W/previous/life_i/, skipping harness-only files
            (AGENTS.md, tools/, references/, previous/, actions.json, sites.json, ...)
        rows ← src/index.jsonl, each row tagged life=i, paths prefixed previous/life_i/
    write W/previous/index.jsonl ← all rows
    # nothing is digested for the model: the contract tells it previous/ exists and that
    # its first turn is a workshop turn; reading is the model's job


procedure OBSERVE(o, s)                               # every environment step
    fired ← L.update(o)                               # milestone rules over the stat stream
    if fired:
        log [EVENT] MILESTONE ...; pending_events += fired
        if Q ≠ ∅ and no macro/GUI at its head: Q.clear()      # the chain is ordered: re-plan
    stats ← L.stat_events(o)                          # mine_block, craft_item, pickup, ...
    log stats; pending_events += stats
    pos, hp ← o
    if |pos − prev_pos| > 15:                         # a teleport
        if hp unchanged and coords scale by 8 and not at spawn:
            dimension ← Nether | Overworld; note "a portal trip, not a death"; Q.clear()
        else if hp ≥ 19:
            note "YOU DIED at prev_pos"; Q.clear()
    else if hp fell ≥ 3 in one tick (or ≥ 4 slowly):
        note "damage: health hp/20 at pos; find the danger before continuing"; Q.clear()
        # harness reflexes are off in this run: the note stands, the runner does not act
    log [STATE] pos pitch yaw; grid.observe(pos)
    last_pov ← o.pov
    GUARDS(s, pos)                                    # nether watcher, lava, shaft, fall, water:
                                                      # each may add a note and clear Q
    cur_inv ← inventory(o)
    if s mod 4 = 0: OWN_REFLEX_TICK(o, s)


procedure NEXT_ACTION(o, s)
    if every milestone is achieved: return noop        # coast to the horizon
    if Q = ∅: ACT_TURN(o, s)                            # refill from the model
    (head, idx) ← Q[0]
    if idx ≠ current_entry:                             # an entry boundary
        current_entry ← idx; start_pos ← pos; start_inv ← cur_inv
        store.open(plan_entries[idx], idx, state(o), frame = o.pov)   # episodes/ep_N/
    if head is a closed-loop marker (_servo, _goto, _dig, _seq, _click, ...):
        a ← head.tick(o); pop head only when it reports done
    else:
        a ← Q.popleft()
    if the entry just ended: FINISH_ENTRY(idx)
    return a


procedure FINISH_ENTRY(idx)
    store.close(events = pending_events, notes = pending_notes)   # outcome.json + index row + tags
    log [ACTION] section: entry text, moved, descended, [INV] delta, [EVENT]s, [NOTE]s, frame path
    turn_outcomes.append({label, moved, descended, inv Δ, events, first note, frame})
    pending_events, pending_notes ← ∅


procedure ACT_TURN(o, s)                              # one model call
    stall_turns ← 0 if (milestones, inventory) changed since the last turn else stall_turns + 1
    store.flush(s)                                    # an entry Q dropped closes as `flushed`
    frame ← save o.pov as attach/<s>.png
    prompt ← TURN_PROMPT(o, s)
    publish W                                         # windowed logs.txt copy; frames linked
    for attempt in 1..analyzer_retries:
        result ← T.run(prompt if attempt = 1 else RETRY_NUDGE, images = [frame])
        # inside the call the model may: grep logs.txt; run tools/episodes.py;
        # view_image any frame; read and write mine/*; write mine/procedures/*.py and
        # mine/reflexes/*.py; it must write ./actions.json and answer with a briefing
        if result.ok: break
        sleep(min(30, 2^attempt))
    if a harness-owned file changed: note "not yours to write"; sweep foreign files
    briefing, plan_text ← split(result.message)
    last_expect ← the `EXPECT:` line of the briefing, if any
    log [PLAN] ← plan_text                            # repeated in every section until replaced
    store.plan(turn, briefing, plan_text)
    if no actions.json:
        note "no valid actions.json this turn; one no-op was executed"; Q ← [noop]; return
    plan ← PARSE(actions.json)
        # entries are {action, repeat}, or {procedure: <own name>, args}
        # an own procedure runs `python mine/procedures/<name>.py --args ...` on the live
        # state and expands to its raw actions; caps: 40 entries, 400 steps per plan
    memory.add_note(each parse note)
    Q ← [(step, i) for i, entry in enumerate(plan.entries) for step in entry.steps]


function TURN_PROMPT(o, s)                            # only what changed; the contract is AGENTS.md
    head ←
        "Step s/max, N remain; milestones k/24"
        "Act turns since anything verifiably changed: stall_turns"
        Milestones block
        [STATE] pos pitch yaw; Vitals; Inventory (free slots); Hotbar; Held; Nearby entities;
                GUI open; cursor line
        [MAP]   what this life's own positions and events prove (the grid)
        [OWN]   mine/procedures/*.py with call counts; mine/reflexes/*.py with fire counts
                and which are switched off
    body ←
        [EXPECTED] last_expect
        [OBSERVED] one line per finished entry of the last plan:
                   moved, descended, inv Δ, events, note, frame path
        "Begin your briefing `OBSERVED vs EXPECTED: ...`; end it `EXPECT: ...`"
        [WORKING] mine/working.md (first 1500 chars)
        "Your memory is ./logs.txt; ./tools/episodes.py queries the episodes;
         view_image opens a frame. The current view is attached. Write ./actions.json."
    return head + body


procedure OWN_REFLEX_TICK(o, s)                       # every 4 ticks, outside a GUI
    state ← {pos, pos_prev, health, health_prev, food, food_prev, lava_frac(last_pov),
             dimension, running entry, queue length, inventory, ...}
    for each live script r in mine/reflexes/*.py (sorted, at most REFLEX_MAX, cooldown per script):
        res ← run `python r` with state on stdin
        if r errored REFLEX_FAILS times in a row: switch it off until its file changes; note it
        if res = ∅: continue
        note "[REFLEX name] res.note"
        if res.stop or res.actions: Q.clear()
        if res.actions: Q ← PARSE(res.actions) (small caps)
        return                                        # the first reflex that fires wins
```

```
────────────────────────────────────────────────────────────────────────────
what the MODEL does with it (the contract, not code)
────────────────────────────────────────────────────────────────────────────
turn 1 of a life with previous/  =  the WORKSHOP turn
    read previous/life_*/mine/{GUIDE,notes}.md and each life's death lines
    query ./tools/episodes.py --previous ... ; view the frames that matter
    write mine/GUIDE.md    (verified places with coordinates, life/step, episode id;
                            what each life died of and where; which scripts and reflexes
                            earned their keep; which assumptions broke)
    copy the scripts worth keeping into mine/procedures/ and mine/reflexes/
    end with a no-op plan (turns cost wall clock, not steps)

every later turn
    read [OBSERVED] against your own EXPECT; look at the cited frame when they differ
    grep logs.txt / query episodes when the present does not explain itself
    rewrite mine/working.md when the plan changes (< 40 lines)
    write ./actions.json: ≤ 40 entries of raw actions or own procedures, with an EXPECT line
    write a new procedure or reflex when the same action sequence recurs or the same
    event keeps killing you; write each reflex firing into mine/notes.md

between lives
    nothing is summarised for you; the next life reads what you wrote under mine/
```
