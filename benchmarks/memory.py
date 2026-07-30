"""Measure incremental peak RSS in an isolated process per algorithm."""

import argparse
import gc
import json
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
except ImportError as error:  # pragma: no cover - unavailable on Windows
    raise SystemExit(
        "The memory benchmark currently requires Linux or macOS."
    ) from error

from bielsort import biel_sort, biel_sort_in_place


ALGORITHMS = ("sorted", "biel-new", "list.sort", "biel-in-place")
CASES = ("dense", "int64")


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def create_data(size, case, seed):
    rng = random.Random(seed)
    if case == "dense":
        return [rng.randint(-size // 4, size // 4) for _ in range(size)]
    if case == "int64":
        return [
            rng.randint(-(1 << 63), (1 << 63) - 1)
            for _ in range(size)
        ]
    raise ValueError(f"Unknown case: {case}")


def ensure_sorted(values):
    if any(left > right for left, right in zip(values, values[1:])):
        raise AssertionError("Incorrect sorting result")


def run_worker(algorithm, case, size, seed):
    data = create_data(size, case, seed)
    gc.collect()
    baseline = peak_rss_bytes()
    started = time.perf_counter()

    if algorithm == "sorted":
        result = sorted(data)
    elif algorithm == "biel-new":
        result = biel_sort(data)
    elif algorithm == "list.sort":
        data.sort()
        result = data
    elif algorithm == "biel-in-place":
        biel_sort_in_place(data)
        result = data
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    elapsed = time.perf_counter() - started
    incremental_peak = max(0, peak_rss_bytes() - baseline)
    ensure_sorted(result)
    return {
        "algorithm": algorithm,
        "case": case,
        "size": size,
        "elapsed_s": elapsed,
        "incremental_peak_bytes": incremental_peak,
    }


def invoke_worker(algorithm, case, size, seed):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        algorithm,
        case,
        str(size),
        str(seed),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def execute(size, repetitions, cases):
    print(
        f"{'case':<8}  {'algorithm':<14}  {'median time':>12}"
        f"  {'incremental peak':>18}"
    )
    print("-" * 60)

    results = []
    for case in cases:
        for algorithm in ALGORITHMS:
            samples = [
                invoke_worker(
                    algorithm,
                    case,
                    size,
                    2026 + repetition,
                )
                for repetition in range(repetitions)
            ]
            median_time = statistics.median(
                sample["elapsed_s"] for sample in samples
            )
            median_peak = statistics.median(
                sample["incremental_peak_bytes"] for sample in samples
            )
            result = {
                "case": case,
                "algorithm": algorithm,
                "size": size,
                "median_time_s": median_time,
                "median_incremental_peak_bytes": median_peak,
            }
            results.append(result)
            print(
                f"{case:<8}  {algorithm:<14}  {median_time:>11.5f}s"
                f"  {median_peak / (1024 * 1024):>16.2f} MiB"
            )
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--size", type=int, default=1_000_000)
    parser.add_argument("-r", "--repetitions", type=int, default=3)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=CASES,
        default=list(CASES),
    )
    parser.add_argument(
        "--worker",
        nargs=4,
        metavar=("ALGORITHM", "CASE", "SIZE", "SEED"),
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args()

    if arguments.worker:
        algorithm, case, size, seed = arguments.worker
        print(json.dumps(run_worker(algorithm, case, int(size), int(seed))))
        return

    execute(arguments.size, arguments.repetitions, arguments.cases)


if __name__ == "__main__":
    main()
