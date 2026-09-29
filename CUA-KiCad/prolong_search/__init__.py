"""The model channel and the log substrate the KiCad memory arms run on.

`codex_client` / `claude_client` are the one-call channels of the direct arm;
`codex_backend` / `claude_backend` the resumed-thread channels of the memory arms
(thin bindings of `mfm.backend`); `log` the append-only episode log (`mfm.memory.log`).
`codex_sandbox.sh` / `claude_sandbox.sh` confine a CLI call to its workspace, with
`sandbox_proxy.py` as the only way out to the model API.
"""
