# Third-party code

This repository is released under the MIT licence (`LICENSE`). It contains or is derived
from the following work of others. Licences were read from the upstream repositories on
2026-09-30.

| part of this repository | origin | licence |
|---|---|---|
| `mfm/vista/`, `MCU/mcu_worldmodel/vista.py`, `CUA-KiCad/gym_codex/vista_agent.py` | a port of VISTA, <https://github.com/joshhhhhan/VISTA> (commit 900aa33, `src/vista_arc3/codex/`); what is ported is listed in `mfm/vista/__init__.py` | MIT, Copyright (c) 2026 VISTA contributors: `licenses/VISTA-MIT.txt` |
| `CUA-KiCad/prolong_search/` (sandbox, Claude Code channel), `MCU/mcu_worldmodel/claude_backend.py`, the log format of the `logbook` / `prolong-logonly` arms | written for this repository after the design of PRO-LONG, <https://github.com/alexisfox7/PRO-LONG> | MIT, Copyright (c) 2026 PRO-LONG authors: `licenses/PRO-LONG-MIT.txt` |
| `MCU/minestudio/` | MineStudio, <https://github.com/CraftJarvis/MineStudio>, as vendored by MCU-AgentBeats | MIT, Copyright (c) 2024 Shaofei Cai: `licenses/MineStudio-MIT.txt` |
| `MCU/minestudio/simulator/minerl/Malmo/` | Project Malmo (Microsoft) with Minecraft Forge | MIT (`Malmo/LICENSE.txt`); Minecraft Forge LGPL 2.1 (`Malmo/Minecraft/LICENSE-new.txt`) |
| `MCU/minestudio/data/minecraft/tools/idm_lib/` | OpenAI Video PreTraining | MIT (`LICENSE` in that directory) |
| `MCU/minestudio/utils/mineclip_lib/` | MineCLIP (MineDojo) | MIT (`license` in that directory) |
| `MCU/minestudio/utils/realtime_sam/` | SAM 2 real-time | Apache 2.0 and BSD 3-Clause (`LICENSE`, `LICENSE_cctorch` in that directory) |
| `MCU/MCU_benchmark/`, `MCU/src/`, `MCU/tutorial/`, `MCU/docs/`, `MCU/scripts/` (the evaluation scripts), the files at the top of `MCU/` other than `worldmodel_purple_agent.py` and `task_milestones.py` | MCU-AgentBeats, <https://github.com/KWSMooBang/MCU-AgentBeats>, a fork of the MCU benchmark, <https://github.com/CraftJarvis/MCU> | MCU-AgentBeats states "MIT License" in its README and ships no licence file; CraftJarvis/MCU ships none |

Not contained in this repository, installed by the user: cua-lite
(<https://github.com/cua-lite/cua-lite>), cua-bench and the cua packages
(<https://github.com/trycua/cua>, MIT), the `trycua/cua-xfce` desktop image, KiCad,
Minecraft, the Codex CLI and Claude Code.
