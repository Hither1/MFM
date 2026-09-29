# The relay family tree

Scores are milestones (score/100). Arrows mean "final memory seeded the next run".
`==>` crosses tasks. Only wave-4+ trajectories are packaged here; earlier ancestors
(waves 1-3, which built the first registries) appear as the initial memory state
inside their children's trajectories.

## Distilled relay (worldmodel memory)

    diamond:  kd12 (dragon 7/24) ==> dm14x 9/10 (90.0) --> dm15 9/10 (90.0) --> dm16 10/10 (100.0) --> dm17 (in flight)
    dragon:   dm11c (diamond 9/10) ==> kd14x 11/24 (45.83) --> kd15 9/24 (37.5)
                                       kd14x --> kd16 9/24 (37.5)
              dm16 ==> kd17 (in flight, cross-task probe)

## Raw-log relay (logbook memory, the ablation)

    diamond:  dm10_lb (6/10) --> dm15_lb 6/10 (60.0)   [below the from-scratch control]
    dragon:   kd10_lb (6/24) --> kd15_lb 8/24 (33.33)

## From-scratch controls (no seed)

    dm15z 7/10 (70.0), kd15z 7/24 (29.17)

## What is in <arm>_final_memory/

Each directory is that run's distilled memory as it stood at episode end — world_model/,
locations/ (incl. the ore registry with per-run exhaustion annotations), procedures/,
hypotheses/, entities/, maps/, tools/, notes/, AGENTS.md — with the operational bulk
(logs.txt, frame episodes, event stream, action buffer) stripped. Diffing consecutive
generations (dm14x -> dm15 -> dm16) shows what each life added; dm16's registry entry for
the diamond site at y12 is the artefact that made its 10/10 fast.
