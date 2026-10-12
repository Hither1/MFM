#!/usr/bin/env bash
#
# The sandbox the mfm arm runs codex inside, standing in for the Docker container
# PRO-LONG uses (https://github.com/alexisfox7/PRO-LONG). One unprivileged
# mount + network namespace per `codex exec`, matching upstream's threat model without a
# container, so that it also runs on a host with no docker group, where rootless podman
# can have no CNI plugins for an `--internal` network.
#
# WHAT UPSTREAM'S CONTAINER GIVES, AND WHERE EACH PIECE LIVES HERE
#
#   only the workspace is reachable      -> outer bwrap mount namespace   [this script]
#   no network except the model API      -> outer --unshare-net + an allowlisting proxy
#                                            on a unix socket              [this script +
#                                            sandbox_proxy.py]
#   the agent's own commands are confined -> codex's inner sandbox, sandbox_mode=
#                                            "workspace-write"             [_args in the
#                                            backend]
#   a minimal, declared tool surface      -> SAFE_CODEX_FLAGS + a clean CODEX_HOME
#                                            [codex_backend.SAFE_CODEX_FLAGS + below]
#
# WHY THE READ ISOLATION MATTERS. codex's own `workspace-write` bounds writes and the
# agent shell's network, but NOT reads: from inside it the agent can read any file the
# runner can, and the grader's task data (the reference netlists) sit on the same
# filesystem. So the datasets, the grader, the driver's output directory and every other
# episode's workspace are simply not mounted; they do not exist to resolve. "The agent
# did not read the answers" is an audit of one run, "the agent could not" is a property
# of the harness -- and only the second survives someone re-running this.
#
# WHY THE NETWORK NAMESPACE. The earlier version of this wrapper did NOT unshare the
# network: codex has to reach the API, so the namespace saw the host's network and the
# agent's shell was kept off it by codex's inner sandbox alone -- one layer, flipped by
# one config key. Now the outer namespace has only loopback and no DNS
# (measured), and the one route out is the allowlist proxy, which lets through the model
# API and nothing else. That is upstream's structural guarantee, restored.
#
# WHY A PER-EPISODE CODEX_HOME. `--ignore-user-config` skips config.toml only; a personal
# $CODEX_HOME still injects its AGENTS.md into every turn (+3,866 tokens measured on a
# one-word prompt) and its skills/plugins into the tool surface. And a *shared* eval home
# is worse than cosmetic: `codex exec resume` needs only the sessions/ dir, so an agent
# with a shared home mounted can read the sessions of the other tasks out of it.
# So each episode gets its own home -- `<workspace>.codexhome` by default -- holding an
# empty skills/.system (which suppresses the account's built-in skills) and nothing else;
# auth.json is bind-mounted read-only from the master, so no token is written to disk.
# Only that home is mounted, so no episode can see another's sessions.
#
# HOW IT IS WIRED. `CodexTurn`/`CodexClient` run codex with cwd == the workspace and the
# binary from $CODEX_BIN, so this reads the workspace off $PWD and is a drop-in:
#
#     CODEX_BIN=model_channel/codex_sandbox.sh       (scripts/run_kicad_arm.sh sets it)
#
# CONTROL ENV (all optional; the callers set the ones that matter):
#   CODEX_SANDBOX_WORKSPACE   the rw workspace (default $PWD)
#   CODEX_EPISODE_HOME        this episode's CODEX_HOME (default `<workspace>.codexhome`,
#                             which is per-episode already; override only to place the
#                             home somewhere other than beside its workspace)
#   CODEX_EVAL_HOME           the master home holding auth.json (default ~/.codex-eval)
#   CODEX_SANDBOX_ALLOW       proxy allowlist, comma-separated host:port
#                             (default .chatgpt.com:443,.openai.com:443,chatgpt.com:443)
#   CODEX_SANDBOX_NO_NET      set to 1 to skip --unshare-net + proxy (debugging only)
#   CODEX_SANDBOX_EXEC        what runs inside (default the real codex)
#   CODEX_SANDBOX_STATELESS   set by CodexClient: a throwaway home for a no-resume call
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WS="${CODEX_SANDBOX_WORKSPACE:-$PWD}"
EVAL_HOME="${CODEX_EVAL_HOME:-$HOME/.codex-eval}"
# Default to a home that is this workspace's alone -- a sibling `<workspace>.codexhome`,
# NOT the shared eval home. $WS is stable across the turns of one episode, so the sibling
# is too, which is exactly what `codex exec resume` needs (it reads sessions/ from here);
# and it is per-episode, so one episode's sessions are never in the home another
# episode mounts. Overridable, and
# replaced by a throwaway for the no-resume CodexClient path below.
WS="$(cd "$WS" 2>/dev/null && pwd || echo "$WS")"
EPISODE_HOME="${CODEX_EPISODE_HOME:-${WS%/}.codexhome}"

