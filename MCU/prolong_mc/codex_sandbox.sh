#!/usr/bin/env bash
#
# The sandbox the codex-driven arms run inside, ported from the sibling mllm-search port
# (prolong_search/codex_sandbox.sh) and standing in for the Docker container upstream
# PRO-LONG uses. One unprivileged mount + network namespace per `codex exec`.
#
# WHY THIS EXISTS HERE, WHEN THE ORIGINAL DECISION WAS "NO CONTAINERS"
#
# That decision (task findings #12-14) was right about the mechanism and wrong about the
# coverage: codex's own `sandbox_mode="workspace-write"` bounds writes and the agent
# shell's network, and it is bubblewrap under the hood -- but it does NOT bound reads.
# From inside it the agent can read anything this user can, and on this benchmark that
# includes the answers:
#
#   benchmark/<scene>/multi-agent/metadata.json   every milestone is
#                                                 `position_near_with_facing` against a
#                                                 spawn-relative target coordinate and a
#                                                 radius. Reading it *is* the solution to
#                                                 a navigation task.
#   benchmark_gen/milestone_checker.py            how the score is computed.
#   artifacts/runs/*/result.json                  other arms' answers.
#
# No transcript so far shows an agent going after any of them. That is an audit of the
# runs we happened to look at; "it could not" is a property of the harness, and only the
# second survives someone re-running this.
#
# AND THE PART NO FILESYSTEM SANDBOX COVERS. codex hands the model whatever the
# authenticated account carries, before any sandbox applies, because those tools run
# server-side: `web_search` (default "cached") and ~250 account connectors were both in
# the tool list, measured on the sibling port with the same account. A web search against
# a published benchmark, or a connector that can fetch a repo, reaches those coordinates
# without touching this filesystem at all. That is closed by `SAFE_CODEX_FLAGS` in
# prolong_mc/codex_backend.py, not here -- this file gives it a place to stand.
#
# WHAT THIS DOES NOT CHANGE: THE MINECRAFT SERVER. `MC_SANDBOX_URL` is the runner's, not
# the agent's -- the runner steps the world, the agent only ever writes actions.json.
# Upstream draws the same line ("the container never talks to the game server (the
# host-side runner does)"). So the server is deliberately NOT on the egress allowlist:
# the namespace has one route out, to the model API, and an agent that tried to drive the
# world directly would fail at connect. A local *model* server (`--codex-base-url`, the
# vLLM arm) is different and must be added:
#
#     CODEX_SANDBOX_ALLOW=".chatgpt.com:443,.openai.com:443,gh142:30000"
#
# ON DELTAAI (aarch64). bwrap need not be installed: codex ships its own, and it works as
# the outer wrapper too. Point BWRAP_BIN at it --
#     $NODE_DIR/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-arm64/\
#       vendor/aarch64-unknown-linux-musl/codex-resources/bwrap
#
# HOW IT IS WIRED. `CodexTurn` and `CodexProvider` both run codex with cwd set to the
# directory codex should work in and take the binary from $CODEX_BIN, so this reads the
# workspace off $PWD and is a drop-in:
#
#     export CODEX_BIN="$PWD/prolong_mc/codex_sandbox.sh"
#     export CODEX_EVAL_HOME="$HOME/.codex-eval"     # master auth.json, bound read-only
#
# CONTROL ENV: CODEX_SANDBOX_WORKSPACE, CODEX_EPISODE_HOME, CODEX_EVAL_HOME,
# CODEX_SANDBOX_ALLOW, CODEX_SANDBOX_NO_NET=1 (debug), CODEX_SANDBOX_EXEC (tests),
# CODEX_SANDBOX_STATELESS=1 (a throwaway home, for the no-resume provider path).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WS="${CODEX_SANDBOX_WORKSPACE:-$PWD}"
WS="$(cd "$WS" 2>/dev/null && pwd || echo "$WS")"
EVAL_HOME="${CODEX_EVAL_HOME:-$HOME/.codex-eval}"
# Per episode by default: a shared CODEX_HOME holds every episode's resumable session,
# and `codex exec resume` needs only sessions/ -- so an agent that can read its own $HOME
# can read another episode's conversation. $WS is stable across one episode's turns and
# distinct between episodes, which is exactly the lifetime this needs.
EPISODE_HOME="${CODEX_EPISODE_HOME:-${WS%/}.codexhome}"

