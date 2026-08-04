"""Measure isolated peak RSS for the adaptive generic-key prototype."""

import argparse
import gc
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
except ImportError as error:  # pragma: no cover - unavailable on Windows
    raise SystemExit("This peak-RSS benchmark requires Linux or macOS.") from error

from benchmarks.keyed_adaptive_benchmark import CASES, KEY, create_data
from benchmarks.keyed_adaptive_prototype import sort_by_key_adaptive
from benchmarks.keyed_int64_prototype import ensure_correct


ALGORITHMS = ("sorted-key", "adaptive-key")


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def run_algorithm(algorithm, data):
    if algorithm == "sorted-key":
        return sorted(data, key=KEY)
    if algorithm == "adaptive-key":
        return sort_by_key_adaptive(data, KEY)
    raise ValueError(f"unknown algorithm: {algorithm}")


def run_worker(algorithm, case, size, seed):
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
        "elapsed_seconds": elapsed,
        "incremental_peak_bytes": incremental_peak,
    }


def invoke_worker(algorithm, case, size, seed):
    command = [
        sys.executable,
        "-m",
        "benchmarks.keyed_adaptive_memory",
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


def execute(size, cases, repetitions):
    rows = []
    print("Median incremental peak RSS")
    print(
        f"{'case':<22}  {'sorted(key=)':>15}  {'adaptive':>15}  "
        f"{'adaptive/sorted':>16}"
    )
    print("-" * 74)
    for case in cases:
        by_algorithm = {}
        for algorithm in ALGORITHMS:
            samples = [
                invoke_worker(
                    algorithm,
                    case,
                    size,
                    12000 + repetition,
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
        adaptive_peak = by_algorithm["adaptive-key"][
            "median_incremental_peak_bytes"
        ]
        ratio = adaptive_peak / sorted_peak if sorted_peak else None
        rows.append(
            {
                "size": size,
                "case": case,
                "sorted_peak_bytes": sorted_peak,
                "adaptive_peak_bytes": adaptive_peak,
                "adaptive_to_sorted_ratio": ratio,
                "samples": by_algorithm,
            }
        )
        ratio_text = f"{ratio:.2f}x" if ratio is not None else "n/a"
        print(
            f"{case:<22}  {sorted_peak / 2**20:>13.2f} MiB  "
            f"{adaptive_peak / 2**20:>13.2f} MiB  {ratio_text:>16}"
        )
    return rows


def parse_csv(value):
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=1_000_000)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--worker",
        nargs=4,
        metavar=("ALGORITHM", "CASE", "N", "SEED"),
    )
    args = parser.parse_args()

    if args.worker is not None:
        algorithm, case, size, seed = args.worker
        print(json.dumps(run_worker(algorithm, case, int(size), int(seed))))
        return

    cases = parse_csv(args.cases)
    if args.size < 1:
        parser.error("size must be positive")
    if not cases or any(case not in CASES for case in cases):
        parser.error(f"cases must be selected from: {', '.join(CASES)}")
    if args.repetitions < 1:
        parser.error("repetitions must be positive")

    rows = execute(args.size, cases, args.repetitions)
    report = {
        "schema": "bielsort-keyed-adaptive-memory-v1",
        "python": sys.version,
        "platform": sys.platform,
        "repetitions": args.repetitions,
        "rows": rows,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"\nRaw report: {args.output}")


if __name__ == "__main__":
    main()
