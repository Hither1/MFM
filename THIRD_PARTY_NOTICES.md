# Third-party code

This repository is released under the MIT licence (`LICENSE`). It contains or is derived
from the following work of others. Licences were read from the upstream repositories on
2026-10-13.

| part of this repository | origin | licence |
|---|---|---|
| `CUA-KiCad/model_channel/` (sandbox, Claude Code channel), `MCU/mcu_worldmodel/claude_backend.py`, the append-only log of the MFM workspace (`logs.txt`; `mfm/memory/log.py`, `CUA-KiCad/gym_codex/mfm_agent.py`) | written for this repository after the design of PRO-LONG, <https://github.com/alexisfox7/PRO-LONG> | MIT, Copyright (c) 2026 PRO-LONG authors: `licenses/PRO-LONG-MIT.txt` |
| the loop section of the short Minecraft contract (`MCU/mcu_worldmodel/prompts.py` `_THIN_LOOP`) and the layout of the skill package (`SKILL.md` with `scripts/` beside it, `MCU/mcu_worldmodel/skills.py`) | written after the `SKILL.md` of Codex-Minecraft-Gameplay, <https://github.com/wz1119/Codex-Minecraft-Gameplay> | Apache 2.0: `licenses/Codex-Minecraft-Gameplay-Apache-2.0.txt` |
| `MCU/src/`, `MCU/MCU_benchmark/`, `MCU/client.py`, `MCU/models.py`, `MCU/test_evaluation.py`, `MCU/pyproject.toml`, `MCU/uv.lock`, with the changes listed in `MCU/README.md` | MCU-AgentBeats, <https://github.com/KWSMooBang/MCU-AgentBeats>, a fork of the MCU benchmark, <https://github.com/CraftJarvis/MCU> | MCU-AgentBeats states "MIT License" in its README and ships no licence file; CraftJarvis/MCU ships no licence file and its README names no licence |

Not contained in this repository, installed by the user: MineStudio
(<https://github.com/CraftJarvis/MineStudio>, MIT; installed by `uv` at the commit in
`MCU/uv.lock`) and its simulator engine, cua-lite (<https://github.com/cua-lite/cua-lite>),
cua-bench and the cua packages (<https://github.com/trycua/cua>, MIT), the
`trycua/cua-xfce` desktop image, KiCad, Minecraft, the Codex CLI and Claude Code.
