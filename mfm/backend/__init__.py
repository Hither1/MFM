"""The Codex CLI channel: argv, sandbox policy, session lifecycle, audit.

`codex_turn.CodexTurn` is the resumable conversation; `errors` classifies a failed turn
for the agents' retry loops. The bubblewrap wrapper and its egress proxy stay beside
the benchmark (`CUA-KiCad/model_channel/codex_sandbox.sh`): the
wrapper bind-mounts `sandbox_proxy.py` into a namespace that has no site-packages, so the
proxy has to be a self-contained file beside the script that mounts it.
"""
