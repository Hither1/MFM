# Getting MCU to actually run on this cluster

Four things were broken or missing. None of them announces itself clearly, and three of the
four fail at import or reset time with an error that points somewhere else.

## 1. The checked-in MineStudio is partly gutted

**21 files under `minestudio/simulator/minerl/herobraine/hero/handlers/agent/` were
0 bytes** — every module in `actions/` and `observations/`, including `pov.py`,
`inventory.py`, `location_stats.py`, `mc_base_stats.py` and their `__init__.py`s. They are
0 bytes *in the commit*, not just in the working tree.

The symptom is misleading: `AttributeError: module '...hero.handlers' has no attribute
'POVObservation'. Did you mean: 'observations'?` — which reads like an import-order problem
and is actually an empty file.

Fixed by restoring from the `minestudio==1.1.6` in the conda env's site-packages, which is
complete:

```bash
SP=~/miniforge3/envs/minestudio/lib/python3.10/site-packages/minestudio
for f in $(find minestudio/simulator/minerl/herobraine/hero/handlers/agent -name "*.py" -size 0); do
  cp "$SP/${f#minestudio/}" "$f"
done
```

The other 9 zero-byte `.py` files in the repo are legitimately-empty `__init__.py` and
should be left alone.

## 2. `hero/mc_constants.1.16.json` was truncated

Truncated at exactly 1310720 bytes (1280 KiB). It parses far enough to import and then dies
with `JSONDecodeError: Expecting property name ... (char 1310720)`. The complete copy is
already in the repo at `minestudio/utils/vpt_lib/mc_constants.1.16.json` (1379016 bytes) and
is byte-identical over the truncated prefix:

```bash
cp minestudio/utils/vpt_lib/mc_constants.1.16.json \
   minestudio/simulator/minerl/herobraine/hero/mc_constants.1.16.json
```

`hero/mc_constants.json` is truncated the same way but is never loaded by anything — leave it.

## 3. `cuda-python` 13.x breaks the simulator's GPU probe

`minestudio/simulator/minerl/env/gpu_utils.py` does `from cuda import cuda, cudart` at module
level. cuda-python 13 moved that API to `cuda.bindings`, so the import raises, the subprocess
exits non-zero, and `malmo.py` turns it into `Exception: An error occured in gpu_utils.py`
during `sim.reset()` — with no mention of cuda in the traceback.

The script only *needs* to import: with `MINESTUDIO_GPU_RENDER` unset it prints `cpu` and
exits, which is what we want for CPU rendering.

```bash
pip install "cuda-python<13"     # 12.9.7
```

## 4. The engine jar and `MINESTUDIO_DIR`

`MinecraftSim` calls `check_engine()` at **class-definition time** and, if the jar is missing,
calls `input()` — an `EOFError` at import in any batch job. Download it once to a path that
persists across nodes:

```bash
unset HF_HUB_OFFLINE          # set in this account's profile; the download fails silently-ish without this
export MINESTUDIO_DIR=/n/netscratch/sham_lab/Lab/$USER/MineStudio
python -c "
import os, zipfile, huggingface_hub
d = os.environ['MINESTUDIO_DIR']
p = huggingface_hub.hf_hub_download('CraftJarvis/SimulatorEngine', 'engine.zip', local_dir=d)
zipfile.ZipFile(p).extractall(d)"
```

Yields `$MINESTUDIO_DIR/engine/build/libs/mcprec-6.13.jar` (466 MB). `MINESTUDIO_DIR` must be
exported **before** python starts, in every job.

## Running

Java 8 (`/usr/bin/java`, 1.8.0_504) and `xvfb-run` are already on the nodes. No GPU is
needed — this agent is API-driven, not a neural policy — so a CPU partition is fine:

```bash
export MINESTUDIO_DIR=/n/netscratch/sham_lab/Lab/$USER/MineStudio
xvfb-run -a -s "-screen 0 1024x768x24" python -m mcu_worldmodel.run --task diamond
```

## 5. Instance directories must be on node-local disk, not NFS

`InstanceManager` derives everything from `MINESTUDIO_DIR`, including the per-instance
working directory it copies a runtime into and launches Minecraft with as its **cwd**. With
`MINESTUDIO_DIR` on netscratch the JVM dies during startup:

```
NoClassDefFoundError: Could not initialize class java.nio.file.FileSystems$DefaultFileSystemHolder
Caused by: sun.nio.fs.UnixException: No such file or directory
```

plus `Stale file handle` writing the crash report. Java initialises its default FileSystem
by stat-ing the working directory, and NFS intermittently returns ESTALE. The error names
neither NFS nor the working directory and reads like a broken JRE.

`mcu_worldmodel/setup_env.sh` builds a node-local `MINESTUDIO_DIR` with only `engine`
symlinked back to the shared copy — instance dirs, runtime and crash reports stay local,
and the 466 MB jar is not copied per job. Use it in every job:

```bash
export MINESTUDIO_DIR=$(./mcu_worldmodel/setup_env.sh)
```

## 6. Codex authentication

`~/.codex/auth.json` holds a ChatGPT subscription token whose refresh token is spent
("your refresh token was already used"), so every turn 401s. The API-key path works and is
what the launcher uses:

```bash
export CODEX_HOME=<per-episode dir>
printenv OPENAI_API_KEY | codex login --with-api-key
```

Verified end-to-end against `gpt-5.6-sol`: the turn wrote a valid `actions.json` and
replied with `[PLAN]`.

## 7. There is no crafting action, and it cannot be added

See `mcu_worldmodel/craft_env.py` and the README. Short version: the engine
(`com.minerl.multiagent.env.EnvServer`) implements only

```
attack back camera chat drop dwheel equip forward hotbar
inventory jump left pickItem right sneak sprint swapHands use ESC
```

`craft` / `nearbyCraft` / `nearbySmelt` / `place` are absent; `equip` takes a number, not an
item name. Installing MineRL's item-list handlers makes the env fail at `reset()`. Crafting
has to go through the inventory GUI, which works (`crafting_table` milestone reached at step
514 of a live run).
