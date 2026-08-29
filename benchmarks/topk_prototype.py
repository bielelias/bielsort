"""Measure the private stable compact top-k prototype.

The primary comparison returns reusable stable indices from the same Python
list. ``heapq`` is the strongest standard-library baseline for small ``k``;
full ``sorted`` is retained to show the avoided whole-input ordering cost.
The reuse scenario constructs one order and applies it to three parallel
Python sequences.
"""

import argparse
import gc
import heapq
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

from bielsort_native import _bielsort


SORTED = "python-full-sorted-indices"
HEAPQ = "python-heapq-indices"
BIELSORT = "biel-compact-stable-topk"
ALGORITHMS = (SORTED, HEAPQ, BIELSORT)
REUSE_ALGORITHMS = (HEAPQ, BIELSORT)
CASES = ("dense", "int32", "int64", "heavy-duplicates")
DIRECTIONS = ("smallest", "largest")


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


def expected_topk(values, k, largest):
    return sorted(
        range(len(values)),
        key=values.__getitem__,
        reverse=largest,
    )[:k]


def run_algorithm(algorithm, values, k, largest):
    indices = range(len(values))
    if algorithm == SORTED:
        return sorted(
            indices,
            key=values.__getitem__,
            reverse=largest,
        )[:k]
    if algorithm == HEAPQ:
        function = heapq.nlargest if largest else heapq.nsmallest
        return function(k, indices, key=values.__getitem__)
    if algorithm == BIELSORT:
        return _bielsort._topk_int64_prototype(values, k, largest)
    raise ValueError(f"unknown algorithm: {algorithm}")


def rotate(items, offset):
    offset %= len(items)
    return items[offset:] + items[:offset]


def ensure_order(result, expected, algorithm):
    if list(result) != expected:
        raise AssertionError(f"incorrect or unstable result from {algorithm}")


