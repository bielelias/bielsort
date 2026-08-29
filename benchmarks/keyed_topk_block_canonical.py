"""Run the complete block-timed adaptive keyed top-k decision protocol.

This benchmark preserves the earlier failed stage-two result. It repeats all
48 cases with paired blocks, rotated algorithm order, and multiple calls per
block so that a new decision does not depend on isolated timing samples.
"""

import argparse
import gc
import json
import platform
import statistics
import sys
import time
from pathlib import Path

from benchmarks.keyed_topk_fallback import (
    ADAPTIVE,
    DIRECTIONS,
    EXACT_ALGORITHMS,
    EXACT_CASES,
    GENERIC_ALGORITHMS,
    GENERIC_CASES,
    HEAPQ,
    KEY,
    STRICT,
    create_exact_values,
    create_generic_values,
    create_records,
    ensure_identity,
    rotate,
    run_algorithm,
)


PROTOCOL_COMMIT = "7fc9609"
SELECTION_CODE_COMMIT = "fdc9bb5"
EXACT_MINIMUM_HEAPQ_WINS = 18
EXACT_HEAPQ_TARGET = 1.20
REGRESSION_FLOOR = 0.87


def median_absolute_deviation(values):
    """Return the unscaled median absolute deviation for timing diagnostics."""
    center = statistics.median(values)
    return statistics.median([abs(value - center) for value in values])


def warm_up(algorithms, records, k, largest, expected):
    """Run one untimed, identity-checked call for each algorithm."""
    for algorithm in algorithms:
        result = run_algorithm(algorithm, records, k, largest)
        ensure_identity(result, expected, algorithm)
        del result
    gc.collect()


def measure_blocks(
    algorithms,
    records,
    k,
    largest,
    expected,
    blocks,
    calls_per_block,
):
    """Collect per-call averages in rotated paired timing blocks."""
    warm_up(algorithms, records, k, largest, expected)
    samples = {algorithm: [] for algorithm in algorithms}
    for block in range(blocks):
        for algorithm in rotate(algorithms, block):
            gc.collect()
            elapsed = 0.0
            gc.disable()
            try:
                for _ in range(calls_per_block):
                    started = time.perf_counter()
                    result = run_algorithm(
                        algorithm,
                        records,
                        k,
                        largest,
                    )
                    elapsed += time.perf_counter() - started
                    ensure_identity(result, expected, algorithm)
                    del result
            finally:
                gc.enable()
            samples[algorithm].append(elapsed / calls_per_block)
    gc.collect()
    return samples


def summarize_case(
    records,
    expected,
    algorithms,
    comparators,
    k,
    largest,
    blocks,
    calls_per_block,
):
    """Measure one case and calculate paired primary statistics."""
    samples = measure_blocks(
        algorithms,
        records,
        k,
        largest,
        expected,
        blocks,
        calls_per_block,
    )
    medians = {
        algorithm: statistics.median(values)
        for algorithm, values in samples.items()
    }
    deviations = {
        algorithm: median_absolute_deviation(values)
        for algorithm, values in samples.items()
    }
    paired = {
        comparator: [
            comparator_sample / adaptive_sample
            for comparator_sample, adaptive_sample in zip(
                samples[comparator],
                samples[ADAPTIVE],
            )
        ]
        for comparator in comparators
    }
    return {
        "medians_s": medians,
        "median_absolute_deviations_s": deviations,
        "samples_s": samples,
        "paired_speedups": paired,
        "median_paired_speedups": {
            comparator: statistics.median(values)
            for comparator, values in paired.items()
        },
        "ratios_of_medians": {
            comparator: medians[comparator] / medians[ADAPTIVE]
            for comparator in comparators
        },
    }


