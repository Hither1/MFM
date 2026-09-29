#!/usr/bin/env bash
# codex for the OpenRouter route. OpenRouter gates some models by the client's region;
# where the host's own egress is refused, MCU_OPENROUTER_PROXY names an HTTPS proxy, set
# here for the codex process alone: the arm's other hops (green <-> purple A2A on
# localhost) never see it.
# The key is not this script's business: codex obtains it by running the command in
# CODEX_LOCAL_AUTH_COMMAND (codex_backend.provider_auth_args), so it is never in any
# process's environment. MCU_CODEX_REAL is the binary (default: `codex` on PATH); give
# it as an absolute path, the backend sets HOME to the arm's codex home.
set -euo pipefail
PROXY="${MCU_OPENROUTER_PROXY-}"
if [ -n "$PROXY" ]; then export HTTPS_PROXY="$PROXY" https_proxy="$PROXY"; fi
exec "${MCU_CODEX_REAL:-codex}" "$@"
