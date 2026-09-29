#!/usr/bin/env bash
# Does the agent's node reach the server, and does codex get a usable answer from it?
set -uo pipefail
ROOT=/n/holylfs06/LABS/sham_lab/Users/chloe00/MCU
cd "$ROOT"
DISC=artifacts/servers/qwen38-27b.json
URL=$(python3 -c "import json;print(json.load(open('$DISC'))['url'])")
MODEL=$(python3 -c "import json;print(json.load(open('$DISC'))['model'])")
echo "node=$(hostname -s) url=$URL model=$MODEL"

echo "--- 1. reachability ---"
curl -fsS --max-time 30 "$URL/models" >/dev/null && echo "  /v1/models reachable" || { echo "  UNREACHABLE"; exit 1; }

echo "--- 2. codex round trip over /v1/responses ---"
export LOCAL_API_KEY=EMPTY
export CODEX_HOME="$ROOT/artifacts/wiretest-codexhome"
rm -rf "$CODEX_HOME"; mkdir -p "$CODEX_HOME"
timeout 900 codex exec --json --skip-git-repo-check --ignore-user-config \
  -m "$MODEL" \
  -c model_provider=local \
  -c 'model_providers.local.name="local"' \
  -c "model_providers.local.base_url=\"$URL\"" \
  -c 'model_providers.local.wire_api="responses"' \
  -c 'model_providers.local.env_key="LOCAL_API_KEY"' \
  -c 'sandbox_mode="read-only"' \
  - <<'PROMPT' > artifacts/wiretest.jsonl 2>&1
Reply with exactly the word: HANDSHAKE
PROMPT
rc=$?
echo "  codex rc=$rc"
echo "--- 3. did a model message come back? ---"
grep -oE '"type":"[a-z_.]+"' artifacts/wiretest.jsonl 2>/dev/null | sort | uniq -c | tail -8
echo "--- text seen ---"
grep -oE 'HANDSHAKE' artifacts/wiretest.jsonl 2>/dev/null | head -2
echo "--- errors ---"
grep -oiE '"(message|error)":"[^"]{0,180}' artifacts/wiretest.jsonl 2>/dev/null | tail -5
