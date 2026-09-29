# Source this file before running anything here (scripts/run-arm.sh does):
#   source env.sh
#
# The Minecraft engine needs a JDK 8 and, headless, an X display from Xvfb. Where they
# are installed system-wide nothing is needed; on a host without root they can sit
# user-locally under $MCU_PREFIX ($MCU_PREFIX/jdk8, $MCU_PREFIX/xvfb/usr/bin) and are
# put on PATH here.
export MCU_PREFIX="${MCU_PREFIX:-$HOME/.local/opt/mcu}"
if [ -d "$MCU_PREFIX/jdk8" ]; then
    export JAVA_HOME="$MCU_PREFIX/jdk8"
    export PATH="$JAVA_HOME/bin:$PATH"
fi
[ -d "$MCU_PREFIX/xvfb/usr/bin" ] && export PATH="$MCU_PREFIX/xvfb/usr/bin:$PATH"

# The recorded runs rendered on the CPU (Xvfb + Mesa llvmpipe, about 22 frames a second
# per instance); MINESTUDIO_GPU_RENDER selects the VirtualGL/EGL path instead.
unset MINESTUDIO_GPU_RENDER

# MineStudio keeps a diskcache/sqlite instance registry and the per-instance working
# directories under MINESTUDIO_DIR. It must be on a local disk: sqlite locking fails on
# NFS ("OperationalError: cannot rollback - no transaction is active"), and the JVM
# dies at startup when its working directory returns ESTALE.
export MINESTUDIO_DIR="${MINESTUDIO_DIR:-/tmp/MineStudio-${USER:-$(id -un)}}"
mkdir -p "$MINESTUDIO_DIR"

# /tmp is volatile: the engine (445 MB) is restored from a persistent copy under
# $MCU_PREFIX/MineStudio/engine, when there is one, rather than downloaded again. One
# copier at a time -- several arms launched together all see the jar missing: the copy
# lands beside the target and is renamed into place, and the check is repeated under
# the lock so the waiters find it done.
if [ ! -f "$MINESTUDIO_DIR/engine/build/libs/mcprec-6.13.jar" ] \
        && [ -d "$MCU_PREFIX/MineStudio/engine" ]; then
    (
        flock 9
        if [ ! -f "$MINESTUDIO_DIR/engine/build/libs/mcprec-6.13.jar" ]; then
            rm -rf "$MINESTUDIO_DIR/engine.partial" "$MINESTUDIO_DIR/engine"
            cp -r "$MCU_PREFIX/MineStudio/engine" "$MINESTUDIO_DIR/engine.partial"
            mv -T "$MINESTUDIO_DIR/engine.partial" "$MINESTUDIO_DIR/engine"
        fi
    ) 9>"$MINESTUDIO_DIR/.engine.lock"
fi

# Minecraft and pyglet need an X display already at python *import* time, so wrap every
# entry point that touches the simulator:
#   xvfb-run -a .venv/bin/python src/server.py --host 127.0.0.1 --port 9009
