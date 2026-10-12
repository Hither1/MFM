"""The benchmark-neutral turn protocol: observe, refill the plan queue when it runs
dry, pop one item, write memory at each point. Benchmarks subclass `base.MemoryAgent`
and implement its hooks; see `mfm/agent/base.py`."""