NODE_DIR="${CODEX_NODE_DIR:-$HOME/.nvm/versions/node/v22.18.0}"
REAL_CODEX="${CODEX_REAL_BIN:-$NODE_DIR/bin/codex}"
BWRAP="${BWRAP_BIN:-$(command -v bwrap || echo /usr/bin/bwrap)}"
SANDBOX_EXEC="${CODEX_SANDBOX_EXEC:-$REAL_CODEX}"
PYTHON_HOST="${CODEX_SANDBOX_PYTHON:-$(command -v python3 || echo /usr/bin/python3)}"

# A local-server arm authenticates with a dummy env key and has no account credential
# at all, so it sets CODEX_SANDBOX_NO_AUTH=1 and the auth bind is skipped. Everything
# else is required: a missing one is a misconfiguration that would otherwise surface as
# an unexplained codex failure several minutes into a job.
AUTH_BIND=()
if [ "${CODEX_SANDBOX_NO_AUTH:-0}" != "1" ]; then
    [ -e "$EVAL_HOME/auth.json" ] || {
        printf 'codex_sandbox: missing %s (set CODEX_SANDBOX_NO_AUTH=1 for a local-server arm)\n' \
            "$EVAL_HOME/auth.json" >&2; exit 1; }
    AUTH_BIND=(--ro-bind "$EVAL_HOME/auth.json" "$EPISODE_HOME/auth.json")
fi
for required in "$SANDBOX_EXEC" "$BWRAP"; do
    [ -e "$required" ] || { printf 'codex_sandbox: missing %s\n' "$required" >&2; exit 1; }
done
[ -d "$WS" ] || { printf 'codex_sandbox: workspace is not a directory: %s\n' "$WS" >&2; exit 1; }

CLEANUP_HOME=""
if [ "${CODEX_SANDBOX_STATELESS:-0}" = "1" ]; then
    EPISODE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/codex-home-XXXXXX")"
    CLEANUP_HOME="$EPISODE_HOME"
fi
mkdir -p "$EPISODE_HOME/skills/.system"
# The marker with an otherwise-empty .system tells codex its built-in skills are already
# installed (as nothing), so none are injected into the prompt. auth.json is bind-mounted
# read-only from the master rather than copied: one token file on disk, and an episode
# home that holds no secret.
: > "$EPISODE_HOME/skills/.system/.codex-system-skills.marker"
# Cleanup runs on the way out, which is why the bwrap below is NOT `exec`ed: an exec
# replaces this shell and the trap never fires. That leaked a socket directory per turn
# and -- worse -- a throwaway CODEX_HOME per stateless call, each holding a bound-in
# credential path. TERM/INT are trapped too: a runner that times out kills this process,
# and the default disposition would skip the EXIT trap entirely.
cleanup() {
    [ -n "${CLEANUP_HOME:-}" ] && rm -rf "$CLEANUP_HOME"
    [ -n "${SOCK_DIR:-}" ] && rm -rf "$SOCK_DIR"
    return 0
}
trap cleanup EXIT INT TERM

NET_ARGS=()
PROXY_SETENV=()
INNER_PREAMBLE=""
if [ "${CODEX_SANDBOX_NO_NET:-0}" != "1" ]; then
    ALLOW="${CODEX_SANDBOX_ALLOW:-.chatgpt.com:443,.openai.com:443,chatgpt.com:443}"
    SOCK_DIR="$(mktemp -d "/run/user/$(id -u)/codexpx-XXXXXX" 2>/dev/null \
                || mktemp -d "${TMPDIR:-/tmp}/codexpx-XXXXXX")"
    SOCK="$SOCK_DIR/proxy.sock"
    "$PYTHON_HOST" "$HERE/sandbox_proxy.py" host "$SOCK" "$ALLOW" &
    PROXY_PID=$!
    for _ in $(seq 1 50); do
        [ -S "$SOCK" ] && break
        kill -0 "$PROXY_PID" 2>/dev/null || { echo "codex_sandbox: egress proxy failed to start" >&2; exit 1; }
        sleep 0.1
    done
    [ -S "$SOCK" ] || { echo "codex_sandbox: egress proxy socket never appeared" >&2; exit 1; }
    NET_ARGS=(--unshare-net --bind "$SOCK_DIR" /run/codexpx --ro-bind "$HERE/sandbox_proxy.py" /sandbox_proxy.py)
    # No NO_PROXY exception, deliberately. Upstream's container sets one because it has
    # nothing local to reach; here a local *model* server is a supported arm
    # (--codex-base-url), and inside this namespace `localhost` is the namespace's own
    # loopback, where that server does not exist. Routing it through the proxy instead
    # means the host resolves it -- and the allowlist still decides, so a local server has
    # to be named in CODEX_SANDBOX_ALLOW like any other destination. The forwarder itself
    # is reached as the proxy, so it needs no exception.
    PROXY_SETENV=(--setenv HTTPS_PROXY "http://127.0.0.1:3128" \
                  --setenv HTTP_PROXY "http://127.0.0.1:3128" \
                  --setenv ALL_PROXY "http://127.0.0.1:3128")
    INNER_PREAMBLE='"$SBX_PYTHON" /sandbox_proxy.py forward /run/codexpx/proxy.sock 3128 & for _ in $(seq 1 50); do (exec 3<>/dev/tcp/127.0.0.1/3128) 2>/dev/null && break; sleep 0.05; done; exec "$@"'
