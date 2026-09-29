# state_inventory_4800

- kind: state
- status: confirmed
- confidence: 1.00
- created_step: 4800
- updated_step: 4800
- depends_on: goal_stone_pickaxe, goal_furnace, location_gui_drop_cache_ep0000_4768

## Statement

At authoritative step 4800 the hotbar holds wooden pickaxe, cobblestone x3, dirt x7, sand x2, fresh stone pickaxe, and furnace in slots 0-5; slots 6-8 are empty. Cobblestone x11 and sticks x2 are nearby floor entities, not inventory.

## Evidence

- The step-4800 hotbar crop shows these five stacks; events record furnace pickup at 4576 and dirt/cobblestone pickups at 4795/4796.
- After step 4800, events record wooden_pickaxe pickup at 4994, two dirt and one cobblestone placements, and numerous dirt pickups through 5367.
- Step-4800 hotbar crop plus accounting: step-4200 stacks were cobble x8/dirt x8, then +9 cobble, +12 dirt, dirt x16 dropped, and 20 stone-pick uses.
- Attached step-4800 hotbar crop gives exact visible stacks; 20 current stone-pick use events have occurred since craft, and the furnace is placed at the surface.
- A magnified crop of step_4800 gives stack counts and two empty slots; events count 52 stone-pick uses after its step-3377 craft and contain no iron/furnace event.
- Events and the magnified step-5400 hotbar supersede this exact earlier snapshot.
- Magnified frame 4800 gives the six stacks; logs at 4765 banks furnace, and the 4768 forced-close note explicitly reports cobblestonex11 and stickx2 dropped.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
