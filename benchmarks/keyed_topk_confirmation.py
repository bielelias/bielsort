"""Confirm four adaptive keyed top-k regressions under block timing.

This separately pre-registered experiment changes no selection code and does
not replace the failed stage-two canonical result. It times three calls per
block, pairs comparator/adaptive samples by block, and includes two controls.
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


EXACT_CONFIRMATIONS = (
    ("dense-largest-k10", "dense", 10, True, False, 0),
    ("dense-smallest-k1000", "dense", 1_000, False, False, 0),
    ("int32-largest-k100", "int32", 100, True, False, 1),
    (
        "heavy-duplicates-smallest-k100-control",
        "heavy-duplicates",
        100,
        False,
        True,
        3,
    ),
)
GENERIC_CONFIRMATIONS = (
    ("huge-int-smallest-k100", "huge-int", 100, False, False, 0),
    ("string-smallest-k100-control", "string", 100, False, True, 1),
)


def warm_up(algorithms, records, k, largest, expected):
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
    warm_up(algorithms, records, k, largest, expected)
    samples = {algorithm: [] for algorithm in algorithms}
    for block in range(blocks):
        for algorithm in rotate(algorithms, block):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                for _ in range(calls_per_block):
                    result = run_algorithm(
                        algorithm,
                        records,
                        k,
                        largest,
                    )
                    ensure_identity(result, expected, algorithm)
                    del result
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            samples[algorithm].append(elapsed / calls_per_block)
    gc.collect()
    return samples


def summarize_case(
    name,
    domain,
    k,
    largest,
    control,
    records,
    algorithms,
    comparator,
    blocks,
    calls_per_block,
):
    expected = sorted(records, key=KEY, reverse=largest)[:k]
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
    paired_speedups = [
        comparator_sample / adaptive_sample
        for comparator_sample, adaptive_sample in zip(
            samples[comparator],
            samples[ADAPTIVE],
        )
    ]
    return {
        "name": name,
        "domain": domain,
        "k": k,
        "direction": "largest" if largest else "smallest",
        "control": control,
        "comparator": comparator,
        "medians_s": medians,
        "samples_s": samples,
        "paired_speedups": paired_speedups,
        "median_paired_speedup": statistics.median(paired_speedups),
        "ratio_of_medians": medians[comparator] / medians[ADAPTIVE],
    }


def execute(exact_size, generic_size, blocks, calls_per_block):
    rows = []
    print("ADAPTIVE KEYED TOP-K FAILURE CONFIRMATION")
    print(
        f"{'case':<43}  {'comparator':<22}  "
        f"{'adaptive':>10}  {'paired':>8}  {'control':>7}"
    )
    print("-" * 101)
    for name, domain, k, largest, control, seed_index in EXACT_CONFIRMATIONS:
        records = create_records(
            create_exact_values(exact_size, domain, 93_000 + seed_index)
        )
        row = summarize_case(
            name,
            domain,
            min(k, exact_size),
            largest,
            control,
            records,
            (STRICT, ADAPTIVE),
            STRICT,
            blocks,
            calls_per_block,
        )
        row["size"] = exact_size
        rows.append(row)
        print(
            f"{name:<43}  {row['medians_s'][STRICT]:>9.6f}s"
            f"  {row['medians_s'][ADAPTIVE]:>9.6f}s"
            f"  {row['median_paired_speedup']:>7.2f}x"
            f"  {str(control):>7}"
        )
        del records
        gc.collect()

    for name, domain, k, largest, control, seed_index in GENERIC_CONFIRMATIONS:
        records = create_records(
            create_generic_values(
                generic_size,
                domain,
                94_000 + seed_index,
            )
        )
        row = summarize_case(
            name,
            domain,
            min(k, generic_size),
            largest,
            control,
            records,
            (HEAPQ, ADAPTIVE),
            HEAPQ,
            blocks,
            calls_per_block,
        )
        row["size"] = generic_size
        rows.append(row)
        print(
            f"{name:<43}  {row['medians_s'][HEAPQ]:>9.6f}s"
            f"  {row['medians_s'][ADAPTIVE]:>9.6f}s"
            f"  {row['median_paired_speedup']:>7.2f}x"
            f"  {str(control):>7}"
        )
        del records
        gc.collect()
    return rows


def evaluate_confirmation(
    rows,
    exact_size,
    generic_size,
    blocks,
    calls_per_block,
):
    canonical_shape = (
        exact_size == 1_000_000
        and generic_size == 100_000
        and blocks == 15
        and calls_per_block == 3
        and len(rows) == 6
        and sum(row["control"] for row in rows) == 2
    )
    below_bound = [
        row for row in rows if row["median_paired_speedup"] < 0.87
    ]
    return {
        "consistent_with_host_variability": (
            canonical_shape and not below_bound
        ),
        "canonical_shape_present": canonical_shape,
        "required_minimum_paired_speedup": 0.87,
        "cases_below_bound": [
            {
                "name": row["name"],
                "control": row["control"],
                "median_paired_speedup": row["median_paired_speedup"],
            }
            for row in below_bound
        ],
        "note": (
            "This confirmation cannot replace the failed stage-two gate or "
            "approve public API work."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-size", type=int, default=1_000_000)
    parser.add_argument("--generic-size", type=int, default=100_000)
    parser.add_argument("--blocks", type=int, default=15)
    parser.add_argument("--calls-per-block", type=int, default=3)
    parser.add_argument("--json-output", type=Path)
    arguments = parser.parse_args()
    if (
        arguments.exact_size < 0
        or arguments.generic_size < 0
        or arguments.blocks < 1
        or arguments.calls_per_block < 1
    ):
        raise SystemExit("sizes must be non-negative; blocks and calls >= 1")

    rows = execute(
        arguments.exact_size,
        arguments.generic_size,
        arguments.blocks,
        arguments.calls_per_block,
    )
    decision = evaluate_confirmation(
        rows,
        arguments.exact_size,
        arguments.generic_size,
        arguments.blocks,
        arguments.calls_per_block,
    )
    print(
        "\nCONFIRMATION: "
        + (
            "CONSISTENT WITH HOST VARIABILITY"
            if decision["consistent_with_host_variability"]
            else "REPRODUCIBLE REGRESSION OR INCOMPLETE SHAPE"
        )
    )

    if arguments.json_output:
        payload = {
            "benchmark": "private-adaptive-keyed-topk-confirmation",
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
                "compiler": platform.python_compiler(),
            },
            "configuration": {
                "exact_size": arguments.exact_size,
                "generic_size": arguments.generic_size,
                "blocks": arguments.blocks,
                "calls_per_block": arguments.calls_per_block,
                "selection_code_changed_since_failed_gate": False,
            },
            "results": rows,
            "decision": decision,
        }
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Raw JSON written to {arguments.json_output}")


if __name__ == "__main__":
    main()
