#!/usr/bin/env bash
# The API-key codex (~/ccr/bin/codex, its own credential and runtime home) reached through the
# host's egress proxy -- the shell alias `withproxy` (192.168.1.64:7890) applied to the codex
# process alone. Added 2026-09-20 when the host's direct route to api.openai.com died mid-wave
# (DNS "Try again" / connection reset on every turn from ~09:37; six arms stalled at 480 s
# timeouts). The arm's other hops (green <-> purple on 127.0.0.1) never see the proxy.
set -euo pipefail
PROXY="${MCU_CODEX_PROXY-http://192.168.1.64:7890}"
if [ -n "$PROXY" ]; then export HTTPS_PROXY="$PROXY" https_proxy="$PROXY" HTTP_PROXY="$PROXY" http_proxy="$PROXY"; fi
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}" no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}"
exec "${MCU_CODEX_API_BIN:-$HOME/ccr/bin/codex}" "$@"
