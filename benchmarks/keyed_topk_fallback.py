"""Measure private adaptive generic-key top-k continuation gates.

The exact-int64 section protects the frozen stage-one core from adaptive-path
regression. The generic section compares arbitrary comparable Python keys
with ``heapq``. Record construction and stable references stay outside the
timed region; all results preserve exact record identity.
"""

import argparse
import gc
import heapq
import json
import operator
import platform
import random
import statistics
import sys
import time
from pathlib import Path

from bielsort_native import _bielsort


HEAPQ = "python-heapq-records"
STRICT = "biel-strict-int64-core"
ADAPTIVE = "biel-adaptive-keyed-topk"
EXACT_ALGORITHMS = (HEAPQ, STRICT, ADAPTIVE)
GENERIC_ALGORITHMS = (HEAPQ, ADAPTIVE)
EXACT_CASES = ("dense", "int32", "int64", "heavy-duplicates")
GENERIC_CASES = ("huge-int", "string", "tuple", "finite-float")
DIRECTIONS = ("smallest", "largest")
KEY = operator.itemgetter(0)


def rotate(items, offset):
    offset %= len(items)
    return items[offset:] + items[:offset]


def create_exact_values(size, case, seed):
    rng = random.Random(seed)
    if case == "dense":
        return [rng.randint(-size // 4, size // 4) for _ in range(size)]
    if case == "int32":
        return [
            rng.randint(-(1 << 31), (1 << 31) - 1)
            for _ in range(size)
        ]
    if case == "int64":
        return [
            rng.randint(-(1 << 63), (1 << 63) - 1)
            for _ in range(size)
        ]
    if case == "heavy-duplicates":
        return [rng.randrange(97) - 48 for _ in range(size)]
    raise ValueError(f"unknown exact case: {case}")


def create_generic_values(size, case, seed):
    rng = random.Random(seed)
    if case == "huge-int":
        return [
            rng.randint(-(1 << 40), (1 << 40)) * (1 << 80)
            + rng.randrange(1 << 40)
            for _ in range(size)
        ]
    if case == "string":
        return [
            f"{rng.getrandbits(128):032x}"
            for _ in range(size)
        ]
    if case == "tuple":
        return [
            (rng.randrange(1_001), rng.getrandbits(63))
            for _ in range(size)
        ]
    if case == "finite-float":
        return [rng.uniform(-1.0e12, 1.0e12) for _ in range(size)]
    raise ValueError(f"unknown generic case: {case}")


def create_records(values):
    return [(value,) for value in values]


def run_algorithm(algorithm, records, k, largest):
    if algorithm == HEAPQ:
        function = heapq.nlargest if largest else heapq.nsmallest
        return function(k, records, key=KEY)
    if algorithm == STRICT:
        return _bielsort._topk_by_int64_key_prototype(
            records,
            k,
            KEY,
            largest,
        )
    if algorithm == ADAPTIVE:
        return _bielsort._topk_by_key_prototype(
            records,
            k,
            KEY,
            largest,
        )
    raise ValueError(f"unknown algorithm: {algorithm}")


def ensure_identity(result, expected, algorithm):
    if len(result) != len(expected) or not all(
        actual is wanted for actual, wanted in zip(result, expected)
    ):
        raise AssertionError(
            f"incorrect, unstable, or copied result from {algorithm}"
        )


def measure(algorithms, records, k, largest, expected, repetitions):
    samples = {algorithm: [] for algorithm in algorithms}
    for repetition in range(repetitions):
        for algorithm in rotate(algorithms, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(
                    algorithm,
                    records,
                    k,
                    largest,
                )
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_identity(result, expected, algorithm)
            samples[algorithm].append(elapsed)
            del result
    gc.collect()
    return samples


def execute_exact(size, ks, cases, directions, repetitions):
    rows = []
    print("EXACT INT64 REGRESSION (median; higher ratios favor adaptive)")
    print(
        f"{'n':>10}  {'k':>7}  {'case':<17}  {'direction':<8}"
        f"  {'heapq':>10}  {'strict':>10}  {'adaptive':>10}"
        f"  {'vs heapq':>9}  {'vs strict':>9}"
    )
    print("-" * 114)
    for case_index, case in enumerate(cases):
        records = create_records(
            create_exact_values(size, case, 93_000 + case_index)
        )
        expected_by_direction = {
            direction: sorted(
                records,
                key=KEY,
                reverse=direction == "largest",
            )
            for direction in directions
        }
        for k in ks:
            effective_k = min(k, size)
            for direction in directions:
                largest = direction == "largest"
                expected = expected_by_direction[direction][:effective_k]
                samples = measure(
                    EXACT_ALGORITHMS,
                    records,
                    effective_k,
                    largest,
                    expected,
                    repetitions,
                )
                medians = {
                    algorithm: statistics.median(values)
                    for algorithm, values in samples.items()
                }
                row = {
                    "size": size,
                    "k": effective_k,
                    "case": case,
                    "direction": direction,
                    "medians_s": medians,
                    "samples_s": samples,
                    "adaptive_speedup_over_heapq": (
                        medians[HEAPQ] / medians[ADAPTIVE]
                    ),
                    "adaptive_speedup_over_strict": (
                        medians[STRICT] / medians[ADAPTIVE]
                    ),
                }
                rows.append(row)
                print(
                    f"{size:>10,}  {effective_k:>7,}  {case:<17}"
                    f"  {direction:<8}  {medians[HEAPQ]:>9.6f}s"
                    f"  {medians[STRICT]:>9.6f}s"
                    f"  {medians[ADAPTIVE]:>9.6f}s"
                    f"  {row['adaptive_speedup_over_heapq']:>8.2f}x"
                    f"  {row['adaptive_speedup_over_strict']:>8.2f}x"
                )
        del expected_by_direction, records
        gc.collect()
    return rows


def execute_generic(size, ks, cases, directions, repetitions):
    rows = []
    print("\nGENERIC KEY FALLBACK (median; higher ratio favors adaptive)")
    print(
        f"{'n':>10}  {'k':>7}  {'case':<17}  {'direction':<8}"
        f"  {'heapq':>10}  {'adaptive':>10}  {'vs heapq':>9}"
    )
    print("-" * 88)
    for case_index, case in enumerate(cases):
        records = create_records(
            create_generic_values(size, case, 94_000 + case_index)
        )
        expected_by_direction = {
            direction: sorted(
                records,
                key=KEY,
                reverse=direction == "largest",
            )
            for direction in directions
        }
        for k in ks:
            effective_k = min(k, size)
            for direction in directions:
                largest = direction == "largest"
                expected = expected_by_direction[direction][:effective_k]
                samples = measure(
                    GENERIC_ALGORITHMS,
                    records,
                    effective_k,
                    largest,
                    expected,
                    repetitions,
                )
                medians = {
                    algorithm: statistics.median(values)
                    for algorithm, values in samples.items()
                }
                row = {
                    "size": size,
                    "k": effective_k,
                    "case": case,
                    "direction": direction,
                    "medians_s": medians,
                    "samples_s": samples,
                    "adaptive_speedup_over_heapq": (
                        medians[HEAPQ] / medians[ADAPTIVE]
                    ),
                }
                rows.append(row)
                print(
                    f"{size:>10,}  {effective_k:>7,}  {case:<17}"
                    f"  {direction:<8}  {medians[HEAPQ]:>9.6f}s"
                    f"  {medians[ADAPTIVE]:>9.6f}s"
                    f"  {row['adaptive_speedup_over_heapq']:>8.2f}x"
                )
        del expected_by_direction, records
        gc.collect()
    return rows


def evaluate_gate(exact_rows, generic_rows, exact_size, generic_size):
    exact_targets = [row for row in exact_rows if row["size"] == exact_size]
    generic_targets = [
        row for row in generic_rows if row["size"] == generic_size
    ]
    exact_fast = [
        row for row in exact_targets
        if row["adaptive_speedup_over_heapq"] >= 1.20
    ]
    exact_regressions = [
        row for row in exact_targets
        if row["adaptive_speedup_over_strict"] < (1.0 / 1.15)
    ]
    generic_regressions = [
        row for row in generic_targets
        if row["adaptive_speedup_over_heapq"] < (1.0 / 1.15)
    ]
    exact_shape = (
        exact_size == 1_000_000
        and len(exact_targets) == 24
        and {row["case"] for row in exact_targets} == set(EXACT_CASES)
        and {row["direction"] for row in exact_targets} == set(DIRECTIONS)
        and {row["k"] for row in exact_targets} == {10, 100, 1_000}
    )
    generic_shape = (
        generic_size == 100_000
        and len(generic_targets) == 24
        and {row["case"] for row in generic_targets} == set(GENERIC_CASES)
        and {row["direction"] for row in generic_targets} == set(DIRECTIONS)
        and {row["k"] for row in generic_targets} == {10, 100, 1_000}
    )
    return {
        "passed": (
            exact_shape
            and generic_shape
            and len(exact_fast) >= 18
            and not exact_regressions
            and not generic_regressions
        ),
        "exact_canonical_shape_present": exact_shape,
        "generic_canonical_shape_present": generic_shape,
        "exact_cases_at_least_1_20x_over_heapq": len(exact_fast),
        "exact_target_case_count": len(exact_targets),
        "generic_target_case_count": len(generic_targets),
        "exact_regressions_over_15_percent_vs_strict": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "speedup": row["adaptive_speedup_over_strict"],
            }
            for row in exact_regressions
        ],
        "generic_regressions_over_15_percent_vs_heapq": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "speedup": row["adaptive_speedup_over_heapq"],
            }
            for row in generic_regressions
        ],
        "memory_contract": {
            "retained_key_objects": "O(k)",
            "native_entry_buffers": "at most 2 * k",
            "key_array_for_reusable_input": False,
        },
        "note": (
            "This private gate does not approve top_k, a version bump, or "
            "a release."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-size", type=int, default=1_000_000)
    parser.add_argument("--generic-size", type=int, default=100_000)
    parser.add_argument(
        "-k",
        "--ks",
        type=int,
        nargs="+",
        default=[10, 100, 1_000],
    )
    parser.add_argument("-r", "--repetitions", type=int, default=7)
    parser.add_argument(
        "--exact-cases",
        nargs="+",
        choices=EXACT_CASES,
        default=list(EXACT_CASES),
    )
    parser.add_argument(
        "--generic-cases",
        nargs="+",
        choices=GENERIC_CASES,
        default=list(GENERIC_CASES),
    )
    parser.add_argument(
        "--directions",
        nargs="+",
        choices=DIRECTIONS,
        default=list(DIRECTIONS),
    )
    parser.add_argument("--json-output", type=Path)
    arguments = parser.parse_args()
    if (
        arguments.exact_size < 0
        or arguments.generic_size < 0
        or arguments.repetitions < 1
        or any(k < 0 for k in arguments.ks)
    ):
        raise SystemExit("sizes and k must be non-negative; repetitions >= 1")

    exact_rows = execute_exact(
        arguments.exact_size,
        arguments.ks,
        arguments.exact_cases,
        arguments.directions,
        arguments.repetitions,
    )
    generic_rows = execute_generic(
        arguments.generic_size,
        arguments.ks,
        arguments.generic_cases,
        arguments.directions,
        arguments.repetitions,
    )
    gate = evaluate_gate(
        exact_rows,
        generic_rows,
        arguments.exact_size,
        arguments.generic_size,
    )
    print(
        "\nPRIVATE ADAPTIVE KEYED TOP-K GATE: "
        + ("PASS" if gate["passed"] else "NOT YET PASSED")
    )

    if arguments.json_output:
        payload = {
            "benchmark": "private-adaptive-keyed-topk",
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
                "compiler": platform.python_compiler(),
            },
            "configuration": {
                "exact_size": arguments.exact_size,
                "generic_size": arguments.generic_size,
                "ks": arguments.ks,
                "exact_cases": arguments.exact_cases,
                "generic_cases": arguments.generic_cases,
                "directions": arguments.directions,
                "repetitions": arguments.repetitions,
                "key": "operator.itemgetter(0)",
            },
            "exact_int64_regression": exact_rows,
            "generic_fallback": generic_rows,
            "decision_gate": gate,
        }
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Raw JSON written to {arguments.json_output}")


if __name__ == "__main__":
    main()