NODE_DIR="${CODEX_NODE_DIR:-$HOME/.nvm/versions/node/v22.18.0}"
REAL_CODEX="${CODEX_REAL_BIN:-$NODE_DIR/bin/codex}"
BWRAP="${BWRAP_BIN:-$(command -v bwrap || echo /usr/bin/bwrap)}"
SANDBOX_EXEC="${CODEX_SANDBOX_EXEC:-$REAL_CODEX}"
PYTHON_HOST="${CODEX_SANDBOX_PYTHON:-$(command -v python3 || echo /usr/bin/python3)}"
# The IN-NAMESPACE interpreter is a separate choice: it must exist at a path the
# sandbox binds, and sandbox_proxy.py needs >= 3.7 (asyncio.run, deferred annotations).
# On EL8 hosts /usr/bin/python3 is 3.6 and the forwarder died at import -- port 3128
# never listened, codex saw ECONNREFUSED on every request and sat in "waiting for
# network" until the runner's timeout. Default to /usr/bin/python3 where it is new
# enough (the datapool hosts), fall back to the host proxy's interpreter otherwise,
# and bind whatever prefix the choice lives under. CODEX_SANDBOX_INNER_PYTHON overrides.
SBX_PY="${CODEX_SANDBOX_INNER_PYTHON:-/usr/bin/python3}"
if ! "$SBX_PY" -c 'import sys; raise SystemExit(sys.version_info < (3, 7))' 2>/dev/null; then
    SBX_PY="$PYTHON_HOST"
