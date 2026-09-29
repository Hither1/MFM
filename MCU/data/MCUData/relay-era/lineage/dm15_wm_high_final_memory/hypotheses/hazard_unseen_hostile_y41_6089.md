# hazard_unseen_hostile_y41_6089

- kind: state
- status: confirmed
- confidence: 0.90
- created_step: 6089
- updated_step: 6600
- depends_on: location_fresh_y41_east_branch_6055, location_fresh_y47_strip_5508

## Statement

The y41 cave beside (-2988,41,-5542) contained a confirmed armed skeleton whose repeated five-damage shots killed the player; its present survival after respawn is unverified, so treat the firing lane as hazardous during recovery.

## Evidence

- Step 6108 frame visibly shows an armed skeleton at the right edge, approximately 20 degrees right of the crosshair, while the pickaxe is striking the central stone block. Health previously fell from 20 to 17 and then 14 at the same fixed position.
- Health fell 20→17→14 at the fixed y41 position. Frames 6108 and 6126 show the armed skeleton moving from the right edge to near center while attack events at 6108 and 6126 only broke stone, proving prior aim was still on the foreground blocks.
- Frames 6108, 6126, and 6130 show the armed skeleton; events record only stone breaks, no entity kill, while damage notes reduce health 20->17->14->9 at the same y41 endpoint.
- Frames 6108-6130 show the armed skeleton and no kill event occurred. Damage reduced health 20->17->14->9. At step 6139 use_item cobblestone and inventory -1 verify the first defensive block; the player then backed 0.47 blocks without another damage note through 6141.
- Frames 6108-6130 visibly show the armed skeleton. No kill_entity event exists. Only one use_item cobblestone event occurred at 6139, and damage recurred at step 6168 behind the incomplete cover, reducing health from 9 to 4.
- Damage notes at steps 6089, 6130, 6168, and 6208 each report 5 damage while stationary; the skeleton and bow are visible at the left edge of the latest cave frame.
- Frames 6208 and 6229 show no respawn transition or inventory loss after 21 ticks at reported 0/20. Frame 6208 visibly shows the skeleton at the far-left edge beyond the low barrier, while frame 6229 shows a half-heart icon and the same cave position.
- Frames 6108-6208 show the skeleton; repeated damage notes culminate in death at step 6248, with no kill_entity event.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