def measure_construction(values, k, largest, expected, repetitions):
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        for algorithm in rotate(ALGORITHMS, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(algorithm, values, k, largest)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_order(result, expected, algorithm)
            samples[algorithm].append(elapsed)
            del result
    gc.collect()
    return samples


def create_parallel_sequences(values):
    size = len(values)
    return (
        values,
        list(range(size)),
        [index % 97 for index in range(size)],
    )


def apply_python_order(order, sequence):
    return [sequence[index] for index in order]


def run_reuse(algorithm, values, sequences, k, largest):
    order = run_algorithm(algorithm, values, k, largest)
    if algorithm == BIELSORT:
        results = [order.apply(sequence) for sequence in sequences]
    else:
        results = [
            apply_python_order(order, sequence)
            for sequence in sequences
        ]
    return order, results


def measure_reuse(values, k, largest, expected_order, repetitions):
    sequences = create_parallel_sequences(values)
    expected_results = [
        apply_python_order(expected_order, sequence)
        for sequence in sequences
    ]
    samples = {algorithm: [] for algorithm in REUSE_ALGORITHMS}
    for repetition in range(repetitions):
        for algorithm in rotate(REUSE_ALGORITHMS, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                order, results = run_reuse(
                    algorithm,
                    values,
                    sequences,
                    k,
                    largest,
                )
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_order(order, expected_order, algorithm)
            if results != expected_results:
                raise AssertionError(
                    f"incorrect parallel-sequence result from {algorithm}"
                )
            samples[algorithm].append(elapsed)
            del order, results
    del expected_results, sequences
    gc.collect()
    return samples


def result_storage(values, k, largest):
    python_result = run_algorithm(HEAPQ, values, k, largest)
    biel_result = run_algorithm(BIELSORT, values, k, largest)
    storage = {
        "python": {
            "list_shallow_bytes": sys.getsizeof(python_result),
            "including_index_objects_bytes": (
                sys.getsizeof(python_result)
                + sum(sys.getsizeof(index) for index in python_result)
            ),
        },
        "biel": {
            "buffer_payload_bytes": memoryview(biel_result).nbytes,
            "itemsize": memoryview(biel_result).itemsize,
        },
    }
    del python_result, biel_result
    return storage


def execute(sizes, ks, cases, directions, repetitions):
    construction_rows = []
    reuse_rows = []
    print("STABLE TOP-K CONSTRUCTION (median; higher gain favors BielSort)")
    print(
        f"{'n':>10}  {'k':>7}  {'case':<17}  {'direction':<8}"
        f"  {'sorted':>10}  {'heapq':>10}  {'Biel':>10}"
        f"  {'vs heapq':>9}"
    )
    print("-" * 99)
    for size in sizes:
        for case_index, case in enumerate(cases):
            values = create_values(size, case, 80_000 + size + case_index)
            for k in ks:
                effective_k = min(k, size)
                for direction in directions:
                    largest = direction == "largest"
                    expected = expected_topk(values, effective_k, largest)
                    samples = measure_construction(
                        values,
                        effective_k,
                        largest,
                        expected,
                        repetitions,
                    )
                    medians = {
                        algorithm: statistics.median(algorithm_samples)
                        for algorithm, algorithm_samples in samples.items()
                    }
                    biel_result, strategy = (
                        _bielsort._topk_int64_prototype_with_strategy(
                            values,
                            effective_k,
                            largest,
                        )
                    )
                    ensure_order(biel_result, expected, BIELSORT)
                    row = {
                        "size": size,
                        "k": effective_k,
                        "case": case,
                        "direction": direction,
                        "strategy": strategy,
                        "medians_s": medians,
                        "biel_speedup_over_heapq": (
                            medians[HEAPQ] / medians[BIELSORT]
                        ),
                        "biel_speedup_over_full_sorted": (
                            medians[SORTED] / medians[BIELSORT]
                        ),
                        "samples_s": samples,
                        "result_storage": result_storage(
                            values,
                            effective_k,
                            largest,
                        ),
                    }
                    construction_rows.append(row)
                    print(
                        f"{size:>10,}  {effective_k:>7,}  {case:<17}"
                        f"  {direction:<8}  {medians[SORTED]:>9.6f}s"
                        f"  {medians[HEAPQ]:>9.6f}s"
                        f"  {medians[BIELSORT]:>9.6f}s"
                        f"  {row['biel_speedup_over_heapq']:>8.2f}x"
                    )

                    reuse_samples = measure_reuse(
                        values,
                        effective_k,
                        largest,
                        expected,
                        repetitions,
                    )
                    reuse_medians = {
                        algorithm: statistics.median(algorithm_samples)
                        for algorithm, algorithm_samples
                        in reuse_samples.items()
                    }
                    reuse_rows.append(
                        {
                            "size": size,
                            "k": effective_k,
                            "case": case,
                            "direction": direction,
                            "sequence_count": 3,
                            "medians_s": reuse_medians,
                            "biel_speedup_over_heapq": (
                                reuse_medians[HEAPQ]
                                / reuse_medians[BIELSORT]
                            ),
                            "samples_s": reuse_samples,
                        }
                    )
                    del biel_result, expected
            del values
            gc.collect()
    return construction_rows, reuse_rows


def evaluate_gate(construction_rows, reuse_rows):
    target_construction = [
        row for row in construction_rows
        if row["size"] == 1_000_000 and row["k"] <= 1_000
    ]
    target_reuse = [
        row for row in reuse_rows
        if row["size"] == 1_000_000 and row["k"] <= 1_000
    ]
    fast_construction = [
        row for row in target_construction
        if row["biel_speedup_over_heapq"] >= 1.25
    ]
    fast_reuse = [
        row for row in target_reuse
        if row["biel_speedup_over_heapq"] >= 1.25
    ]
    construction_regressions = [
        row for row in target_construction
        if row["biel_speedup_over_heapq"] < (1.0 / 1.10)
    ]
    reuse_regressions = [
        row for row in target_reuse
        if row["biel_speedup_over_heapq"] < (1.0 / 1.10)
    ]
    storage_passed = all(
        row["result_storage"]["biel"]["buffer_payload_bytes"]
        <= row["result_storage"]["python"]["list_shallow_bytes"] / 2
        for row in target_construction
    )
    canonical_shape = (
        len(target_construction) >= 24
        and len(target_reuse) >= 24
    )
    return {
        "passed": (
            canonical_shape
            and len(fast_construction) >= 18
            and len(fast_reuse) >= 18
            and not construction_regressions
            and not reuse_regressions
            and storage_passed
        ),
        "canonical_shape_present": canonical_shape,
        "construction_cases_at_least_1_25x": len(fast_construction),
        "reuse_cases_at_least_1_25x": len(fast_reuse),
        "target_case_count": len(target_construction),
        "construction_regressions_over_10_percent": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "speedup": row["biel_speedup_over_heapq"],
            }
            for row in construction_regressions
        ],
        "reuse_regressions_over_10_percent": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "speedup": row["biel_speedup_over_heapq"],
            }
            for row in reuse_regressions
        ],
        "compact_storage_passed": storage_passed,
        "note": (
            "This gate evaluates a private prototype and does not approve a "
            "public API or release."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--sizes", type=int, nargs="+", default=[100_000, 1_000_000])
    parser.add_argument("-k", "--ks", type=int, nargs="+", default=[10, 100, 1_000])
    parser.add_argument("-r", "--repetitions", type=int, default=7)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
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

    construction_rows, reuse_rows = execute(
        arguments.sizes,
        arguments.ks,
        arguments.cases,
        arguments.directions,
        arguments.repetitions,
    )
    gate = evaluate_gate(construction_rows, reuse_rows)
    print("\nPRIVATE TOP-K GATE: " + ("PASS" if gate["passed"] else "NOT YET PASSED"))

    if arguments.json_output:
        payload = {
            "benchmark": "private-stable-compact-topk",
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
            },
            "construction": construction_rows,
            "build_and_apply_three": reuse_rows,
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
