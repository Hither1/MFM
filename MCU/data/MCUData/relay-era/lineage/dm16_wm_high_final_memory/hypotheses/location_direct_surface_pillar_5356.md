# location_direct_surface_pillar_5356

- kind: location
- status: confirmed
- confidence: 1.00
- created_step: 5356
- updated_step: 9200
- depends_on: goal_mine_iron_ore, location_current_crafting_table, resource_current_cobblestone, mechanism_pitch88_pillar_ascent_3149

## Statement

This-run column B at x=-2996.70,z=-5563.70 is a completed capped pillar from y55 to y65; step 8970 exited west safely to the surface table. The older z=-5564.70 opening was only a partial approach, not the final full ascent.

## Evidence

- Final STATE at step 5850 is y62. Cobblestone placement events and inventory deltas verify seven ascent levels, while mine_ahead through step 5766 broke one stone and two dirt directly overhead. Failed go_to attempts briefly reached y63.18, showing the open shaft extends at least one more level, but the player lacked cobblestone selected during those attempts.
- Cobblestone use events at steps 5864 and 5873 plus STATE y64.00 at step 5911 verify the final two pillar levels and complete the direct surface return.
- visited.csv and matching stone events show the same column re-dug from y65 to y55 during steps 7468-7643; final pose is (-2996.31,55,-5564.70).
- Steps 8024-8032 moved from the exhausted iron face into the shaft cell. Steps 8092-8182 show repeated four-tick jumps peaking only at y55.20, no cobblestone decrement, and no use_item event, which is the established close-ceiling signature; the same column was previously re-dug from surface to y55 and ascended to y64.
- Historical states fix the successful ascent column at (-2996.70,-5564.62/-5564.30), while steps 8092-8348 failed from the adjacent wrong cell at z=-5563.87. The step-8361 go_to moved south into the correct cell at z=-5564.70; current pitch-88 frame shows the underfoot block and enclosing vertical column.
- Overhead cobble breaks fired at 8398/8419/8440, pickups followed through 8457, and frame 8600 looks straight up the open shaft from the fixed pose.
- Events record the final cobblestone placements through step 8961; authoritative step-8970 STATE is (-2997.87,64.42,-5563.62), and the attached frame shows the surface crafting table, grass, and the capped pillar underfoot.
- Cobblestone/dirt use deltas and final map rows trace x=-2996.70,z=-5563.70 from y55 to y65 through step 8961; step 8970 reaches (-2997.87,64.42,-5563.62) beside the table.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
