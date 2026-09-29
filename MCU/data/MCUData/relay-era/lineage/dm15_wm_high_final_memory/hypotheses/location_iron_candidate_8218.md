# location_iron_candidate_8218

- kind: location
- status: refuted
- confidence: 1.00
- created_step: 8218
- updated_step: 9600
- depends_on: goal_mine_iron_ore, location_productive_west_stair_6600

## Statement

The alleged step-8218 iron candidate is future-trajectory contamination and is not a location in the authoritative step-9600 run.

## Evidence

- The step-8218 ore watcher localized a 54-pixel patch at screen (309,202); a 4x crop of the flag-time frame clearly shows characteristic tan-speckled iron texture spanning multiple adjacent floor faces.
- events/events.jsonl records mine_block iron_ore at step 8247; the magnified step-8260 frame shows another centered iron face and a further iron-textured floor block.
- Mine_block iron_ore fired at 8247 and 8276; pickup iron_ore +2 fired at 8319. No third iron event exists through 8400.
- Claim cites step 8218 while current step is 4200 and no iron event exists.
- Authoritative events through 9583 contain no iron event, while the candidate file cites contradictory events absent from events/events.jsonl.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
