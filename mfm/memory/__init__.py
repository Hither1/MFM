"""What the agent remembers between model calls, as files in its workspace.

`log.EpisodeLog` is PRO-LONG's append-only `logs.txt` plus the attachment tree and the
ablation-enforcing `publish`. `sink.MemorySink` is the hook set a second memory (the
episode store) implements to be written from the same call sites.
"""
