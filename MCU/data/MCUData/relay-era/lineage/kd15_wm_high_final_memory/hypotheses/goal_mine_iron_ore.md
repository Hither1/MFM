# goal_mine_iron_ore

- kind: goal
- status: confirmed
- confidence: 1.00
- created_step: 0
- updated_step: 6669
- depends_on: goal_stone_pickaxe, location_current_east_tunnel_4200, location_current_dry_tunnel_4200, location_current_iron_face_6000

## Statement

The current reset achieved mine_iron_ore at step 6669 when the third block on the true straight-up ray from (-2985.70,41.00,-5584.07) broke as iron ore with the stone pickaxe.

## Evidence

- Current events through step 5400 contain no iron break. Final-reset visited rows and frame 5400 fix the live pose; locations/ore_registry.md proves iron near (-2985.5,44,-5581.7), including a prior break from (-2986.30,44,-5580.70).
- The step-5516 state and final visited rows prove another 2.0-block north advance from z=-5568.70 to z=-5570.70. Current events contain no iron break yet; locations/ore_registry.md records iron near (-2985.5,44,-5581.7), with a prior successful break from (-2986.30,44,-5580.70).
- Step 5906 mine_forward report verifies 8.0 blocks of northward advance to z=-5578.70 with 86 stone-pick uses remaining and no current iron event; locations/ore_registry.md records a prior iron break from (-2986.30,44,-5580.70) and the vein near (-2985.5,44,-5581.7).
- Final-reset visited rows end at the stated pose. Events through 6000 contain no iron break, while ore_registry preserves a prior successful break from (-2986.30,44,-5580.70).
- Events through step 6247 contain no iron break. The selected stone pick has 76 uses, and the attached frame's magnified upper wall clearly shows the registered vein while the current crosshair rests on plain stone below it.
- Events through step 6445 show only stone and diorite breaks. The step-6247 magnified frame visibly places iron textures above the failed ray; current STATE is (-2986.21,42,-5582.35), so the surviving face is now southeast and overhead. Placing the held furnace frees one inventory slot for the ore drop.
- Events through 6600 contain no iron. Frame 6247 visibly confirms the vein, while steps 6007-6578 show only stone/diorite on the two coordinate rays; final visited rows place the player at (-2985.70,41,-5583.80).
- events/events.jsonl records the mine_iron_ore milestone, mine_block iron_ore +1, and use_item stone_pickaxe +1 at step 6669.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
