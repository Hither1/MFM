#!/usr/bin/env bash
# Prepare MINESTUDIO_DIR for a job, and echo it.
#
# The engine jar is 466 MB and lives on netscratch so it survives between jobs. But
# `InstanceManager` derives *everything* from MINESTUDIO_DIR -- including the per-instance
# working directory it copies a runtime into and then launches Minecraft with as its cwd --
# and that directory must not be on NFS. Java initialises its default FileSystem by
# stat-ing the working directory, and on netscratch that intermittently returns ESTALE, so
# the JVM dies before Minecraft starts with:
#
#     NoClassDefFoundError: Could not initialize class
#       java.nio.file.FileSystems$DefaultFileSystemHolder
#     Caused by: sun.nio.fs.UnixException: No such file or directory
#
# which names neither NFS nor the working directory and reads like a broken JRE.
#
# So: a node-local MINESTUDIO_DIR, with only `engine` symlinked back to the shared copy.
# Instance dirs, the runtime and crash reports all land on local disk; the 466 MB jar is
# not copied per job.
set -euo pipefail
SHARED=${MINESTUDIO_SHARED:-/n/netscratch/sham_lab/Lab/$USER/MineStudio}
LOCAL=${TMPDIR:-/tmp}/minestudio-${SLURM_JOB_ID:-$$}
mkdir -p "$LOCAL"
[ -e "$LOCAL/engine" ] || ln -s "$SHARED/engine" "$LOCAL/engine"
mkdir -p "$LOCAL/runtime" "$LOCAL/tmp"
echo "$LOCAL"
