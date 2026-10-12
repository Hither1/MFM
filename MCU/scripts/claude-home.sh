#!/usr/bin/env bash
# Build an isolated CLAUDE_CONFIG_DIR for one experiment arm and print the exports
# for it -- the claude twin of codex-home.sh:
#
#   eval "$(scripts/claude-home.sh <arm>)"
#
# Then every `claude` call in that shell uses a config dir no other arm touches.
#
# The codex twin prevents four cross-arm contaminations; the claude analogues line up
# one for one:
#
#   1. A shared session store mixes arms. Claude keeps one transcript per session
#      under $CLAUDE_CONFIG_DIR/projects/<cwd-slug>/<uuid>.jsonl plus a shared
#      state file (.claude.json); concurrent arms writing one config dir share
#      history, statsig state and the resume namespace. One dir per arm.
#
#   2. Credentials race. `.credentials.json` carries OAuth tokens that the CLI
#      refreshes in place; a COPY per arm forks the refresh chain and the loser
#      401s, so the file is a symlink to one live credential, never a copy. The
#      cleaner option -- immune to refresh entirely -- is a long-lived token from
#      `claude setup-token`, exported as CLAUDE_CODE_OAUTH_TOKEN; when
#      MCU_CLAUDE_OAUTH_TOKEN is set this script emits that instead of linking a
#      file at all.
#
#   3. The account's personal instructions ride along. The user-level CLAUDE.md,
#      settings.json, skills/ and memories/ of whatever account the host shell is
#      logged into would otherwise sit ahead of the arm's own system prompt. A
#      fresh config dir holds none of them, and the backend passes
#      `--setting-sources project` so even a populated user layer would not load.
#
#   4. Session writes belong on a local disk, and $HOME can be network storage.
#      /var/tmp is local, survives reboots (unlike /tmp), and is where the codex
#      homes already live. Override with MCU_CLAUDE_ROOT if it is the wrong disk.
set -euo pipefail

ARM="${1:?usage: claude-home.sh <arm-name>}"
ROOT="${MCU_CLAUDE_ROOT:-/var/tmp/mcu-claude-$(id -un)}"
HOME_DIR="$ROOT/$ARM"

rm -rf "$HOME_DIR"
mkdir -p "$HOME_DIR"
# 700: /var/tmp is world-readable and the transcripts are the run's data.
chmod 700 "$ROOT" "$HOME_DIR"

# What the model must never read: this config dir (the key helper, or a subscription
# arm's .credentials.json) and, on the OpenRouter route, the secrets directory the
# helper reads. claude_backend turns the list into sandbox denyRead + Read-tool deny
# rules (measured unreadable on 2.1.257).
DENY="$HOME_DIR"
# The eval identity is a directory, ~/.claude-eval by default (the twin of
# ~/.codex-eval): the account the arms burn is deliberately separated from whatever
# account the developer's own shell is logged into. MCU_CLAUDE_EVAL_DIR names another
# account's directory; its .credentials.json is the credential the arms share.
EVAL_DIR="${MCU_CLAUDE_EVAL_DIR:-$HOME/.claude-eval}"
if [ "${MCU_CLAUDE_ACCOUNT:-}" = "openrouter" ]; then
    # OpenRouter's Anthropic-compatible endpoint, keyed from a 600 file the CLI reads
    # through settings `apiKeyHelper` -- the twin of codex's auth.command: the key is
    # never in any process environment. The helper lives in the arm's own config dir.
    KEYFILE="${MCU_OPENROUTER_ENV:?MCU_CLAUDE_ACCOUNT=openrouter needs MCU_OPENROUTER_ENV=<file with OPENROUTER_API_KEY=...>}"
    [ -r "$KEYFILE" ] || { echo "claude-home.sh: no readable key file at $KEYFILE" >&2; exit 1; }
    cat > "$HOME_DIR/keyhelper.sh" <<HELPER
#!/usr/bin/env bash
sed -n 's/^OPENROUTER_API_KEY=//p' "$KEYFILE"
HELPER
    chmod 700 "$HOME_DIR/keyhelper.sh"
    echo "export CLAUDE_API_KEY_HELPER=$HOME_DIR/keyhelper.sh"
    DENY="$DENY:$(dirname "$KEYFILE")"
elif [ -n "${MCU_CLAUDE_OAUTH_TOKEN:-}" ]; then
    echo "export CLAUDE_CODE_OAUTH_TOKEN=$MCU_CLAUDE_OAUTH_TOKEN"
else
    # The credential every arm shares, read through a symlink so refreshes stay in
    # one place. Point MCU_CLAUDE_AUTH at another file to run a different account.
    # The symlink is resolved here, not stored: a chain of links breaks the CLI's
    # rewrite-on-refresh in ways a single link does not.
    AUTH="${MCU_CLAUDE_AUTH:-$EVAL_DIR/.credentials.json}"
    if [ ! -e "$AUTH" ]; then
        echo "claude-home.sh: no live credential at $AUTH --" >&2
        echo "  log the account in once:  CLAUDE_CONFIG_DIR=$EVAL_DIR claude login," >&2
        echo "  or set MCU_CLAUDE_AUTH to the .credentials.json the arms share," >&2
        echo "  or set MCU_CLAUDE_OAUTH_TOKEN to a 'claude setup-token' token." >&2
        exit 1
    fi
    ln -s "$(readlink -f "$AUTH")" "$HOME_DIR/.credentials.json"
    DENY="$DENY:$(dirname "$(readlink -f "$AUTH")")"
fi

# MCU_CLAUDE_BIN, else an npm-prefix install when there is one; otherwise the backend
# takes `claude` from PATH. (An nvm shim on PATH can point at a non-executable
# claude.exe, and `command -v` happily hands it back.)
BIN="${MCU_CLAUDE_BIN:-$HOME/.local/share/claude-code-npm/bin/claude}"
[ -x "$BIN" ] && echo "export CLAUDE_BIN=$BIN"

echo "export CLAUDE_SANDBOX_DENY_READ=$DENY"
echo "export CLAUDE_RUNTIME_HOME=$HOME_DIR"