fi

# --clearenv, then an explicit allowlist: the runner's environment carries AGENT_API_KEY,
# HF tokens and whatever else the launcher exported, and none of it belongs in the agent's
# process. LOCAL_API_KEY is forwarded only when set (the local-server arm needs it).
LOCAL_KEY_SETENV=()
[ -n "${LOCAL_API_KEY:-}" ] && LOCAL_KEY_SETENV=(--setenv LOCAL_API_KEY "$LOCAL_API_KEY")

BWRAP_ARGS=(
    --ro-bind /usr /usr
    --ro-bind /bin /bin
    --ro-bind /sbin /sbin
    --ro-bind-try /lib /lib
    --ro-bind-try /lib64 /lib64
    --ro-bind /etc /etc
    `# The private /tmp goes FIRST: bwrap applies mounts in order, so a tmpfs laid over` \
    `# /tmp later would hide anything already bound beneath it -- the workspace, but also` \
    `# sandbox_bin and the proxy script when the repo itself lives under /tmp (a worktree,` \
    `# a scratch checkout). Everything below lands on top of it instead.` \
    --tmpfs /tmp
    --ro-bind-try /run/systemd/resolve /run/systemd/resolve
    --ro-bind "$NODE_DIR" "$NODE_DIR"
    --ro-bind "$HERE/sandbox_bin" "$HERE/sandbox_bin"
    --proc /proc
    --dev /dev
    --bind "$EPISODE_HOME" "$EPISODE_HOME"
    `# auth read-only, on top of the rw home: the token is a single master file, and the` \
    `# episode home on disk never contains it. Empty for a local-server arm.` \
    "${AUTH_BIND[@]}"
    --bind "$WS" "$WS"
    "${NET_ARGS[@]}"
    --clearenv
    --setenv HOME "$EPISODE_HOME"
    --setenv CODEX_HOME "$EPISODE_HOME"
    --setenv PATH "$HERE/sandbox_bin:$NODE_DIR/bin:/usr/local/bin:/usr/bin:/bin"
    `# The forwarder's interpreter must exist INSIDE: a conda python3 on the host lives` \
    `# under an unmounted prefix. /usr/bin/python3 arrives with --ro-bind /usr.` \
    --setenv SBX_PYTHON "/usr/bin/python3"
    --setenv TERM "${TERM:-xterm}"
    --setenv LANG "${LANG:-C.UTF-8}"
    "${LOCAL_KEY_SETENV[@]}"
    "${PROXY_SETENV[@]}"
    --chdir "$WS"
    --die-with-parent
    --unshare-pid
)

# Foreground, not exec (see cleanup above), and not backgrounded either: a `&` in a
# non-interactive shell redirects stdin from /dev/null, and stdin is how every caller
# passes the turn's prompt. `--die-with-parent` still ties bwrap's life to this shell.
set +e
if [ -n "$INNER_PREAMBLE" ]; then
    "$BWRAP" "${BWRAP_ARGS[@]}" -- /bin/bash -c "$INNER_PREAMBLE" -- "$SANDBOX_EXEC" "$@"
else
    "$BWRAP" "${BWRAP_ARGS[@]}" -- "$SANDBOX_EXEC" "$@"
fi
rc=$?
set -e
exit $rc