def execute_exact(size, ks, cases, directions, blocks, calls_per_block):
    """Execute all exact-int64 regression cases."""
    rows = []
    print("EXACT INT64 BLOCK PROTOCOL (median paired ratios)")
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
                timing = summarize_case(
                    records,
                    expected_by_direction[direction][:effective_k],
                    EXACT_ALGORITHMS,
                    (HEAPQ, STRICT),
                    effective_k,
                    largest,
                    blocks,
                    calls_per_block,
                )
                row = {
                    "size": size,
                    "k": effective_k,
                    "case": case,
                    "direction": direction,
                    **timing,
                }
                rows.append(row)
                medians = row["medians_s"]
                paired = row["median_paired_speedups"]
                print(
                    f"{size:>10,}  {effective_k:>7,}  {case:<17}"
                    f"  {direction:<8}  {medians[HEAPQ]:>9.6f}s"
                    f"  {medians[STRICT]:>9.6f}s"
                    f"  {medians[ADAPTIVE]:>9.6f}s"
                    f"  {paired[HEAPQ]:>8.2f}x"
                    f"  {paired[STRICT]:>8.2f}x"
                )
        del expected_by_direction, records
        gc.collect()
    return rows


def execute_generic(size, ks, cases, directions, blocks, calls_per_block):
    """Execute all generic-key comparison cases."""
    rows = []
    print("\nGENERIC KEY BLOCK PROTOCOL (median paired ratios)")
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
                timing = summarize_case(
                    records,
                    expected_by_direction[direction][:effective_k],
                    GENERIC_ALGORITHMS,
                    (HEAPQ,),
                    effective_k,
                    largest,
                    blocks,
                    calls_per_block,
                )
                row = {
                    "size": size,
                    "k": effective_k,
                    "case": case,
                    "direction": direction,
                    **timing,
                }
                rows.append(row)
                medians = row["medians_s"]
                paired = row["median_paired_speedups"]
                print(
                    f"{size:>10,}  {effective_k:>7,}  {case:<17}"
                    f"  {direction:<8}  {medians[HEAPQ]:>9.6f}s"
                    f"  {medians[ADAPTIVE]:>9.6f}s"
                    f"  {paired[HEAPQ]:>8.2f}x"
                )
        del expected_by_direction, records
        gc.collect()
    return rows


def has_complete_rows(rows, size, cases, ks, directions, algorithms, blocks):
    """Check case uniqueness and retained block samples."""
    expected_cases = {
        (case, k, direction)
        for case in cases
        for k in ks
        for direction in directions
    }
    actual_cases = {
        (row["case"], row["k"], row["direction"])
        for row in rows
        if row["size"] == size
    }
    return (
        len(rows) == len(expected_cases)
        and actual_cases == expected_cases
        and all(
            set(row["samples_s"]) == set(algorithms)
            and all(
                len(row["samples_s"][algorithm]) == blocks
                for algorithm in algorithms
            )
            for row in rows
        )
    )


