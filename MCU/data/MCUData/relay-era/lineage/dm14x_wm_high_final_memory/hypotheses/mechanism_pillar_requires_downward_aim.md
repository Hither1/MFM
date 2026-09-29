# mechanism_pillar_requires_downward_aim

- kind: mechanism
- status: confirmed
- confidence: 1.00
- created_step: 3600
- updated_step: 1901

## Statement

Pillar ascent requires pitch about 88, a selected placeable block, solid support below, and open body/head space; the first live open-shaft attempt at step 1901 consumed one dirt and raised y55 to y56, while identical attempts under the two-high spur ceiling failed.

## Evidence

- Eight pitch-88 cycles consumed cobblestone and raised y55 to y63 at steps 2463-2526; pitch-8 uses at 3590 and 3599 caused no inventory decrement or use_item event.
- Inherited open-shaft ascent succeeded at pitch 88; in the live run six 10-tick jump/use batches at pitch 88 under the north-spur ceiling caused no movement, use event, or inventory decrement.
- Authoritative step-1901 STATE reports y56 and [INV] dirt -1 after a ten-tick jump+use batch at pitch 88 in the recovered shaft column; six earlier identical batches under the spur ceiling changed nothing.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
