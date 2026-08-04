"""Measure the Python-level guard overhead on the native keyed-int64 path."""

import argparse
import gc
import json
import platform
import statistics
import struct
import sys
import time
from datetime import date
from pathlib import Path

from benchmarks.keyed_int64_guard import (
    native_worst_case_variable_auxiliary_bytes,
    sort_by_int64_key_guarded,
)
from benchmarks.keyed_int64_prototype import KEY, create_data, ensure_correct
from bielsort_native import _bielsort


ALGORITHMS = ("direct", "guard-no-limit", "guard-with-limit")
CASES = ("dense", "int64")


def run_algorithm(algorithm, data):
    if algorithm == "direct":
        return _bielsort._sort_by_int64_key_prototype(data, KEY)
    if algorithm == "guard-no-limit":
        return sort_by_int64_key_guarded(data, KEY)
    if algorithm == "guard-with-limit":
        return sort_by_int64_key_guarded(
            data,
            KEY,
            max_native_auxiliary_bytes=(
                native_worst_case_variable_auxiliary_bytes(len(data))
            ),
        )
    raise ValueError(f"unknown algorithm: {algorithm}")


def measure(data, repetitions):
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        offset = repetition % len(ALGORITHMS)
        order = ALGORITHMS[offset:] + ALGORITHMS[:offset]
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


def measure_empty_call_cost(repetitions, calls_per_sample):
    data = []
    limit = native_worst_case_variable_auxiliary_bytes(0)
    candidates = {
        "direct": lambda: _bielsort._sort_by_int64_key_prototype(data, KEY),
        "guard-no-limit": lambda: sort_by_int64_key_guarded(data, KEY),
        "guard-with-limit": lambda: sort_by_int64_key_guarded(
            data,
            KEY,
            max_native_auxiliary_bytes=limit,
        ),
    }
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        offset = repetition % len(ALGORITHMS)
        order = ALGORITHMS[offset:] + ALGORITHMS[:offset]
        for algorithm in order:
            candidate = candidates[algorithm]
            gc.disable()
            try:
                started = time.perf_counter()
                for _ in range(calls_per_sample):
                    candidate()
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            samples[algorithm].append(elapsed / calls_per_sample)

    medians = {
        algorithm: statistics.median(values)
        for algorithm, values in samples.items()
    }
    direct = medians["direct"]
    return {
        "calls_per_sample": calls_per_sample,
        "median_seconds_per_call": medians,
        "added_seconds_per_call": {
            algorithm: medians[algorithm] - direct
            for algorithm in ALGORITHMS[1:]
        },
        "samples_seconds_per_call": samples,
    }


def execute(sizes, cases, repetitions):
    rows = []
    print("Guard overhead relative to the direct private native function")
    print(
        f"{'n':>10}  {'case':<8}  {'direct':>11}  "
        f"{'no limit':>11}  {'limited':>11}  "
        f"{'no-limit Δ':>10}  {'limited Δ':>10}"
    )
    print("-" * 91)
    for size in sizes:
        for case in cases:
            data = create_data(size, case, 8200 + size)
            samples = measure(data, repetitions)
            medians = {
                algorithm: statistics.median(values)
                for algorithm, values in samples.items()
            }
            direct = medians["direct"]
            no_limit_overhead = medians["guard-no-limit"] / direct - 1
            limited_overhead = medians["guard-with-limit"] / direct - 1
            rows.append(
                {
                    "size": size,
                    "case": case,
                    "median_seconds": medians,
                    "overhead_ratio": {
                        "guard-no-limit": no_limit_overhead,
                        "guard-with-limit": limited_overhead,
                    },
                    "samples_seconds": samples,
                }
            )
            print(
                f"{size:>10,}  {case:<8}  {direct:>10.6f}s  "
                f"{medians['guard-no-limit']:>10.6f}s  "
                f"{medians['guard-with-limit']:>10.6f}s  "
                f"{no_limit_overhead:>9.2%}  {limited_overhead:>9.2%}"
            )
            del data
            gc.collect()
    return rows


def parse_csv(value, cast):
    return tuple(cast(part.strip()) for part in value.split(",") if part.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="10000,100000,1000000")
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--repetitions", type=int, default=9)
    parser.add_argument("--micro-calls", type=int, default=200_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    sizes = parse_csv(args.sizes, int)
    cases = parse_csv(args.cases, str)
    if not sizes or any(size < 0 for size in sizes):
        parser.error("sizes must contain non-negative integers")
    if not cases or any(case not in CASES for case in cases):
        parser.error(f"cases must be selected from: {', '.join(CASES)}")
    if args.repetitions < 3:
        parser.error("repetitions must be at least 3")
    if args.micro_calls < 1:
        parser.error("micro-calls must be positive")

    rows = execute(sizes, cases, args.repetitions)
    empty_call_cost = measure_empty_call_cost(
        args.repetitions,
        args.micro_calls,
    )
    direct = empty_call_cost["median_seconds_per_call"]["direct"]
    no_limit = empty_call_cost["median_seconds_per_call"]["guard-no-limit"]
    limited = empty_call_cost["median_seconds_per_call"]["guard-with-limit"]
    print("\nFixed empty-input call cost")
    print(f"direct:           {direct * 1e9:9.1f} ns/call")
    print(
        f"guard, no limit:  {no_limit * 1e9:9.1f} ns/call "
        f"(added {(no_limit - direct) * 1e9:.1f} ns)"
    )
    print(
        f"guard, limited:   {limited * 1e9:9.1f} ns/call "
        f"(added {(limited - direct) * 1e9:.1f} ns)"
    )
    report = {
        "schema": "bielsort-keyed-int64-guard-overhead-v1",
        "date": date.today().isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "pointer_bytes": struct.calcsize("P"),
        "repetitions": args.repetitions,
        "empty_call_cost": empty_call_cost,
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