def evaluate_gate(
    exact_rows,
    generic_rows,
    exact_size,
    generic_size,
    ks,
    exact_cases,
    generic_cases,
    directions,
    blocks,
    calls_per_block,
):
    """Apply only the thresholds fixed in protocol commit 7fc9609."""
    canonical_parameters = (
        exact_size == 1_000_000
        and generic_size == 100_000
        and ks == [10, 100, 1_000]
        and exact_cases == list(EXACT_CASES)
        and generic_cases == list(GENERIC_CASES)
        and directions == list(DIRECTIONS)
        and blocks == 11
        and calls_per_block == 3
    )
    exact_shape = has_complete_rows(
        exact_rows,
        exact_size,
        EXACT_CASES,
        (10, 100, 1_000),
        DIRECTIONS,
        EXACT_ALGORITHMS,
        blocks,
    )
    generic_shape = has_complete_rows(
        generic_rows,
        generic_size,
        GENERIC_CASES,
        (10, 100, 1_000),
        DIRECTIONS,
        GENERIC_ALGORITHMS,
        blocks,
    )
    exact_fast = [
        row
        for row in exact_rows
        if row["median_paired_speedups"][HEAPQ] >= EXACT_HEAPQ_TARGET
    ]
    exact_regressions = [
        row
        for row in exact_rows
        if row["median_paired_speedups"][STRICT] < REGRESSION_FLOOR
    ]
    generic_regressions = [
        row
        for row in generic_rows
        if row["median_paired_speedups"][HEAPQ] < REGRESSION_FLOOR
    ]
    passed = (
        canonical_parameters
        and exact_shape
        and generic_shape
        and len(exact_fast) >= EXACT_MINIMUM_HEAPQ_WINS
        and not exact_regressions
        and not generic_regressions
    )
    return {
        "passed": passed,
        "canonical_parameters_present": canonical_parameters,
        "exact_canonical_shape_present": exact_shape,
        "generic_canonical_shape_present": generic_shape,
        "exact_cases_at_least_1_20x_over_heapq": len(exact_fast),
        "exact_target_case_count": len(exact_rows),
        "generic_target_case_count": len(generic_rows),
        "exact_regressions_below_0_87x_vs_strict": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "median_paired_speedup": (
                    row["median_paired_speedups"][STRICT]
                ),
            }
            for row in exact_regressions
        ],
        "generic_regressions_below_0_87x_vs_heapq": [
            {
                "case": row["case"],
                "k": row["k"],
                "direction": row["direction"],
                "median_paired_speedup": (
                    row["median_paired_speedups"][HEAPQ]
                ),
            }
            for row in generic_regressions
        ],
        "fixed_thresholds": {
            "minimum_exact_cases_at_1_20x_over_heapq": 18,
            "exact_strict_regression_floor": 0.87,
            "generic_heapq_regression_floor": 0.87,
        },
        "memory_contract": {
            "retained_key_objects": "O(k)",
            "native_entry_buffers": "at most 2 * k",
            "key_array_for_reusable_input": False,
        },
        "note": (
            "A pass permits further private callable and memory experiments; "
            "it does not approve a public API, version, tag, or release."
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
    parser.add_argument("--blocks", type=int, default=11)
    parser.add_argument("--calls-per-block", type=int, default=3)
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
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--json-output", type=Path)
    arguments = parser.parse_args()
    if (
        arguments.exact_size < 0
        or arguments.generic_size < 0
        or arguments.blocks < 1
        or arguments.calls_per_block < 1
        or any(k < 0 for k in arguments.ks)
    ):
        raise SystemExit(
            "sizes and k must be non-negative; blocks and calls must be >= 1"
        )

    exact_rows = execute_exact(
        arguments.exact_size,
        arguments.ks,
        arguments.exact_cases,
        arguments.directions,
        arguments.blocks,
        arguments.calls_per_block,
    )
    generic_rows = execute_generic(
        arguments.generic_size,
        arguments.ks,
        arguments.generic_cases,
        arguments.directions,
        arguments.blocks,
        arguments.calls_per_block,
    )
    gate = evaluate_gate(
        exact_rows,
        generic_rows,
        arguments.exact_size,
        arguments.generic_size,
        arguments.ks,
        arguments.exact_cases,
        arguments.generic_cases,
        arguments.directions,
        arguments.blocks,
        arguments.calls_per_block,
    )
    print(
        "\nCOMPLETE BLOCK-TIMED ADAPTIVE KEYED TOP-K GATE: "
        + ("PASS" if gate["passed"] else "NOT PASSED OR NON-CANONICAL")
    )

    if arguments.json_output:
        payload = {
            "benchmark": "private-adaptive-keyed-topk-block-canonical",
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
                "compiler": platform.python_compiler(),
            },
            "provenance": {
                "pre_registered_protocol_commit": PROTOCOL_COMMIT,
                "selection_code_commit": SELECTION_CODE_COMMIT,
                "benchmark_implementation_commit": (
                    arguments.implementation_commit
                ),
                "previous_failed_gate_preserved": True,
            },
            "configuration": {
                "exact_size": arguments.exact_size,
                "generic_size": arguments.generic_size,
                "ks": arguments.ks,
                "exact_cases": arguments.exact_cases,
                "generic_cases": arguments.generic_cases,
                "directions": arguments.directions,
                "blocks": arguments.blocks,
                "calls_per_block": arguments.calls_per_block,
                "warmups_per_algorithm": 1,
                "key": "operator.itemgetter(0)",
                "primary_statistic": "median paired block speedup",
                "spread_statistic": "unscaled median absolute deviation",
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
