#!/usr/bin/env bash
# Build an isolated CODEX_HOME for one experiment arm and print the exports for it.
#
#   eval "$(scripts/codex-home.sh <arm>)"
#
# Then every `codex` call in that shell uses a home no other arm touches. This
# prevents four failures, all of them measured:
#
#   1. A shared thread store gets corrupted. Six arms that ran against one
#      `thread_history_1.sqlite` broke it ("database disk image is malformed"), and
#      with it `codex exec resume` for every arm on the host.
#
#   2. Copied credentials race. Each copy of an OAuth auth.json carries the same
#      single-use refresh token, so the second arm to refresh gets "your refresh token
#      was already used" and every later turn 401s. auth.json is therefore a symlink
#      to one live credential, never a copy.
#
#   3. The account's personal instructions ride along. A `codex` wrapper can link
#      the user's own instruction files (AGENTS.md and the others emptied below) into
#      whatever home it is given, and codex prepends them to every turn, ahead of the
#      agent's own system prompt. `--ignore-user-config` does not cover them. Empty
#      real files defeat the link step, which skips a target that already exists.
#
#   4. Codex refuses to create its PATH-alias helper binaries under /tmp
#      ("Refusing to create helper binaries under temporary dir"). /var/tmp is not
#      wiped at boot the way /tmp is, and does not trigger it.
#
# Override the location with MCU_CODEX_ROOT if /var/tmp is not the right disk. It must
# be a local disk: sqlite locking fails on a network filesystem.
set -euo pipefail

ARM="${1:?usage: codex-home.sh <arm-name>}"
ROOT="${MCU_CODEX_ROOT:-/var/tmp/mcu-codex-$(id -un)}"
HOME_DIR="$ROOT/$ARM"
SQLITE_DIR="$HOME_DIR/sqlite"

# The credential every arm shares, read through a symlink so refreshes stay in one
# place: the auth.json `codex login` wrote (default ~/.codex/auth.json). Point
# MCU_CODEX_AUTH at another file to run a different account; MCU_CODEX_AUTH=none for a
# provider codex authenticates against by running a command (CODEX_LOCAL_AUTH_COMMAND,
# the OpenRouter route): no auth.json at all in the home.
AUTH="${MCU_CODEX_AUTH:-$HOME/.codex/auth.json}"
if [ "$AUTH" != none ] && [ ! -e "$AUTH" ]; then
    echo "codex-home.sh: no credential at $AUTH -- set MCU_CODEX_AUTH to the auth.json" >&2
    echo "  the arms should share (written by 'codex login')." >&2
    exit 1
fi

rm -rf "$HOME_DIR"
mkdir -p "$SQLITE_DIR"
# 700: /var/tmp is world-readable. The
# credential is a symlink to a 600 file so it was never exposed, but the thread store
# holds the full conversation, which is the run's data.
chmod 700 "$HOME_DIR" "$SQLITE_DIR"

[ "$AUTH" = none ] || ln -s "$AUTH" "$HOME_DIR/auth.json"
for f in AGENTS.md lessons.md RTK.md config.toml; do : > "$HOME_DIR/$f"; done
for d in agents rules skills skills.disabled memories plugins; do mkdir -p "$HOME_DIR/$d"; done

echo "export CODEX_RUNTIME_HOME=$HOME_DIR"
echo "export CODEX_SQLITE_DIR=$SQLITE_DIR"
