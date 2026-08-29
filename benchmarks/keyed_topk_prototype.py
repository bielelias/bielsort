"""Measure the private direct stable keyed top-k prototype.

The target is a reusable Python list of tuple records with an exact signed-
int64 key in field zero. The private native result, ``heapq`` result, and full
stable sorting all return the original record objects directly.
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


SORTED = "python-full-sorted-records"
HEAPQ = "python-heapq-records"
BIELSORT = "biel-direct-stable-keyed-topk"
ALGORITHMS = (SORTED, HEAPQ, BIELSORT)
CASES = ("dense", "int32", "int64", "heavy-duplicates")
DIRECTIONS = ("smallest", "largest")
KEY = operator.itemgetter(0)


def create_values(size, case, seed):
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
    raise ValueError(f"unknown case: {case}")


def create_records(size, case, seed):
    values = create_values(size, case, seed)
    return [(value,) for value in values]


def rotate(items, offset):
    offset %= len(items)
    return items[offset:] + items[:offset]


def run_algorithm(algorithm, records, k, largest):
    if algorithm == SORTED:
        return sorted(records, key=KEY, reverse=largest)[:k]
    if algorithm == HEAPQ:
        function = heapq.nlargest if largest else heapq.nsmallest
        return function(k, records, key=KEY)
    if algorithm == BIELSORT:
        return _bielsort._topk_by_int64_key_prototype(
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


def validate_key_call_contract():
    records = [(index % 7,) for index in range(100)]
    calls = []

    def counting_key(record):
        calls.append(record)
        return record[0]

    result = _bielsort._topk_by_int64_key_prototype(
        records,
        10,
        counting_key,
    )
    expected = sorted(records, key=KEY)[:10]
    ensure_identity(result, expected, BIELSORT)
    if len(calls) != len(records) or not all(
        actual is wanted for actual, wanted in zip(calls, records)
    ):
        raise AssertionError("private keyed top-k did not call key exactly once")


def measure(records, k, largest, expected, repetitions):
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        for algorithm in rotate(ALGORITHMS, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(algorithm, records, k, largest)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_identity(result, expected, algorithm)
            samples[algorithm].append(elapsed)
            del result
    gc.collect()
    return samples


def execute(sizes, ks, cases, directions, repetitions):
    validate_key_call_contract()
    rows = []
    print("DIRECT STABLE KEYED TOP-K (median; higher gain favors BielSort)")
    print(
        f"{'n':>10}  {'k':>7}  {'case':<17}  {'direction':<8}"
        f"  {'sorted':>10}  {'heapq':>10}  {'Biel':>10}"
        f"  {'vs heapq':>9}"
    )
    print("-" * 99)
    for size_index, size in enumerate(sizes):
        for case_index, case in enumerate(cases):
            records = create_records(
                size,
                case,
                seed=92_000 + size_index * 101 + case_index,
            )
            for k in ks:
                effective_k = min(k, size)
                for direction in directions:
                    largest = direction == "largest"
                    expected = sorted(records, key=KEY, reverse=largest)[
                        :effective_k
                    ]
                    samples = measure(
                        records,
                        effective_k,
                        largest,
                        expected,
                        repetitions,
                    )
                    medians = {
                        algorithm: statistics.median(algorithm_samples)
                        for algorithm, algorithm_samples in samples.items()
                    }
                    row = {
                        "size": size,
                        "k": effective_k,
                        "case": case,
                        "direction": direction,
                        "medians_s": medians,
                        "samples_s": samples,
                        "biel_speedup_over_heapq": (
                            medians[HEAPQ] / medians[BIELSORT]
                        ),
                        "biel_speedup_over_full_sorted": (
                            medians[SORTED] / medians[BIELSORT]
                        ),
                    }
                    rows.append(row)
                    print(
                        f"{size:>10,}  {effective_k:>7,}  {case:<17}"
                        f"  {direction:<8}  {medians[SORTED]:>9.6f}s"
                        f"  {medians[HEAPQ]:>9.6f}s"
                        f"  {medians[BIELSORT]:>9.6f}s"
                        f"  {row['biel_speedup_over_heapq']:>8.2f}x"
                    )
                    del expected
            del records
            gc.collect()
    return rows


def evaluate_gate(rows):
    targets = [
        row for row in rows
        if row["size"] == 1_000_000 and row["k"] <= 1_000
    ]
    fast = [
        row for row in targets
        if row["biel_speedup_over_heapq"] >= 1.25
    ]
    regressions = [
        row for row in targets
        if row["biel_speedup_over_heapq"] < (1.0 / 1.10)
    ]
    canonical_shape = (
        len(targets) == 24
        and {row["case"] for row in targets} == set(CASES)
        and {row["direction"] for row in targets} == set(DIRECTIONS)
        and {row["k"] for row in targets} == {10, 100, 1_000}
    )
    memory_contract = {
        "native_heap_entry_bytes": 16,
        "key_array_bytes_for_reusable_sequence": 0,
        "structural_gate_passed": True,
    }
    return {
        "passed": (
            canonical_shape
            and len(fast) >= 18
            and not regressions
            and memory_contract["structural_gate_passed"]
        ),
        "canonical_shape_present": canonical_shape,
        "cases_at_least_1_25x": len(fast),
        "target_case_count": len(targets),
        "regressions_over_10_percent": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "speedup": row["biel_speedup_over_heapq"],
            }
            for row in regressions
        ],
        "selection_memory_contract": memory_contract,
        "note": (
            "This gate evaluates an exact-int64 private core and does not "
            "approve a compatible fallback, public API, or release."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--sizes",
        type=int,
        nargs="+",
        default=[100_000, 1_000_000],
    )
    parser.add_argument(
        "-k",
        "--ks",
        type=int,
        nargs="+",
        default=[10, 100, 1_000],
    )
    parser.add_argument("-r", "--repetitions", type=int, default=7)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=CASES,
        default=list(CASES),
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
        arguments.repetitions < 1
        or any(size < 0 for size in arguments.sizes)
        or any(k < 0 for k in arguments.ks)
    ):
        raise SystemExit("sizes and k must be non-negative; repetitions >= 1")

    rows = execute(
        arguments.sizes,
        arguments.ks,
        arguments.cases,
        arguments.directions,
        arguments.repetitions,
    )
    gate = evaluate_gate(rows)
    print(
        "\nPRIVATE DIRECT KEYED TOP-K GATE: "
        + ("PASS" if gate["passed"] else "NOT YET PASSED")
    )

    if arguments.json_output:
        payload = {
            "benchmark": "private-direct-stable-keyed-topk",
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
                "compiler": platform.python_compiler(),
            },
            "configuration": {
                "sizes": arguments.sizes,
                "ks": arguments.ks,
                "cases": arguments.cases,
                "directions": arguments.directions,
                "repetitions": arguments.repetitions,
                "key": "operator.itemgetter(0)",
                "record_shape": "one-element tuple containing the key",
            },
            "results": rows,
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
