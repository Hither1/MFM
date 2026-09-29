# location_current_surface_furnace_8528

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 8528
- updated_step: 10197
- depends_on: goal_furnace, location_current_ascent_8208

## Statement

The current-run surface furnace is centered at (-2992.5,64.5,-5564.5); aiming there from (-2991.19,63.00,-5563.27) opened its GUI at step 10191, correcting the prior one-block-east center.

## Evidence

- At step 8528 place_block produced [INV] furnace -1 while the player was at (-2991.91,65.16,-5564.71), pitch 90; the attached frame shows the furnace top directly under the crosshair.
- Inventory lost furnace at step 8528 and events records use_item furnace at step 8531; no later mine_block furnace event exists through 8938.
- At placement step 8525 the player was at x=-2992.40 before place_block, so the downward target occupied x block -2993; the step-10183 frame shows the furnace left of the failed ray to x=-2991.5, and two exact opens on that old ray failed. The corrected center is therefore x=-2992.5; successful GUI opening will confirm it.
- After two failed opens aimed at (-2991.5,64.5,-5564.5), look_at(-2992.5,64.5,-5564.5) at step 10186 followed by use_until_gui opened the furnace GUI at step 10191; it remains open at step 10197.
- Step 10186 look_at the corrected center followed by use_until_gui; GUI open=True at step 10191 and the attached furnace screen is visible.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
