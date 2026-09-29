# Source this file before running anything in MCU-AgentBeats on this machine:
#   source env.sh
#
# This host has no root and no docker access, so JDK8 (required by the Minecraft
# engine) and Xvfb (required for headless OpenGL) are installed user-locally
# under $MCU_PREFIX instead of through apt.
export MCU_PREFIX="${MCU_PREFIX:-$HOME/.local/opt/mcu}"
export JAVA_HOME="$MCU_PREFIX/jdk8"
export PATH="$JAVA_HOME/bin:$MCU_PREFIX/xvfb/usr/bin:$PATH"

# /dev/dri/* is not readable by this user (not in the `render` group), so the
# VirtualGL/EGL render path is unavailable -> leave MINESTUDIO_GPU_RENDER off and
# let the engine render through Xvfb + Mesa llvmpipe (CPU, ~22 FPS per instance).
unset MINESTUDIO_GPU_RENDER

# MineStudio keeps a diskcache/sqlite instance registry under MINESTUDIO_DIR.
# $HOME is NFS (LeoFS), where sqlite locking fails with
# "OperationalError: cannot rollback - no transaction is active",
# so MINESTUDIO_DIR has to sit on the local ext4 disk.
export MINESTUDIO_DIR="/tmp/MineStudio-${USER:-$(id -un)}"
mkdir -p "$MINESTUDIO_DIR"

# /tmp is volatile: restore the 445MB engine from the persistent copy under
# $MCU_PREFIX rather than re-downloading it from HuggingFace.
# Several arms launched at once all see the jar missing and race the copy: on
# 2026-09-06 two of four launchers died on `cp: cannot create directory ... File
# exists` and the two survivors wrote the same files concurrently, one of them
# landing a second copy inside the first's directory (engine/engine). One copier
# at a time: the copy lands beside the target and is renamed into place, and the
# check is repeated under the lock so the waiters find it done.
if [ ! -f "$MINESTUDIO_DIR/engine/build/libs/mcprec-6.13.jar" ]; then
    (
        flock 9
        if [ ! -f "$MINESTUDIO_DIR/engine/build/libs/mcprec-6.13.jar" ]; then
            rm -rf "$MINESTUDIO_DIR/engine.partial" "$MINESTUDIO_DIR/engine"
            cp -r "$MCU_PREFIX/MineStudio/engine" "$MINESTUDIO_DIR/engine.partial"
            mv -T "$MINESTUDIO_DIR/engine.partial" "$MINESTUDIO_DIR/engine"
        fi
    ) 9>"$MINESTUDIO_DIR/.engine.lock"
fi

# Minecraft and pyglet need an X display already at python *import* time, so
# wrap every entry point:
#   xvfb-run -a .venv/bin/python src/server.py --host 127.0.0.1 --port 9009
#   xvfb-run -a .venv/bin/python test_purple_agent.py --host 127.0.0.1 --port 9019
