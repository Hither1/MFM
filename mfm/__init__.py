"""Multimodal Filesystem Memory.

Three layers, each importable on its own and stdlib-only:

  mfm.backend   the Codex CLI channel: argv, sandbox policy, session lifecycle, audit
  mfm.agent     the benchmark-neutral turn protocol and plan queue
  mfm.memory    the append-only log, the episode store, the index and retrieval

The benchmarks (MCU, CUA-KiCad) supply an adapter each; see PLAN_episodic_memory.md.
"""
