"""Measure private fused application of one permutation to parallel lists.

The comparison is deliberately narrow:

* repeated-native calls ``order.apply(sequence)`` once per sequence;
* fused-native calls ``order.apply_many(*sequences)`` once.

Both paths receive the same already-built compact permutation and produce the
same tuple of new Python lists. Construction is outside the timed region.
"""

import argparse
import gc
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

from bielsort_native import _bielsort


REPEATED = "repeated-native-apply"
FUSED = "fused-native-apply-many"
ALGORITHMS = (REPEATED, FUSED)
CASES = (
    "topk-10",
    "topk-100",
    "topk-1000",
    "full-random",
    "full-identity",
)
SEQUENCE_COUNTS = (2, 3, 5)
TARGET_APPLIED_ITEMS_PER_SAMPLE = 500_000
MAX_BATCH_ITERATIONS = 20_000


def rotate(items, offset):
    offset %= len(items)
    return items[offset:] + items[:offset]


def create_values(size, case, seed):
    if case == "full-identity":
        return list(range(size))
    rng = random.Random(seed)
    return [
        rng.randint(-(1 << 31), (1 << 31) - 1)
        for _ in range(size)
    ]


def create_order(values, case):
    if case.startswith("topk-"):
        k = min(int(case.removeprefix("topk-")), len(values))
        return _bielsort._topk_int64_prototype(values, k)
    return _bielsort._argsort_int64_prototype(values)


def create_parallel_sequences(values, sequence_count):
    markers = [object() for _ in range(sequence_count - 1)]
    return (
        values,
        *([marker] * len(values) for marker in markers),
    )


def assert_identical_results(order, sequences):
    repeated = tuple(order.apply(sequence) for sequence in sequences)
    fused = order.apply_many(*sequences)
    if len(repeated) != len(fused):
        raise AssertionError("Incorrect apply_many result count")
    for repeated_part, fused_part in zip(repeated, fused):
        if len(repeated_part) != len(fused_part):
            raise AssertionError("Incorrect apply_many result length")
        if not all(
            repeated_item is fused_item
            for repeated_item, fused_item in zip(repeated_part, fused_part)
        ):
            raise AssertionError("apply_many did not preserve exact identity")
    del repeated, fused


