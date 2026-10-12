#!/usr/bin/env bash
# Set up the Minecraft benchmark (MCU-AgentBeats on MineStudio). No root is needed.
#
#   bash scripts/env_setup/minecraft.sh
#
# The script does these steps and skips each one that is already done:
#   1. makes MCU/.venv from MCU/uv.lock (Python 3.11, MineStudio);
#   2. installs JDK 8 (Eclipse Temurin) in $MCU_PREFIX/jdk8 if no JDK 8 is found;
#   3. installs Xvfb in $MCU_PREFIX/xvfb if xvfb-run is not found;
#   4. downloads the simulator engine (about 450 MB) to $MCU_PREFIX/MineStudio/engine.
#
# MCU_PREFIX defaults to ~/.local/opt/mcu. MCU/env.sh, which scripts/run-arm.sh sources,
# puts $MCU_PREFIX/jdk8 and $MCU_PREFIX/xvfb on PATH and copies the engine to
# $MINESTUDIO_DIR (default /tmp/MineStudio-$USER, which must be on a local disk).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MCU_PREFIX="${MCU_PREFIX:-$HOME/.local/opt/mcu}"
mkdir -p "$MCU_PREFIX"

# 1. The Python environment
command -v uv >/dev/null || { echo "uv is not installed: https://docs.astral.sh/uv/" >&2; exit 1; }
(cd "$ROOT/MCU" && uv sync --frozen)

# 2. JDK 8
has_jdk8() { [ -x "$1" ] && "$1" -version 2>&1 | grep -q 'version "1\.8'; }
if has_jdk8 "$MCU_PREFIX/jdk8/bin/java" || has_jdk8 "$(command -v java || true)"; then
    echo "JDK 8: found"
else
    echo "JDK 8: downloading Eclipse Temurin 8 to $MCU_PREFIX/jdk8"
    rm -rf "$MCU_PREFIX/jdk8" && mkdir -p "$MCU_PREFIX/jdk8"
    TMP="$(mktemp -d)"
    "$ROOT/MCU/.venv/bin/python" - "$TMP/jdk8.tar.gz" <<'EOF'
import sys

import requests

URL = "https://api.adoptium.net/v3/binary/latest/8/ga/linux/x64/jdk/hotspot/normal/eclipse"
with requests.get(URL, stream=True, timeout=60) as r, open(sys.argv[1], "wb") as f:
    r.raise_for_status()
    for chunk in r.iter_content(1 << 20):
        f.write(chunk)
EOF
    tar -xzf "$TMP/jdk8.tar.gz" -C "$MCU_PREFIX/jdk8" --strip-components=1
    rm -rf "$TMP"
    has_jdk8 "$MCU_PREFIX/jdk8/bin/java"
fi

# 3. Xvfb
if command -v xvfb-run >/dev/null || [ -x "$MCU_PREFIX/xvfb/usr/bin/xvfb-run" ]; then
    echo "Xvfb: found"
elif command -v apt-get >/dev/null && command -v dpkg >/dev/null; then
    echo "Xvfb: unpacking the xvfb package to $MCU_PREFIX/xvfb"
    TMP="$(mktemp -d)"
    (cd "$TMP" && apt-get download xvfb)
    dpkg -x "$TMP"/xvfb_*.deb "$MCU_PREFIX/xvfb"
    rm -rf "$TMP"
    "$MCU_PREFIX/xvfb/usr/bin/Xvfb" -help >/dev/null 2>&1 \
        || { echo "Xvfb does not start. Install it as root: apt-get install xvfb" >&2; exit 1; }
else
    echo "Xvfb is not installed. Install the package that gives xvfb-run (Debian/Ubuntu: xvfb)." >&2
    exit 1
fi

# 4. The simulator engine. MineStudio asks for it on stdin at import time when it is
# missing, so a batch run fails without it.
if [ -f "$MCU_PREFIX/MineStudio/engine/build/libs/mcprec-6.13.jar" ]; then
    echo "Engine: found"
else
    echo "Engine: downloading CraftJarvis/SimulatorEngine to $MCU_PREFIX/MineStudio"
    MINESTUDIO_DIR="$MCU_PREFIX/MineStudio" "$ROOT/MCU/.venv/bin/python" - <<'EOF'
import os
import zipfile

import huggingface_hub

d = os.environ["MINESTUDIO_DIR"]
p = huggingface_hub.hf_hub_download("CraftJarvis/SimulatorEngine", "engine.zip", local_dir=d)
zipfile.ZipFile(p).extractall(d)
os.remove(p)
EOF
    test -f "$MCU_PREFIX/MineStudio/engine/build/libs/mcprec-6.13.jar"
fi

echo "Done. Check the simulator with:"
echo "  cd MCU && source env.sh && xvfb-run -a .venv/bin/python -c 'from minestudio.simulator import MinecraftSim'"
