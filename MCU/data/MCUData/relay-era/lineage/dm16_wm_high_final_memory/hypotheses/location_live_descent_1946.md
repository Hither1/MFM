# location_live_descent_1946

- kind: location
- status: refuted
- confidence: 0.00
- created_step: 1946
- updated_step: 1800
- depends_on: resource_wooden_pickaxe_secure, goal_wooden_pickaxe, goal_mine_cobblestone

## Statement

The claimed step-1800 pose (-3004.70,64,-5565.01) belongs to another trajectory and is not a live location.

## Evidence

- Step 2042 frame visibly shows a narrow dirt shaft with stone at its bottom. The preceding dig_down broke grass and two dirt blocks but reported descended 0.0 and diagnosed that the player was not centered over the column.
- The step-2231 state is (-2998.70,55.00,-5564.70), and dig_down reports six blocks broken, 8.5 blocks descended, and target depth reached.
- visited.csv at step 1200 ends at y67 and events have no stone breaks; all cited y55 evidence is after this checkpoint.
- Step-1347 STATE fixes the position and reports dig_down stopped because blocks broke without descent; mine_block stone fired at step 1253, and the attached downward frame shows stone at the shaft bottom.
- Step 1253 verified a stone break, while the step-1407 dig_down broke zero blocks at pitch 88 and the attached downward frame shows an open shaft; x=-3004.20 places the avatar against the east edge of the centered column.
- Ground-truth STATE at step 1652 gives y64, pitch 0, yaw 0; the attached frame shows a traversable stone/dirt tunnel and the last action broke its centered cobblestone block.
- STATE/visited rows at 1800 fix the position and facing; events at 1730-1784 show stone/dirt breaks and cobblestone pickups at 1763/1764.
- Current-run STATE and final visited segment place step 1800 at (-3003.40,55.12,-5561.30).

<!-- projection of hypotheses/graph.json; edits here are overwritten. Change a belief by sending a hypothesis op. -->
