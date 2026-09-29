# location_diamond_level_east_tunnel_10800

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 10800
- updated_step: 10800
- depends_on: goal_iron_pickaxe

## Statement

Refuted as future-trajectory contamination: the live step-10800 location is the dark y55 south iron branch, not a lit y11 diamond tunnel.

## Evidence

- visited.csv bounds after 10589 and step 10800 frame establish the tunnel; events 10614-10791 show ten stone/diorite breaks and no diamond mine/pickup event.
- The step 10959 strip_mine note reports 18 blocks broken and 8.4 blocks of movement; events contain only stone/diorite/andesite mining, and the endpoint frame shows no cyan ore.
- visited.csv through 11400 fixes the endpoint; strip notes account for 14.1 blocks advanced after x=-3040.30, and latest frame shows the chamber and ore.
- Attached frame/current STATE and authoritative events show stone-pick mining at (-3019.7,55,-5592), while no iron pickaxe or diamond event exists.

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
