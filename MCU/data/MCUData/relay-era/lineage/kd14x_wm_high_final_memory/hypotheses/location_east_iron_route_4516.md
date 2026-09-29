# location_east_iron_route_4516

- kind: location
- status: active
- confidence: 0.90
- created_step: 4516
- updated_step: 5302
- depends_on: location_live_shaft_3600, goal_mine_iron_ore

## Statement

The y61 east tunnel from (-2998.70,-5568.30) reaches an exposed sand-and-dirt surface pocket near x=-2985 and is no longer a productive underground iron-search corridor; falling or uneven sand caused two break-without-advance cycles.

## Evidence

- Current ground-truth pose is directly over the known shaft with a fresh stone pick; existing graph evidence records the later iron break endpoint at y61 about 43 blocks east.
- Last-per-step visited rows show eastward advance to x=-2994.44; events 4622-4787 show ten ordinary stone breaks and no iron event.
- At step 5302 the player is at (-2985.45,62.02,-5568.30) in daylight amid sand and dirt. The step-4993 to 5302 mine_forward run broke dirt/sand only, found no ore, and stopped early after two cycles broke blocks without movement.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
