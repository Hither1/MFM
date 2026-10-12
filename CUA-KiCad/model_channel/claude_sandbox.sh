#!/usr/bin/env bash
#
# The sandbox the mfm arm runs Claude Code inside: codex_sandbox.sh's design for `claude -p`.
# One unprivileged mount + network namespace per call.
#
#   only the workspace is reachable      -> bwrap mounts the workspace and this episode's
#                                            CLAUDE_CONFIG_DIR read-write, the system and
#                                            the claude binary read-only, nothing else
#   no network except the model API      -> --unshare-net + sandbox_proxy.py, allowlisting
#                                            Anthropic's hosts (CLAUDE_SANDBOX_ALLOW)
#   a declared tool surface              -> the backend's --tools allowlist, checked
#                                            against the init event
#
# Why it exists: Claude Code's native sandbox bounds writes and the network of the model's
# commands, but not reads -- and on KiCad the reference netlists live on the same
# filesystem as the run. Unmounted, they do not exist to resolve. The native sandbox is
# turned off under this wrapper by the backend (bwrap does not nest here).
#
# Wiring: ClaudeTurn runs `$CLAUDE_BIN -p ...` with cwd == the workspace and
# CLAUDE_CONFIG_DIR set, so with CLAUDE_BIN pointing here this is a drop-in.
#
# CONTROL ENV
#   CLAUDE_REAL_BIN           the real claude binary (default: `claude` on PATH, resolved)
#   CLAUDE_CONFIG_DIR         this episode's config dir (default <workspace>.claudehome)
#   CLAUDE_CODE_OAUTH_TOKEN   a `claude setup-token` token (preferred: never refreshes)
#   CLAUDE_EVAL_AUTH          else a .credentials.json bound read-only (default
#                             ~/.claude-eval/.credentials.json)
#   CLAUDE_SANDBOX_NO_AUTH    1: bind no credential (an API-key helper)
#   CLAUDE_SANDBOX_ALLOW      proxy allowlist (default .anthropic.com:443,claude.ai:443)
#   CLAUDE_SANDBOX_NO_NET     1: skip --unshare-net + proxy (debugging only)
#   CLAUDE_SANDBOX_EXEC       what runs inside (default the real claude)
#   CLAUDE_SANDBOX_INNER_PYTHON  interpreter for the in-namespace forwarder (>= 3.7)
#   CLAUDE_SANDBOX_RW_BINDS    colon-separated host directories bound read-write at their
#                             own paths
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(cd "${CLAUDE_SANDBOX_WORKSPACE:-$PWD}" && pwd)"
HOME_DIR="${CLAUDE_CONFIG_DIR:-${WS%/}.claudehome}"
mkdir -p "$HOME_DIR" && chmod 700 "$HOME_DIR"
HOME_DIR="$(cd "$HOME_DIR" && pwd)"

REAL="${CLAUDE_REAL_BIN:-$(command -v claude || true)}"
[ -n "$REAL" ] || { echo "claude_sandbox: no claude binary (set CLAUDE_REAL_BIN)" >&2; exit 1; }
REAL="$(readlink -f "$REAL")"
[ -x "$REAL" ] || { echo "claude_sandbox: not executable: $REAL" >&2; exit 1; }
CLAUDE_DIR="$(dirname "$REAL")"
SANDBOX_EXEC="${CLAUDE_SANDBOX_EXEC:-$REAL}"
BWRAP="${BWRAP_BIN:-$(command -v bwrap || echo /usr/bin/bwrap)}"
[ -x "$BWRAP" ] || { echo "claude_sandbox: missing bwrap" >&2; exit 1; }
PYTHON_HOST="${CLAUDE_SANDBOX_PYTHON:-$(command -v python3 || echo /usr/bin/python3)}"
SBX_PY="${CLAUDE_SANDBOX_INNER_PYTHON:-${CODEX_SANDBOX_INNER_PYTHON:-/usr/bin/python3}}"
if ! "$SBX_PY" -c 'import sys; raise SystemExit(sys.version_info < (3, 7))' 2>/dev/null; then
    SBX_PY="$PYTHON_HOST"
