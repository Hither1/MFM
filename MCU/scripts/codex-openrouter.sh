#!/usr/bin/env bash
# codex for the OpenRouter route: the same binary, reached through the host's proxy.
# OpenRouter gates OpenAI and Anthropic models by client region -- 403 "not available in
# your region" from this host's Beijing egress, both endpoints (2026-09-09) -- and serves
# them from the proxy's Los Angeles exit. The proxy is set here, for the codex process
# alone: the arm's other hops (green <-> purple A2A on localhost) never see it.
# The key is not this script's business: codex obtains it by running the command in
# CODEX_LOCAL_AUTH_COMMAND (codex_backend.provider_auth_args), so it is never in any
# process's environment. Absolute paths: the backend sets HOME to the arm's codex home.
set -euo pipefail
PROXY="${MCU_OPENROUTER_PROXY-http://192.168.1.64:7890}"
if [ -n "$PROXY" ]; then export HTTPS_PROXY="$PROXY" https_proxy="$PROXY"; fi
exec "${MCU_CODEX_REAL:-/datapool/data2/home/ruihan/.nvm/versions/node/v22.18.0/bin/codex}" "$@"
