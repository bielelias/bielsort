"""Example provider for benchmarks/workload_evaluator.py.

Copy this file and replace only ``load_values`` with code that loads or builds
your real list. This synthetic example is for testing the evaluator and must
not be submitted as a real-world workload.
"""

from random import Random


def load_values():
    """Return one exact list without printing or uploading its contents."""
    rng = Random(42)
    return [rng.randint(-(1 << 63), (1 << 63) - 1) for _ in range(100_000)]

