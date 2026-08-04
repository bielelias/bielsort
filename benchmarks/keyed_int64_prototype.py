"""Evaluate the research-only stable int64-key object sorting path.

The benchmark compares equivalent new-list operations. Both candidates receive
the same live list of Python objects, call the same key callable, preserve the
input, and return a new list. Peak RSS is measured in isolated subprocesses.
"""

import argparse
import gc
import json
import random
import statistics
import subprocess
import sys
import time
from operator import attrgetter
from pathlib import Path

try:
    import resource
except ImportError as error:  # pragma: no cover - unavailable on Windows
    raise SystemExit(
        "The keyed prototype memory benchmark requires Linux or macOS."
    ) from error

from bielsort_native import _bielsort


ALGORITHMS = ("sorted-key", "biel-keyed-prototype")
CASES = ("dense", "timestamp", "int32", "int64", "nearly-sorted")
KEY = attrgetter("sort_key")
IMPLEMENTATION = "compact-keyed-int64-radix"


class Record:
    __slots__ = ("sort_key", "original_position", "payload")

    def __init__(self, sort_key, original_position):
        self.sort_key = sort_key
        self.original_position = original_position
        self.payload = original_position ^ 0x5A5A


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def iter_keys(size, case, seed):
    rng = random.Random(seed)
    if case == "dense":
        for _ in range(size):
            yield rng.randint(-size // 4, size // 4)
    elif case == "timestamp":
        start = 1_700_000_000_000_000
        one_week_us = 7 * 24 * 60 * 60 * 1_000_000
        for _ in range(size):
            yield start + rng.randrange(one_week_us)
    elif case == "int32":
        for _ in range(size):
            yield rng.randint(-(1 << 31), (1 << 31) - 1)
    elif case == "int64":
        for _ in range(size):
            yield rng.randint(-(1 << 63), (1 << 63) - 1)
    elif case != "nearly-sorted":
        raise ValueError(f"Unknown case: {case}")


def create_data(size, case, seed):
    if case == "nearly-sorted":
        data = [Record(position, position) for position in range(size)]
        rng = random.Random(seed)
        for _ in range(max(1, size // 500)):
            left = rng.randrange(size)
            right = rng.randrange(size)
            data[left].sort_key, data[right].sort_key = (
                data[right].sort_key,
                data[left].sort_key,
            )
        return data

    return [
        Record(key, position)
        for position, key in enumerate(iter_keys(size, case, seed))
    ]


def run_algorithm(algorithm, data):
    if algorithm == "sorted-key":
        return sorted(data, key=KEY)
    if algorithm == "biel-keyed-prototype":
        return _bielsort._sort_by_int64_key_prototype(data, KEY)
    raise ValueError(f"Unknown algorithm: {algorithm}")


def ensure_correct(result, data, reverse=False):
    if len(result) != len(data):
        raise AssertionError("Incorrect result length")
    if result is data:
        raise AssertionError("New-list operation returned the input list")

    previous_key = None
    previous_position = None
    first = True
    result_ids = set()
    for record in result:
        if not first:
            if (
                record.sort_key > previous_key
                if reverse
                else record.sort_key < previous_key
            ):
                raise AssertionError("Result is not ordered")
            if (
                record.sort_key == previous_key
                and record.original_position < previous_position
            ):
                raise AssertionError("Result is not stable")
        first = False
        previous_key = record.sort_key
        previous_position = record.original_position
        result_ids.add(id(record))

    if len(result_ids) != len(data):
        raise AssertionError("Result duplicated or lost an object")
    if result_ids != {id(record) for record in data}:
        raise AssertionError("Result did not preserve object identity")


def measure_time_pair(data, repetitions):
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        order = (
            ALGORITHMS
            if repetition % 2 == 0
            else tuple(reversed(ALGORITHMS))
        )
        for algorithm in order:
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(algorithm, data)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_correct(result, data)
            samples[algorithm].append(elapsed)
            del result
    gc.collect()
    return samples


def run_memory_worker(algorithm, case, size, seed):
    data = create_data(size, case, seed)
    gc.collect()
    baseline = peak_rss_bytes()
    started = time.perf_counter()
    result = run_algorithm(algorithm, data)
    elapsed = time.perf_counter() - started
    incremental_peak = max(0, peak_rss_bytes() - baseline)
    ensure_correct(result, data)
    return {
        "algorithm": algorithm,
        "case": case,
        "size": size,
        "elapsed_s": elapsed,
        "incremental_peak_bytes": incremental_peak,
    }


def invoke_memory_worker(algorithm, case, size, seed):
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


def execute_time_benchmark(sizes, repetitions, cases):
    print("\nTIME (median; speedup above 1.00x favors BielSort)")
    print(
        f"{'n':>10}  {'case':<15}  {'sorted(key=)':>13}"
        f"  {'Biel keyed':>13}  {'speedup':>9}"
    )
    print("-" * 70)
    rows = []
    for size in sizes:
        for case in cases:
            data = create_data(size, case, 2026 + size)
            samples = measure_time_pair(data, repetitions)
            sorted_samples = samples["sorted-key"]
            biel_samples = samples["biel-keyed-prototype"]
            sorted_median = statistics.median(sorted_samples)
            biel_median = statistics.median(biel_samples)
            speedup = sorted_median / biel_median
            row = {
                "size": size,
                "case": case,
                "sorted_median_s": sorted_median,
                "biel_median_s": biel_median,
                "speedup": speedup,
                "sorted_samples_s": sorted_samples,
                "biel_samples_s": biel_samples,
            }
            rows.append(row)
            print(
                f"{size:>10,}  {case:<15}  {sorted_median:>12.6f}s"
                f"  {biel_median:>12.6f}s  {speedup:>8.2f}x"
            )
            del data
            gc.collect()
    return rows


def execute_memory_benchmark(size, repetitions, cases):
    print("\nPEAK RSS (median incremental peak; lower is better)")
    print(
        f"{'case':<15}  {'sorted(key=)':>15}  {'Biel keyed':>15}"
        f"  {'Biel/sorted':>13}"
    )
    print("-" * 67)
    rows = []
    for case in cases:
        by_algorithm = {}
        for algorithm in ALGORITHMS:
            samples = [
                invoke_memory_worker(
                    algorithm,
                    case,
                    size,
                    4040 + repetition,
                )
                for repetition in range(repetitions)
            ]
            by_algorithm[algorithm] = {
                "median_incremental_peak_bytes": statistics.median(
                    sample["incremental_peak_bytes"] for sample in samples
                ),
                "samples": samples,
            }

        sorted_peak = by_algorithm["sorted-key"][
            "median_incremental_peak_bytes"
        ]
        biel_peak = by_algorithm["biel-keyed-prototype"][
            "median_incremental_peak_bytes"
        ]
        ratio = biel_peak / sorted_peak if sorted_peak else float("inf")
        row = {
            "size": size,
            "case": case,
            "sorted_peak_bytes": sorted_peak,
            "biel_peak_bytes": biel_peak,
            "biel_to_sorted_ratio": ratio,
            "raw": by_algorithm,
        }
        rows.append(row)
        print(
            f"{case:<15}  {sorted_peak / 2**20:>13.2f} MiB"
            f"  {biel_peak / 2**20:>13.2f} MiB  {ratio:>12.2f}x"
        )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--sizes",
        nargs="+",
        type=int,
        default=[10_000, 100_000, 1_000_000],
    )
    parser.add_argument("-r", "--repetitions", type=int, default=5)
    parser.add_argument(
        "--memory-repetitions",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=CASES,
        default=list(CASES),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path for raw, reviewable benchmark results.",
    )
    parser.add_argument(
        "--skip-memory",
        action="store_true",
        help="Skip isolated-process peak RSS measurement.",
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
        print(
            json.dumps(
                run_memory_worker(
                    algorithm,
                    case,
                    int(size),
                    int(seed),
                )
            )
        )
        return

    # Run child-process RSS measurements before this supervisor has ever held a
    # large workload. On Linux, ru_maxrss can retain a high-water mark across
    # exec, so timing first could make children inherit a misleading peak and
    # report zero incremental memory.
    memory_rows = []
    if not arguments.skip_memory:
        memory_rows = execute_memory_benchmark(
            max(arguments.sizes),
            arguments.memory_repetitions,
            arguments.cases,
        )
    time_rows = execute_time_benchmark(
        arguments.sizes,
        arguments.repetitions,
        arguments.cases,
    )

    if arguments.json_output:
        payload = {
            "schema_version": 1,
            "benchmark": "keyed-int64-prototype",
            "implementation": IMPLEMENTATION,
            "python": sys.version,
            "platform": sys.platform,
            "time": time_rows,
            "memory": memory_rows,
        }
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nRaw results written to {arguments.json_output}")


if __name__ == "__main__":
    main()
