"""The model channel of the KiCad arms.

`codex_client` / `claude_client` are the one-call channels of the direct arm. The mfm
arm's resumed-thread channel is `mfm.backend.codex_turn.CodexTurn` on codex and
`claude_backend.ClaudeTurn` on Claude Code. `codex_sandbox.sh` / `claude_sandbox.sh`
confine a CLI call of the mfm arm to its workspace, with `sandbox_proxy.py` as the only
way out to the model API.
"""
