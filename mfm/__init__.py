"""Multimodal Filesystem Memory.

Three layers, each importable on its own and stdlib-only:

  mfm.backend   the Codex CLI channel: argv, sandbox policy, session lifecycle, audit
  mfm.agent     the benchmark-neutral turn protocol and plan queue
  mfm.memory    the append-only log, the episode store, the index and retrieval

The benchmarks supply an adapter each: `MCU/mcu_worldmodel/episodes.py` and
`CUA-KiCad/gym_codex/mfm_agent.py`.
"""
