#!/usr/bin/env bash
# claude for the OpenRouter route: the same binary, reached through the host's proxy
# (OpenRouter serves Anthropic models from a US exit; this host's own egress is refused,
# see codex-openrouter.sh). Set here, for the claude process alone. The sandbox tools
# the CLI needs on Linux (bubblewrap, socat) are put on PATH from a conda prefix that
# carries socat, which the system lacks (2.1.257 refuses to run Bash without it once
# failIfUnavailable is set). The key is not this script's business: the CLI runs the
# helper named in settings (claude-home.sh writes it), so it is never in any environment.
set -euo pipefail
PROXY="${MCU_OPENROUTER_PROXY-http://192.168.1.64:7890}"
if [ -n "$PROXY" ]; then export HTTPS_PROXY="$PROXY" https_proxy="$PROXY"; fi
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}" no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}"
TOOLS="${MCU_CLAUDE_SANDBOX_TOOLS:-/datapool/data3/storage/ruihan/data_share/jh/Collab/tools/cc-sandbox-env/bin}"
export PATH="$TOOLS:/datapool/data2/home/ruihan/anaconda3/bin:$PATH"
exec "${MCU_CLAUDE_REAL:-/datapool/data2/home/ruihan/.nvm/versions/node/v22.18.0/bin/claude}" "$@"
