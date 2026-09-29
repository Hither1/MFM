# location_direct_west_return_tunnel_6654

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 6654
- updated_step: 7525
- depends_on: location_live_coal_shaft_2814, location_return_blocked_by_furnace_6570, location_live_east_branch_3600, location_live_return_shaft_3449

## Statement

The direct west return tunnel is now traversal-verified through the shaft foot at (-3007.8,55,-5559.7); step 7525 also verified one cobblestone foundation placement immediately west/downward for re-entering the coal shaft column.

## Evidence

- Step 6826/6831 frames show a lit west corridor with one dark floor void; sprint-jump and go_to made no horizontal progress. The step-6828 use aimed diagonally at (-2994.5,54.5,-5560.5) produced no use_item event and inventory remained cobblestone x57.
- At step 6833 inventory lost one cobblestone, proving placement. Step 6836 go_to still moved only 0.03 blocks, and the new frame shows a cobblestone block filling the passage directly ahead where the pre-placement step-6784 frame showed open air over a floor void.
- Authoritative step-6924 STATE records 1.12 blocks of real movement and a safe one-block descent to y54 during plain forward movement; two cobblestone pickups verify the freshly cleared entry was crossed.
- Step 6924 safely entered the lower passage, but 120 ticks of level forward movement at yaw 90 through step 7046 produced exactly 0.00 movement and the current frame shows a close stone face.
- From step 6924 to 7152, targeted westward mining broke six more blocks and the authoritative pose advanced from x=-2994.7 to x=-2996.93. The current frame shows a lit one-wide tunnel continuing west, but the last mining macro stopped after only 1.7 blocks of advance, so the remaining route is not yet verified.
- At live step 7169, go_to advanced 3.79 real blocks west from x=-2996.93 to x=-3000.72, collected three fresh cobblestone drops, and stopped 7.6 blocks short at the next stone closure; the attached frame shows a straight lit tunnel ahead.
- Authoritative STATE/maps reach x=-3000.80 by step 7200; frame 7200 shows the trench and corridor. At step 6924 raw forward crossed the prior identical trench while go_to refused it.
- Steps 7402-7492 cleared and crossed the final west closures to x=-3007.70; step 7495 reached y55 within 0.6 blocks of the historical shaft centre; step 7525 consumed one cobblestone and fired use_item while aimed down at the shaft foot.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
