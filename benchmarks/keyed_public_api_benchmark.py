"""Benchmark the candidate public ``sort(key=...)`` adaptive path."""

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

import bielsort
from benchmarks.keyed_adaptive_benchmark import (
    CASES as PRIVATE_CASES,
    KEY,
    create_data,
)
from benchmarks.keyed_int64_prototype import Record, ensure_correct


ALGORITHMS = ("sorted-key", "bielsort-key")
CASES = ("dense-int64", *PRIVATE_CASES)


def create_public_data(size, case, seed):
    if case != "dense-int64":
        return create_data(size, case, seed)
    rng = random.Random(seed)
    return [
        Record(rng.randrange(-size // 4, size // 4), position)
        for position in range(size)
    ]


def run_algorithm(algorithm, data, reverse):
    if algorithm == "sorted-key":
        return sorted(data, key=KEY, reverse=reverse)
    if algorithm == "bielsort-key":
        return bielsort.sort(data, key=KEY, reverse=reverse)
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
        "Candidate public sort(key=...) "
        f"({direction}; above 1.00x favors BielSort)"
    )
    print(
        f"{'n':>10}  {'case':<32}  {'sorted(key=)':>13}  "
        f"{'bielsort':>13}  {'speedup':>9}"
    )
    print("-" * 86)
    for size in sizes:
        for case in cases:
            data = create_public_data(size, case, 16_000 + size)
            samples = measure(data, repetitions, reverse)
            sorted_median = statistics.median(samples["sorted-key"])
            bielsort_median = statistics.median(samples["bielsort-key"])
            result, strategy = bielsort.sort_with_strategy(
                data,
                key=KEY,
                reverse=reverse,
            )
            ensure_correct(result, data, reverse=reverse)
            row = {
                "size": size,
                "case": case,
                "strategy": strategy,
                "reverse": reverse,
                "sorted_median_seconds": sorted_median,
                "bielsort_median_seconds": bielsort_median,
                "speedup": sorted_median / bielsort_median,
                "sorted_samples_seconds": samples["sorted-key"],
                "bielsort_samples_seconds": samples["bielsort-key"],
            }
            rows.append(row)
            print(
                f"{size:>10,}  {case:<32}  {sorted_median:>12.6f}s  "
                f"{bielsort_median:>12.6f}s  {row['speedup']:>8.2f}x"
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
        "schema": "bielsort-keyed-public-api-benchmark-v1",
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