fi
SBX_PY="$(readlink -f "$SBX_PY" 2>/dev/null || echo "$SBX_PY")"
SBX_PY_PREFIX="$("$SBX_PY" -c 'import sys; print(sys.prefix)' 2>/dev/null || echo /usr)"
PY_BIND=()
case "$SBX_PY_PREFIX" in
    /usr|/usr/*) : ;;                       # already bound below
    *) PY_BIND=(--ro-bind "$SBX_PY_PREFIX" "$SBX_PY_PREFIX") ;;
esac

# A local-server arm authenticates with a dummy env key and has no account credential
# at all, so it sets CODEX_SANDBOX_NO_AUTH=1 and the auth bind is skipped. Everything
# else is required: a missing one is a misconfiguration that would otherwise surface as
# an unexplained codex failure several minutes into a job. The bind args themselves are
# assembled AFTER the stateless branch below -- the target path names $EPISODE_HOME,
# and a stateless call replaces that with a throwaway after this point. Assembling here
# bound auth to the abandoned per-workspace path while codex read the throwaway: every
# hosted stateless call (the direct arm) got 401, and nothing local ever
# noticed because local arms skip the bind entirely.
if [ "${CODEX_SANDBOX_NO_AUTH:-0}" != "1" ]; then
    [ -e "$EVAL_HOME/auth.json" ] || {
        printf 'codex_sandbox: missing %s (set CODEX_SANDBOX_NO_AUTH=1 for a local-server arm)\n' \
            "$EVAL_HOME/auth.json" >&2; exit 1; }
fi
for required in "$SANDBOX_EXEC" "$BWRAP"; do
    [ -e "$required" ] || { printf 'codex_sandbox: missing %s\n' "$required" >&2; exit 1; }
done
[ -d "$WS" ] || { printf 'codex_sandbox: workspace is not a directory: %s\n' "$WS" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Per-episode CODEX_HOME. Seed it with auth and an empty system-skills dir so the
# account's built-in skills are not injected; sessions/ accumulate here and are the
# resumable conversation. A stateless call (CodexClient) gets a throwaway home instead.
# ---------------------------------------------------------------------------
CLEANUP_HOME=""
if [ "${CODEX_SANDBOX_STATELESS:-0}" = "1" ]; then
    EPISODE_HOME="$(mktemp -d "${TMPDIR:-/tmp}/codex-home-XXXXXX")"
    CLEANUP_HOME="$EPISODE_HOME"
fi
# Assembled only now, when $EPISODE_HOME is final (see the note at the top check).
AUTH_BIND=()
if [ "${CODEX_SANDBOX_NO_AUTH:-0}" != "1" ]; then
    AUTH_BIND=(--ro-bind "$EVAL_HOME/auth.json" "$EPISODE_HOME/auth.json")
fi
mkdir -p "$EPISODE_HOME/skills/.system"
# auth.json is bind-mounted read-only from the master (see BWRAP_ARGS), not copied: one
# token file on disk instead of one per episode, and an episode home that holds no secret
# and so is safe to leave or delete. codex may want to *write* auth.json on a token
# refresh; that is bound-read-only here, so refresh the master with `codex login` before a
# run that could outlive the token (checked: ~1 week validity).
# The marker with an otherwise-empty .system tells codex the system skills are "already
# installed" (empty), so it injects none of its own into the tool surface.
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

# ---------------------------------------------------------------------------
# The egress proxy, unless explicitly disabled. Started on the host, before the
# namespace, listening on a unix socket in a short-pathed dir (AF_UNIX caps the path at
# 108 bytes, so not under $WS which may be deep). --unshare-net then gives the namespace
# only loopback; a forwarder started inside bridges 127.0.0.1:3128 to the socket.
# ---------------------------------------------------------------------------
NET_ARGS=()
PROXY_SETENV=()
INNER_PREAMBLE=""
INNER_PATH_PREFIX=""
if [ "${CODEX_SANDBOX_NO_NET:-0}" != "1" ]; then
    ALLOW="${CODEX_SANDBOX_ALLOW:-.chatgpt.com:443,.openai.com:443,chatgpt.com:443}"
    # Not under /run/user/$UID. That is logind's per-session tmpfs, and on a compute
    # node -- where a batch job holds no login session -- it exists only while some
    # other session of the user's does, and is torn down when that session ends. Two
    # turns of one run failed exactly this way: the directory was
    # created here and was gone by the time the proxy tried to bind in it. /tmp is
    # short enough for AF_UNIX's 108-byte path cap and is not removed under us.
    # Starting the proxy is tried three times regardless, with a fresh directory each
    # time, because the answer to "the runtime dir vanished" is not a default.
    PROXY_PID=""
    for _try in 1 2 3; do
        SOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codexpx-XXXXXX")"
        SOCK="$SOCK_DIR/proxy.sock"
        "$PYTHON_HOST" "$HERE/sandbox_proxy.py" host "$SOCK" "$ALLOW" &
        PROXY_PID=$!
        # Wait for the socket, but do not hang forever if the proxy died.
        for _ in $(seq 1 100); do
            [ -S "$SOCK" ] && break
            kill -0 "$PROXY_PID" 2>/dev/null || break
            sleep 0.1
        done
        [ -S "$SOCK" ] && break
        echo "codex_sandbox: egress proxy did not come up in $SOCK_DIR (attempt $_try)" >&2
        kill "$PROXY_PID" 2>/dev/null || true
        rm -rf "$SOCK_DIR"
        sleep 1
    done
    [ -S "$SOCK" ] || { echo "codex_sandbox: egress proxy socket never appeared" >&2; exit 1; }
    if ! "$SBX_PY" -c 'import sys; raise SystemExit(sys.version_info < (3, 7))' 2>/dev/null; then
        echo "codex_sandbox: no python >= 3.7 for the in-namespace forwarder;" \
             "set CODEX_SANDBOX_INNER_PYTHON" >&2; exit 1
    fi
    # `python` on the sandbox PATH resolves here, ahead of sandbox_bin's system-python
    # symlink: tools with an `/usr/bin/env python` shebang (tools/zoom.py) get the same
    # interpreter as the forwarder -- one with PIL where the host provides it.
    mkdir -p "$SOCK_DIR/bin"
    ln -sfn "$SBX_PY" "$SOCK_DIR/bin/python"
    ln -sfn "$SBX_PY" "$SOCK_DIR/bin/python3"
    INNER_PATH_PREFIX="/run/codexpx/bin:"
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
    # Start the in-namespace forwarder, then exec the real target. `exec` so codex keeps
    # this shell's pid (--die-with-parent still reaps the forwarder when codex exits).
    INNER_PREAMBLE='"$SBX_PYTHON" /sandbox_proxy.py forward /run/codexpx/proxy.sock 3128 & for _ in $(seq 1 50); do (exec 3<>/dev/tcp/127.0.0.1/3128) 2>/dev/null && break; sleep 0.05; done; exec "$@"'
fi

# ---------------------------------------------------------------------------
# The toolchain, declared rather than inherited: inside the namespace the host PATH is
# gone, so what the agent can run is exactly what is mounted here. sandbox_bin supplies
# `python`, because PRO-LONG's mechanism is the agent writing scripts to parse its log
# and the namespace otherwise has only /usr/bin/python3. rg comes from codex's own
# bundle via NODE_DIR.
#
# --clearenv, then an explicit allowlist: the runner's environment carries API tokens
# (GITHUB_PERSONAL_ACCESS_TOKEN, WANDB_API_KEY, ... were present) that have no business
# in the agent's process. LOCAL_API_KEY is forwarded only when set (local-server arms).
# ---------------------------------------------------------------------------
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
    `# resolv.conf is a symlink into /run; without the target a *networked* run dies on` \
    `# DNS. Harmless under --unshare-net where there is no DNS anyway.` \
    --ro-bind-try /run/systemd/resolve /run/systemd/resolve
    --ro-bind "$NODE_DIR" "$NODE_DIR"
    --ro-bind "$HERE/sandbox_bin" "$HERE/sandbox_bin"
    "${PY_BIND[@]}"
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
    --setenv PATH "${INNER_PATH_PREFIX}$HERE/sandbox_bin:$NODE_DIR/bin:/usr/local/bin:/usr/bin:/bin"
    `# The in-namespace forwarder's interpreter: resolved above to a path that exists` \
    `# INSIDE the namespace (/usr comes in with --ro-bind; any other prefix is bound` \
    `# via PY_BIND). /usr/bin/python3 alone is 3.6 on EL8 and cannot run the forwarder.` \
    --setenv SBX_PYTHON "$SBX_PY"
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
