# MCU: the Minecraft benchmark and harness

This directory contains MCU-AgentBeats
(<https://github.com/KWSMooBang/MCU-AgentBeats>), a fork of the MCU benchmark
(<https://github.com/CraftJarvis/MCU>), and the Minecraft harness of MFM. For the setup
and the run commands, see the [README](../README.md) at the top of the repository.

| Path | Origin | Content |
| --- | --- | --- |
| `src/` | MCU-AgentBeats | The environment server (the green agent). It runs the simulator and verifies the milestones. |
| `MCU_benchmark/` | MCU benchmark, MCU-AgentBeats | The configurations of the three tasks, the milestone tracker, and the prompts and criteria of the video rating. |
| `client.py`, `models.py`, `test_evaluation.py` | MCU-AgentBeats | The evaluation client and the message types. |
| `pyproject.toml`, `uv.lock` | MCU-AgentBeats | The Python environment, with MineStudio at commit 278aa85. |
| `mcu_worldmodel/` | MFM | The harness: arms, contracts, procedures, perception and memory. See [`mcu_worldmodel/README.md`](mcu_worldmodel/README.md). |
| `worldmodel_purple_agent.py` | MFM | The agent server (the purple agent). |
| `task_milestones.py` | MFM | The milestone list of each task, read by the agent from the public task configuration. |
| `camera_contract.py` | MFM | The camera rules that all arms get. |
| `env.sh`, `scripts/` | MFM | The run environment, the launcher (`run-arm.sh`) and its helpers. |

## Tasks

| Task | Configuration | Milestones | Step budget | World seed |
| --- | --- | ---: | ---: | ---: |
| `mine_diamond_from_scratch` | `MCU_benchmark/task_configs/tasks/mine_diamond_from_scratch/` | 10 | 12,000 | 0 |
| `ender_dragon` | `MCU_benchmark/task_configs/tasks/ender_dragon/` | 24 | 36,000 | 0 |
| `nether_portal` | `MCU_benchmark/task_configs/tasks/nether_portal/` | 2 | 6,000 | 42 |

The score of a life is the number of milestones that the environment verified, in any
order (`sim_score` in `logs/<arm>_result.json`).

## Changes to MCU-AgentBeats

- A task configuration can set the world seed (`world_seed`), and `--world-seed` of
  `scripts/run-arm.sh` replaces it.
- The task `nether_portal` (the case study of the paper) is new.
- The environment server sends the frame and a fixed list of simulator fields to the
  agent (`INFO_PASSTHROUGH` in `src/agent.py`). It does not send the milestone results.
- Each server writes its results in its own directory (`output/<date>_<pid>/`), so two
  servers on one host do not write to the same files.
- The environment server accepts only the three tasks above.