fi
SBX_PY="$(readlink -f "$SBX_PY" 2>/dev/null || echo "$SBX_PY")"
SBX_PY_PREFIX="$("$SBX_PY" -c 'import sys; print(sys.prefix)' 2>/dev/null || echo /usr)"
PY_BIND=()
case "$SBX_PY_PREFIX" in /usr|/usr/*) : ;; *) PY_BIND=(--ro-bind "$SBX_PY_PREFIX" "$SBX_PY_PREFIX") ;; esac

# ---- the credential -----------------------------------------------------------------
AUTH_ARGS=()
if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
    AUTH_ARGS=(--setenv CLAUDE_CODE_OAUTH_TOKEN "$CLAUDE_CODE_OAUTH_TOKEN")
elif [ "${CLAUDE_SANDBOX_NO_AUTH:-0}" != "1" ]; then
    AUTH="${CLAUDE_EVAL_AUTH:-$HOME/.claude-eval/.credentials.json}"
    [ -r "$AUTH" ] || {
        echo "claude_sandbox: no credential. Either export CLAUDE_CODE_OAUTH_TOKEN from" >&2
        echo "  \`claude setup-token\` (recommended for long runs), or point CLAUDE_EVAL_AUTH at a" >&2
        echo "  logged-in .credentials.json (bound read-only; it cannot refresh in here)." >&2
        exit 1; }
    # bwrap cannot mount over a dangling symlink an unwrapped call may have left.
    [ -L "$HOME_DIR/.credentials.json" ] && rm -f "$HOME_DIR/.credentials.json"
    AUTH_ARGS=(--ro-bind "$(readlink -f "$AUTH")" "$HOME_DIR/.credentials.json")
fi

# The model's Bash tool starts a login shell. This host's /etc/profile.d (lmod) points
# into /n/sw, which is not mounted, and fails the shell before the command runs; the
# uid has no passwd entry in here either. Both get a minimal stand-in.
RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/claudesb-XXXXXX")"
mkdir -p "$RUN_DIR/profile.d"
: > "$RUN_DIR/empty"
printf 'agent:x:%s:%s:agent:%s:/bin/bash\n' "$(id -u)" "$(id -g)" "$HOME_DIR" > "$RUN_DIR/passwd"
printf 'agent:x:%s:\n' "$(id -g)" > "$RUN_DIR/group"

cleanup() { [ -n "${SOCK_DIR:-}" ] && rm -rf "$SOCK_DIR"; rm -rf "$RUN_DIR"; return 0; }
trap cleanup EXIT INT TERM

# ---- the egress proxy ---------------------------------------------------------------
NET_ARGS=(); PROXY_SETENV=(); INNER_PREAMBLE=""; INNER_PATH_PREFIX=""
if [ "${CLAUDE_SANDBOX_NO_NET:-0}" != "1" ]; then
    ALLOW="${CLAUDE_SANDBOX_ALLOW:-.anthropic.com:443,claude.ai:443}"
    for _try in 1 2 3; do
        SOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/claudepx-XXXXXX")"
        SOCK="$SOCK_DIR/proxy.sock"
        "$PYTHON_HOST" "$HERE/sandbox_proxy.py" host "$SOCK" "$ALLOW" &
        PROXY_PID=$!
        for _ in $(seq 1 100); do
            [ -S "$SOCK" ] && break
            kill -0 "$PROXY_PID" 2>/dev/null || break
            sleep 0.1
        done
        [ -S "$SOCK" ] && break
        echo "claude_sandbox: egress proxy did not come up (attempt $_try)" >&2
        kill "$PROXY_PID" 2>/dev/null || true; rm -rf "$SOCK_DIR"; sleep 1
    done
    [ -S "$SOCK" ] || { echo "claude_sandbox: egress proxy socket never appeared" >&2; exit 1; }
    mkdir -p "$SOCK_DIR/bin"
    ln -sfn "$SBX_PY" "$SOCK_DIR/bin/python"; ln -sfn "$SBX_PY" "$SOCK_DIR/bin/python3"
    INNER_PATH_PREFIX="/run/claudepx/bin:"
    NET_ARGS=(--unshare-net --bind "$SOCK_DIR" /run/claudepx --ro-bind "$HERE/sandbox_proxy.py" /sandbox_proxy.py)
    PROXY_SETENV=(--setenv HTTPS_PROXY "http://127.0.0.1:3128" --setenv HTTP_PROXY "http://127.0.0.1:3128"
                  --setenv https_proxy "http://127.0.0.1:3128" --setenv http_proxy "http://127.0.0.1:3128")
    INNER_PREAMBLE='"$SBX_PYTHON" /sandbox_proxy.py forward /run/claudepx/proxy.sock 3128 & for _ in $(seq 1 50); do (exec 3<>/dev/tcp/127.0.0.1/3128) 2>/dev/null && break; sleep 0.05; done; exec "$@"'
fi

# ---- the harness's own knobs pass through; everything else is cleared ---------------
PASS=()
while IFS= read -r name; do
    case "$name" in
        CLAUDE_CODE_DISABLE_*|DISABLE_AUTOUPDATER|MFM_IMAGE_TOOL|ANTHROPIC_BASE_URL)
            PASS+=(--setenv "$name" "${!name}") ;;
    esac
done < <(compgen -e)

# Directories the harness needs inside at their own paths (after --tmpfs /tmp, so a
# socket directory under /tmp is reachable): CLAUDE_SANDBOX_RW_BINDS=dir1:dir2.
EXTRA_BINDS=()
IFS=: read -r -a _rw <<< "${CLAUDE_SANDBOX_RW_BINDS:-}"
for _d in "${_rw[@]}"; do [ -n "$_d" ] && [ -d "$_d" ] && EXTRA_BINDS+=(--bind "$_d" "$_d"); done

# The shell rc files are blanked only where the host has them: /etc is read-only inside,
# so bwrap cannot create a mountpoint for one that does not exist (Ubuntu has no
# /etc/bashrc; "Can't create file at /etc/bashrc: Read-only file system").
RC_BINDS=()
for _rc in /etc/bashrc /etc/bash.bashrc /etc/zshrc /etc/zshenv /etc/zprofile; do
    [ -e "$_rc" ] && RC_BINDS+=(--ro-bind "$RUN_DIR/empty" "$_rc")
done

BWRAP_ARGS=(
    --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /sbin /sbin
    --ro-bind-try /lib /lib --ro-bind-try /lib64 /lib64 --ro-bind /etc /etc
    --ro-bind "$RUN_DIR/profile.d" /etc/profile.d
    --ro-bind "$RUN_DIR/passwd" /etc/passwd --ro-bind "$RUN_DIR/group" /etc/group
    "${RC_BINDS[@]}"
    --tmpfs /tmp
    --ro-bind-try /run/systemd/resolve /run/systemd/resolve
    --ro-bind "$CLAUDE_DIR" "$CLAUDE_DIR"
    --ro-bind "$HERE/sandbox_bin" "$HERE/sandbox_bin"
    "${PY_BIND[@]}"
    --proc /proc --dev /dev
    --bind "$HOME_DIR" "$HOME_DIR"
    --bind "$WS" "$WS"
    "${EXTRA_BINDS[@]}"
    "${NET_ARGS[@]}"
    --clearenv
    --setenv HOME "$HOME_DIR"
    --setenv SHELL /bin/bash --setenv USER agent
    --setenv CLAUDE_CONFIG_DIR "$HOME_DIR"
    --setenv PATH "${INNER_PATH_PREFIX}$HERE/sandbox_bin:$CLAUDE_DIR:/usr/local/bin:/usr/bin:/bin"
    --setenv SBX_PYTHON "$SBX_PY"
    --setenv TERM "${TERM:-xterm}" --setenv LANG "${LANG:-C.UTF-8}"
    "${PASS[@]}"
    "${PROXY_SETENV[@]}"
    # After --clearenv, which bwrap applies where it stands in argv: a --setenv placed
    # before it is wiped, and the CLI then runs "Not logged in".
    "${AUTH_ARGS[@]}"
    --chdir "$WS"
    --die-with-parent --unshare-pid
)

set +e
if [ -n "$INNER_PREAMBLE" ]; then
    "$BWRAP" "${BWRAP_ARGS[@]}" -- /bin/bash -c "$INNER_PREAMBLE" -- "$SANDBOX_EXEC" "$@"
else
    "$BWRAP" "${BWRAP_ARGS[@]}" -- "$SANDBOX_EXEC" "$@"
fi
rc=$?
set -e
exit $rc
