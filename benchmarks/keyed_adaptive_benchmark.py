"""Benchmark the private generic-key selector against ``sorted(key=...)``."""

import argparse
import gc
import json
import platform
import random
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from bielsort_native._keyed_adaptive import sort_by_key_adaptive
from benchmarks.keyed_int64_prototype import KEY, Record, ensure_correct


ALGORITHMS = ("sorted-key", "adaptive-key")
CASES = (
    "int64",
    "nearly-sorted-int64",
    "nearly-sorted-wide-int64",
    "nearly-sorted-spaced-int64",
    "ordered-prefix-random-int64",
    "string",
    "huge-int",
)


def create_data(size, case, seed):
    rng = random.Random(seed)
    if case.startswith("nearly-sorted-"):
        if case == "nearly-sorted-int64":
            data = [Record(position, position) for position in range(size)]
        elif case == "nearly-sorted-wide-int64":
            data = [
                rng.randint(-(1 << 63), (1 << 63) - 1)
                for _ in range(size)
            ]
            data.sort()
            for position, key in enumerate(data):
                data[position] = Record(key, position)
        elif case == "nearly-sorted-spaced-int64":
            data = [
                Record(position * 1_000_000, position)
                for position in range(size)
            ]
        else:
            raise ValueError(f"unknown case: {case}")
        for _ in range(max(1, size // 500)):
            left = rng.randrange(size)
            right = rng.randrange(size)
            data[left].sort_key, data[right].sort_key = (
                data[right].sort_key,
                data[left].sort_key,
            )
        return data

    if case == "ordered-prefix-random-int64":
        prefix_size = min(size, 512)
        data = [
            Record(position * 1_000_000, position)
            for position in range(prefix_size)
        ]
        data.extend(
            Record(
                rng.randint(-(1 << 63), (1 << 63) - 1),
                position,
            )
            for position in range(prefix_size, size)
        )
        return data

    values = (
        rng.randint(-(1 << 63), (1 << 63) - 1)
        for _ in range(size)
    )
    if case == "string":
        keys = (f"{value:+021d}" for value in values)
    elif case == "huge-int":
        keys = (value * (1 << 80) for value in values)
    elif case == "int64":
        keys = iter(values)
    else:
        raise ValueError(f"unknown case: {case}")
    return [Record(key, position) for position, key in enumerate(keys)]


def run_algorithm(algorithm, data, reverse):
    if algorithm == "sorted-key":
        return sorted(data, key=KEY, reverse=reverse)
    if algorithm == "adaptive-key":
        return sort_by_key_adaptive(data, KEY, reverse=reverse)
    raise ValueError(f"unknown algorithm: {algorithm}")


def measure(data, repetitions, reverse):
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        order = ALGORITHMS if repetition % 2 == 0 else ALGORITHMS[::-1]
        for algorithm in order:
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(algorithm, data, reverse)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_correct(result, data, reverse=reverse)
            samples[algorithm].append(elapsed)
            del result
    gc.collect()
    return samples


def execute(sizes, cases, repetitions, reverse=False):
    rows = []
    direction = "descending" if reverse else "ascending"
    print(
        "Adaptive generic-key prototype "
        f"({direction}; above 1.00x favors BielSort)"
    )
    print(
        f"{'n':>10}  {'case':<22}  {'sorted(key=)':>13}  "
        f"{'adaptive':>13}  {'speedup':>9}"
    )
    print("-" * 76)
    for size in sizes:
        for case in cases:
            data = create_data(size, case, 9600 + size)
            samples = measure(data, repetitions, reverse)
            sorted_median = statistics.median(samples["sorted-key"])
            adaptive_median = statistics.median(samples["adaptive-key"])
            speedup = sorted_median / adaptive_median
            result, info = sort_by_key_adaptive(
                data,
                KEY,
                reverse=reverse,
                return_info=True,
            )
            ensure_correct(result, data, reverse=reverse)
            row = {
                "size": size,
                "case": case,
                "algorithm": info["algorithm"],
                "reverse": reverse,
                "sorted_median_seconds": sorted_median,
                "adaptive_median_seconds": adaptive_median,
                "speedup": speedup,
                "sorted_samples_seconds": samples["sorted-key"],
                "adaptive_samples_seconds": samples["adaptive-key"],
            }
            rows.append(row)
            print(
                f"{size:>10,}  {case:<22}  {sorted_median:>12.6f}s  "
                f"{adaptive_median:>12.6f}s  {speedup:>8.2f}x"
            )
            del result
            del data
            gc.collect()
    return rows


def parse_csv(value, cast):
    return tuple(cast(part.strip()) for part in value.split(",") if part.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="10000,100000,1000000")
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sizes = parse_csv(args.sizes, int)
    cases = parse_csv(args.cases, str)
    if not sizes or any(size < 1 for size in sizes):
        parser.error("sizes must contain positive integers")
    if not cases or any(case not in CASES for case in cases):
        parser.error(f"cases must be selected from: {', '.join(CASES)}")
    if args.repetitions < 3:
        parser.error("repetitions must be at least 3")

    rows = execute(sizes, cases, args.repetitions, reverse=args.reverse)
    report = {
        "schema": "bielsort-keyed-adaptive-benchmark-v1",
        "date": date.today().isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "repetitions": args.repetitions,
        "reverse": args.reverse,
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