def batch_iterations(order_length, sequence_count):
    applied_items = max(1, order_length * sequence_count)
    return min(
        MAX_BATCH_ITERATIONS,
        max(1, TARGET_APPLIED_ITEMS_PER_SAMPLE // applied_items),
    )


def run_batch(algorithm, order, sequences, iterations):
    for _ in range(iterations):
        if algorithm == REPEATED:
            result = tuple(order.apply(sequence) for sequence in sequences)
        elif algorithm == FUSED:
            result = order.apply_many(*sequences)
        else:  # pragma: no cover - internal benchmark invariant
            raise ValueError(f"Unknown algorithm: {algorithm}")
        del result


def measure(order, sequences, repetitions):
    assert_identical_results(order, sequences)
    iterations = batch_iterations(len(order), len(sequences))
    samples = {algorithm: [] for algorithm in ALGORITHMS}
    for repetition in range(repetitions):
        for algorithm in rotate(list(ALGORITHMS), repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter_ns()
                run_batch(algorithm, order, sequences, iterations)
                elapsed = time.perf_counter_ns() - started
            finally:
                gc.enable()
            samples[algorithm].append(elapsed / iterations / 1_000_000_000)
    gc.collect()
    return samples, iterations


def execute(sizes, cases, sequence_counts, repetitions):
    rows = []
    print(
        "PRIVATE PERMUTATION APPLY-MANY "
        "(median per call; higher speedup favors fused)"
    )
    print(
        f"{'n':>10}  {'case':<14}  {'lists':>5}  "
        f"{'repeated':>10}  {'fused':>10}  {'speedup':>8}"
    )
    print("-" * 75)
    for size_index, size in enumerate(sizes):
        for case_index, case in enumerate(cases):
            values = create_values(
                size,
                case,
                seed=91_000 + size_index * 101 + case_index,
            )
            order = create_order(values, case)
            for sequence_count in sequence_counts:
                sequences = create_parallel_sequences(values, sequence_count)
                samples, iterations = measure(
                    order,
                    sequences,
                    repetitions,
                )
                medians = {
                    algorithm: statistics.median(algorithm_samples)
                    for algorithm, algorithm_samples in samples.items()
                }
                speedup = medians[REPEATED] / medians[FUSED]
                row = {
                    "size": size,
                    "case": case,
                    "sequence_count": sequence_count,
                    "permutation_length": len(order),
                    "batch_iterations": iterations,
                    "medians_s": medians,
                    "samples_s": samples,
                    "fused_speedup_over_repeated": speedup,
                }
                rows.append(row)
                print(
                    f"{size:>10,}  {case:<14}  {sequence_count:>5}  "
                    f"{medians[REPEATED]:>9.6f}s  "
                    f"{medians[FUSED]:>9.6f}s  {speedup:>7.2f}x"
                )
                del sequences
            del order, values
            gc.collect()
    return rows


def evaluate_gate(rows):
    targets = [row for row in rows if row["size"] == 1_000_000]
    expected_target_count = len(CASES) * len(SEQUENCE_COUNTS)
    fast = [
        row for row in targets
        if row["fused_speedup_over_repeated"] >= 1.05
    ]
    full_fast = [
        row for row in targets
        if row["case"].startswith("full-")
        and row["fused_speedup_over_repeated"] >= 1.10
    ]
    regressions = [
        row for row in targets
        if row["fused_speedup_over_repeated"] < (1.0 / 1.05)
    ]
    canonical_shape = (
        len(targets) == expected_target_count
        and {row["case"] for row in targets} == set(CASES)
        and {row["sequence_count"] for row in targets}
        == set(SEQUENCE_COUNTS)
    )
    return {
        "passed": (
            canonical_shape
            and len(fast) >= 9
            and len(full_fast) >= 3
            and not regressions
        ),
        "canonical_shape_present": canonical_shape,
        "target_case_count": len(targets),
        "cases_at_least_1_05x": len(fast),
        "full_cases_at_least_1_10x": len(full_fast),
        "regressions_over_5_percent": [
            {
                "case": row["case"],
                "sequence_count": row["sequence_count"],
                "speedup": row["fused_speedup_over_repeated"],
            }
            for row in regressions
        ],
        "note": (
            "This gate evaluates a private method and does not approve a "
            "public API or release."
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
        "-r",
        "--repetitions",
        type=int,
        default=9,
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=CASES,
        default=list(CASES),
    )
    parser.add_argument(
        "--sequence-counts",
        type=int,
        nargs="+",
        default=list(SEQUENCE_COUNTS),
    )
    parser.add_argument("--json-output", type=Path)
    arguments = parser.parse_args()
    if (
        arguments.repetitions < 1
        or any(size < 0 for size in arguments.sizes)
        or any(count < 1 for count in arguments.sequence_counts)
    ):
        raise SystemExit(
            "sizes must be non-negative; repetitions and sequence counts >= 1"
        )

    rows = execute(
        arguments.sizes,
        arguments.cases,
        arguments.sequence_counts,
        arguments.repetitions,
    )
    gate = evaluate_gate(rows)
    print(
        "\nPRIVATE APPLY-MANY GATE: "
        + ("PASS" if gate["passed"] else "NOT YET PASSED")
    )

    if arguments.json_output:
        payload = {
            "benchmark": "private-permutation-apply-many",
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
                "compiler": platform.python_compiler(),
            },
            "configuration": {
                "sizes": arguments.sizes,
                "cases": arguments.cases,
                "sequence_counts": arguments.sequence_counts,
                "repetitions": arguments.repetitions,
                "target_applied_items_per_sample": (
                    TARGET_APPLIED_ITEMS_PER_SAMPLE
                ),
                "max_batch_iterations": MAX_BATCH_ITERATIONS,
            },
            "application": rows,
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
