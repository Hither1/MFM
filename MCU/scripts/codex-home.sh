#!/usr/bin/env bash
# Build an isolated CODEX_HOME for one experiment arm and print the exports for it.
#
#   eval "$(scripts/codex-home.sh dm2_wm)"
#
# Then every `codex` call in that shell uses a home no other arm touches.
#
# Four things this exists to prevent, all of them measured on this project:
#
#   1. A shared thread store gets corrupted. Six arms ran against one
#      `~/.codex/runtime-home/thread_history_1.sqlite` until it failed
#      `PRAGMA integrity_check` with "database disk image is malformed". That broke
#      `codex exec resume` host-wide, which forced every arm onto
#      CODEX_SESSION_MAX_TURNS=1 -- no conversation memory at all -- for the whole
#      campaign. The wrapper auto-repairs four other databases and not this one.
#
#   2. Copied credentials race. Each copy of an OAuth auth.json carries the same
#      single-use refresh token, so the second arm to refresh gets "your refresh token
#      was already used" and every later turn 401s. auth.json is therefore a symlink
#      to one live credential, never a copy.
#
#   3. The account's personal instructions ride along. The `codex` wrapper symlinks
#      ~/.codex/{AGENTS.md,lessons.md,RTK.md} into whatever home it is given, and
#      codex prepends them to every turn -- 24,756 bytes here, ahead of the agent's own
#      19.6 KB system prompt. `--ignore-user-config` does not cover them. Empty real
#      files defeat the symlink step, which skips a target that already exists.
#
#   4. Codex refuses to create its PATH-alias helper binaries under /tmp
#      ("Refusing to create helper binaries under temporary dir"). /var/tmp is the same
#      ext4 partition, is not wiped at boot the way /tmp is, and does not trigger it.
#
# Override the location with MCU_CODEX_ROOT if /var/tmp is not the right disk. It must
# be local: $HOME here is LeoFS, and sqlite locking fails on it.
set -euo pipefail

ARM="${1:?usage: codex-home.sh <arm-name>}"
ROOT="${MCU_CODEX_ROOT:-/var/tmp/mcu-codex-$(id -un)}"
HOME_DIR="$ROOT/$ARM"
SQLITE_DIR="$HOME_DIR/sqlite"

# The credential every arm shares, read through a symlink so refreshes stay in one
# place. Two live on this host: ~/ccr/.codex/auth.json, an OpenAI API key (the
# account behind ~/ccr/bin/codex, pay-per-token, no model catalog -- codex logs
# "Model metadata for <model> not found. Defaulting to fallback metadata" once per
# turn, harmless on 1-turn sessions), and ~/.codex/runtime-home/auth.json, the
# ChatGPT plan login. The API key is the default since 2026-09-06 (the user's call:
# every later batch runs on it); it answered gpt-6-astra at effort high with a frame
# attached when probed through both wrappers. Point MCU_CODEX_AUTH at another file
# to run a different account; MCU_CODEX_AUTH=none for a provider codex authenticates
# against by running a command (CODEX_LOCAL_AUTH_COMMAND, the OpenRouter route): no
# auth.json at all in the home.
AUTH="${MCU_CODEX_AUTH:-$HOME/ccr/.codex/auth.json}"
if [ "$AUTH" != none ] && [ ! -e "$AUTH" ]; then
    echo "codex-home.sh: no credential at $AUTH -- set MCU_CODEX_AUTH to the auth.json" >&2
    echo "  the arms should share (e.g. \$HOME/.codex/runtime-home/auth.json after 'codex login')." >&2
    exit 1
fi

rm -rf "$HOME_DIR"
mkdir -p "$SQLITE_DIR"
# 700: /var/tmp is world-readable and this host has a dozen accounts on it. The
# credential is a symlink to a 600 file so it was never exposed, but the thread store
# holds the full conversation, which is the run's data.
chmod 700 "$HOME_DIR" "$SQLITE_DIR"

[ "$AUTH" = none ] || ln -s "$AUTH" "$HOME_DIR/auth.json"
for f in AGENTS.md lessons.md RTK.md config.toml; do : > "$HOME_DIR/$f"; done
for d in agents rules skills skills.disabled memories plugins; do mkdir -p "$HOME_DIR/$d"; done

echo "export CODEX_RUNTIME_HOME=$HOME_DIR"
echo "export CODEX_SQLITE_DIR=$SQLITE_DIR"
