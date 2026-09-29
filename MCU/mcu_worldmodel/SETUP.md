# Getting the simulator to run

The benchmark is MCU-AgentBeats on MineStudio; its own README (one directory up) covers
the Python environment (`uv sync`). What follows is what the arms need beyond that, and
the failures that do not announce themselves.

## Requirements

- JDK 8 and `xvfb-run`. No GPU: the arms are API-driven and the recorded runs rendered
  on the CPU.
- The Codex CLI (`codex`) for the GPT arms, Claude Code (`claude`) for the Claude arms,
  logged in or keyed (see `scripts/codex-home.sh`, `scripts/claude-home.sh` and
  `--route openrouter` of `scripts/run-arm.sh`).
- On Linux the Claude Code sandbox needs `bubblewrap` and `socat` on PATH.

## The engine and `MINESTUDIO_DIR`

`MinecraftSim` calls `check_engine()` at class-definition time and, if the engine jar is
missing, calls `input()` -- an `EOFError` at import in any batch job. Download it once:

```bash
export MINESTUDIO_DIR=/path/on/a/local/disk/MineStudio
python -c "
import os, zipfile, huggingface_hub
d = os.environ['MINESTUDIO_DIR']
p = huggingface_hub.hf_hub_download('CraftJarvis/SimulatorEngine', 'engine.zip', local_dir=d)
zipfile.ZipFile(p).extractall(d)"
```

This yields `$MINESTUDIO_DIR/engine/build/libs/mcprec-6.13.jar`.

`MINESTUDIO_DIR` must be on a local disk. MineStudio derives the per-instance working
directory from it and launches Minecraft with that as its cwd; on NFS the JVM dies at
startup with

```
NoClassDefFoundError: Could not initialize class java.nio.file.FileSystems$DefaultFileSystemHolder
Caused by: sun.nio.fs.UnixException: No such file or directory
```

which names neither NFS nor the working directory. The instance registry (sqlite) fails
on NFS as well. `env.sh` sets a local `MINESTUDIO_DIR` under `/tmp` and restores the
engine from `$MCU_PREFIX/MineStudio/engine` when a persistent copy is kept there.

## `cuda-python` 13 breaks the simulator's GPU probe

`minestudio/simulator/minerl/env/gpu_utils.py` imports `from cuda import cuda, cudart`
at module level; cuda-python 13 moved that API, the import raises, and `sim.reset()`
fails with `Exception: An error occured in gpu_utils.py`, with no mention of cuda.

```bash
pip install "cuda-python<13"
```

## There is no crafting action

The engine implements

```
attack back camera chat drop dwheel equip forward hotbar
inventory jump left pickItem right sneak sprint swapHands use ESC
```

and nothing else: `craft`, `nearbyCraft`, `nearbySmelt` and `place` are absent, and
`equip` takes a number. Crafting goes through the inventory GUI (`gui.py`,
`macros_gui.py`). `craft_env.py` adds `drop`, the one verb the engine supports and the
simulator's action spec leaves out.
