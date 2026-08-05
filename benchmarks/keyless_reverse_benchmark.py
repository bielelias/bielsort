"""Benchmark the experimental keyless ``reverse=True`` public path."""

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


ALGORITHMS = ("sorted-reverse", "bielsort-reverse")
IN_PLACE_ALGORITHMS = ("list-sort-reverse", "bielsort-in-place-reverse")
CASES = (
    "dense-int64",
    "random-int32",
    "random-int64",
    "nearly-descending",
    "ascending",
)


def create_data(size, case, seed):
    rng = random.Random(seed)
    if case == "dense-int64":
        return [rng.randrange(-size // 4, size // 4) for _ in range(size)]
    if case == "random-int32":
        return [rng.randint(-(1 << 31), (1 << 31) - 1) for _ in range(size)]
    if case == "random-int64":
        return [rng.randint(-(1 << 63), (1 << 63) - 1) for _ in range(size)]
    if case == "nearly-descending":
        values = list(range(size, 0, -1))
        for _ in range(max(1, size // 500)):
            left = rng.randrange(size)
            right = rng.randrange(size)
            values[left], values[right] = values[right], values[left]
        return values
    if case == "ascending":
        return list(range(size))
    raise ValueError(f"unknown case: {case}")


def run_algorithm(algorithm, data):
    if algorithm == "sorted-reverse":
        return sorted(data, reverse=True)
    if algorithm == "bielsort-reverse":
        return bielsort.sort(data, reverse=True)
    raise ValueError(f"unknown algorithm: {algorithm}")


def measure(data, expected, repetitions):
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        order = ALGORITHMS if repetition % 2 == 0 else ALGORITHMS[::-1]
        for algorithm in order:
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(algorithm, data)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            if result != expected:
                raise AssertionError(f"incorrect result from {algorithm}")
            samples[algorithm].append(elapsed)
            del result
    gc.collect()
    return samples


def run_in_place_algorithm(algorithm, values):
    if algorithm == "list-sort-reverse":
        return values.sort(reverse=True)
    if algorithm == "bielsort-in-place-reverse":
        return bielsort.sort_in_place(values, reverse=True)
    raise ValueError(f"unknown in-place algorithm: {algorithm}")


def measure_in_place(data, expected, repetitions):
    samples = {algorithm: [] for algorithm in IN_PLACE_ALGORITHMS}
    for repetition in range(repetitions):
        order = (
            IN_PLACE_ALGORITHMS
            if repetition % 2 == 0
            else IN_PLACE_ALGORITHMS[::-1]
        )
        for algorithm in order:
            values = data.copy()
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_in_place_algorithm(algorithm, values)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            if result is not None or values != expected:
                raise AssertionError(f"incorrect result from {algorithm}")
            samples[algorithm].append(elapsed)
            del values
    gc.collect()
    return samples


def execute(sizes, cases, repetitions):
    rows = []
    print("Keyless reverse=True (above 1.00x favors BielSort)")
    print(
        f"{'n':>10}  {'case':<24}  {'strategy':<36}  "
        f"{'sorted':>12}  {'bielsort':>12}  {'speedup':>9}  "
        f"{'.sort':>12}  {'biel-ip':>12}  {'speedup':>9}"
    )
    print("-" * 152)
    for size in sizes:
        for case in cases:
            data = create_data(size, case, 21_000 + size)
            expected = sorted(data, reverse=True)
            samples = measure(data, expected, repetitions)
            in_place_samples = measure_in_place(data, expected, repetitions)
            sorted_median = statistics.median(samples["sorted-reverse"])
            bielsort_median = statistics.median(
                samples["bielsort-reverse"]
            )
            list_sort_median = statistics.median(
                in_place_samples["list-sort-reverse"]
            )
            bielsort_in_place_median = statistics.median(
                in_place_samples["bielsort-in-place-reverse"]
            )
            result, strategy = bielsort.sort_with_strategy(
                data,
                reverse=True,
            )
            if result != expected:
                raise AssertionError("diagnostic result is incorrect")
            row = {
                "size": size,
                "case": case,
                "strategy": strategy,
                "sorted_median_seconds": sorted_median,
                "bielsort_median_seconds": bielsort_median,
                "speedup": sorted_median / bielsort_median,
                "list_sort_median_seconds": list_sort_median,
                "bielsort_in_place_median_seconds": (
                    bielsort_in_place_median
                ),
                "in_place_speedup": (
                    list_sort_median / bielsort_in_place_median
                ),
                "sorted_samples_seconds": samples["sorted-reverse"],
                "bielsort_samples_seconds": samples["bielsort-reverse"],
                "list_sort_samples_seconds": (
                    in_place_samples["list-sort-reverse"]
                ),
                "bielsort_in_place_samples_seconds": (
                    in_place_samples["bielsort-in-place-reverse"]
                ),
            }
            rows.append(row)
            print(
                f"{size:>10,}  {case:<24}  {strategy:<36}  "
                f"{sorted_median:>11.6f}s  {bielsort_median:>11.6f}s  "
                f"{row['speedup']:>8.2f}x  {list_sort_median:>11.6f}s  "
                f"{bielsort_in_place_median:>11.6f}s  "
                f"{row['in_place_speedup']:>8.2f}x"
            )
            del result
            del expected
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

    rows = execute(sizes, cases, args.repetitions)
    report = {
        "schema": "bielsort-keyless-reverse-benchmark-v1",
        "research": "unreleased keyless reverse public-path prototype",
        "date": date.today().isoformat(),
        "bielsort_version": bielsort.__version__,
        "python": sys.version,
        "platform": platform.platform(),
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
