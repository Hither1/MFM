#!/usr/bin/env bash
# claude for the OpenRouter route: the twin of codex-openrouter.sh. MCU_OPENROUTER_PROXY
# names an HTTPS proxy where the host's own egress is refused, set here for the claude
# process alone. MCU_CLAUDE_SANDBOX_TOOLS is a directory put first on PATH: the CLI's
# sandbox needs bubblewrap and socat on Linux, and refuses to run Bash without them.
# The key is not this script's business: the CLI runs the helper named in settings
# (claude-home.sh writes it), so it is never in any environment. MCU_CLAUDE_REAL is the
# binary (default: `claude` on PATH).
set -euo pipefail
PROXY="${MCU_OPENROUTER_PROXY-}"
if [ -n "$PROXY" ]; then export HTTPS_PROXY="$PROXY" https_proxy="$PROXY"; fi
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}" no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}"
if [ -n "${MCU_CLAUDE_SANDBOX_TOOLS:-}" ]; then export PATH="$MCU_CLAUDE_SANDBOX_TOOLS:$PATH"; fi
exec "${MCU_CLAUDE_REAL:-claude}" "$@"
