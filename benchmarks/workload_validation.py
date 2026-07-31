"""Validate BielSort against synthetic proxies for real Python workloads.

The input generators are deliberately transparent. They do not claim to be
production datasets; they let potential users replace a proxy with an
anonymized generator that matches their own list[int] workload.
"""

import argparse
import gc
import json
import os
import platform
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from bielsort import __version__ as bielsort_version
from bielsort import sort as bielsort_sort
from bielsort import sort_with_strategy

try:
    import numpy as np
except ImportError:  # NumPy is an optional comparison dependency.
    np = None


INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1

CASE_DESCRIPTIONS = {
    "event-timestamps": (
        "unordered event timestamps from one UTC day, with duplicates"
    ),
    "signed-record-ids": (
        "unordered signed 64-bit record identifiers across a wide range"
    ),
    "mostly-ordered-offsets": (
        "append-like integer offsets with a small number of displaced items"
    ),
}


def create_case(name, size, seed):
    """Create one deterministic list[int] workload proxy."""
    if size < 1:
        raise ValueError("size must be at least 1")

    rng = random.Random(seed)
    if name == "event-timestamps":
        start_of_day = 1_767_225_600
        return [
            start_of_day + rng.randrange(86_400)
            for _ in range(size)
        ]

    if name == "signed-record-ids":
        return [rng.randint(INT64_MIN, INT64_MAX) for _ in range(size)]

    if name == "mostly-ordered-offsets":
        values = list(range(size))
        for _ in range(max(1, size // 500)):
            left = rng.randrange(size)
            right = rng.randrange(size)
            values[left], values[right] = values[right], values[left]
        return values

    raise ValueError(f"unknown case: {name}")


def _measure_operations(operations, expected, repetitions, seed):
    samples = {name: [] for name in operations}
    order_rng = random.Random(seed)

    for _ in range(repetitions):
        names = list(operations)
        order_rng.shuffle(names)
        for name in names:
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = operations[name]()
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()

            if result != expected:
                raise AssertionError(f"incorrect result from {name}")
            samples[name].append(elapsed)

    return {
        name: statistics.median(timings)
        for name, timings in samples.items()
    }


def benchmark_case(name, values, repetitions, include_numpy, seed):
    """Benchmark equivalent new-list operations for one prepared input."""
    expected = sorted(values)
    diagnostic_result, strategy = sort_with_strategy(values)
    if diagnostic_result != expected:
        raise AssertionError("incorrect diagnostic BielSort result")

    operations = {
        "sorted": lambda: sorted(values),
        "bielsort": lambda: bielsort_sort(values),
    }
    if include_numpy:
        operations["numpy-e2e"] = lambda: np.sort(
            np.asarray(values, dtype=np.int64),
            kind="stable",
        ).tolist()

    timings = _measure_operations(
        operations,
        expected,
        repetitions,
        seed,
    )
    bielsort_time = timings["bielsort"]
    result = {
        "case": name,
        "description": CASE_DESCRIPTIONS[name],
        "size": len(values),
        "strategy": strategy,
        "native_fast_path": strategy.startswith(
            ("counting nativo", "radix nativo")
        ),
        "median_seconds": timings,
        "bielsort_speedup_vs_sorted": timings["sorted"] / bielsort_time,
        "winner": min(timings, key=timings.get),
    }
    if "numpy-e2e" in timings:
        result["bielsort_speedup_vs_numpy_e2e"] = (
            timings["numpy-e2e"] / bielsort_time
        )
    return result


def environment_metadata():
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "bielsort": bielsort_version,
        "numpy": np.__version__ if np is not None else None,
    }


def run_validation(
    sizes,
    repetitions,
    cases,
    include_numpy,
    show_table=True,
    context=None,
):
    """Run all requested proxies and return a JSON-serializable report."""
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if include_numpy and np is None:
        raise RuntimeError(
            "NumPy is not installed; install with "
            "`python -m pip install -e '.[benchmark]'` or pass "
            "`--without-numpy`."
        )

    results = []
    if show_table:
        numpy_heading = f"  {'NumPy E2E':>10}" if include_numpy else ""
        print(
            f"{'n':>10}  {'workload':<23}  {'strategy':<31}"
            f"  {'sorted':>10}  {'BielSort':>10}{numpy_heading}"
            f"  {'Biel gain':>9}  {'winner':<10}"
        )
        print("-" * (122 if include_numpy else 110))

    for size in sizes:
        for case_index, case in enumerate(cases):
            seed = 20_260_731 + size + case_index
            values = create_case(case, size, seed)
            result = benchmark_case(
                case,
                values,
                repetitions,
                include_numpy,
                seed,
            )
            results.append(result)

            if show_table:
                timings = result["median_seconds"]
                numpy_value = (
                    f"  {timings['numpy-e2e']:>9.5f}s"
                    if include_numpy
                    else ""
                )
                print(
                    f"{size:>10,}  {case:<23}  {result['strategy']:<31}"
                    f"  {timings['sorted']:>9.5f}s"
                    f"  {timings['bielsort']:>9.5f}s{numpy_value}"
                    f"  {result['bielsort_speedup_vs_sorted']:>8.2f}x"
                    f"  {result['winner']:<10}"
                )

    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment_metadata(),
        "configuration": {
            "context": context,
            "sizes": list(sizes),
            "repetitions": repetitions,
            "cases": list(cases),
            "numpy_end_to_end": include_numpy,
            "timing_policy": (
                "median; deterministic interleaved order; input generation "
                "and expected result excluded"
            ),
        },
        "results": results,
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Validate BielSort on transparent workload proxies and optionally "
            "write a shareable JSON report."
        )
    )
    parser.add_argument(
        "-n",
        "--sizes",
        nargs="+",
        type=int,
        default=[10_000, 100_000, 1_000_000],
    )
    parser.add_argument("-r", "--repetitions", type=int, default=5)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=tuple(CASE_DESCRIPTIONS),
        default=list(CASE_DESCRIPTIONS),
    )
    parser.add_argument(
        "--without-numpy",
        action="store_true",
        help="compare only equivalent Python-list APIs",
    )
    parser.add_argument(
        "--json",
        type=Path,
        metavar="PATH",
        help="write environment, configuration, and results as JSON",
    )
    parser.add_argument(
        "--context",
        help="identify the machine, installation source, or experiment",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    include_numpy = not arguments.without_numpy

    print(
        "Synthetic workload proxies; median of "
        f"{arguments.repetitions} runs. A Biel gain above 1.00x favors "
        "BielSort over sorted()."
    )
    report = run_validation(
        arguments.sizes,
        arguments.repetitions,
        arguments.cases,
        include_numpy,
        context=arguments.context,
    )

    if arguments.json:
        arguments.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote report to {arguments.json}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error
