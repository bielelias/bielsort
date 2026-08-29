"""Measure practical key callables and isolated top-k peak memory.

The protocol is pre-registered in commit 1c793b9. Memory workers run before
the timing supervisor has held a large workload, and every benchmark result is
checked against stable full sorting by exact object identity.
"""

import argparse
import gc
import heapq
import json
import operator
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections import namedtuple
from pathlib import Path

try:
    import resource
except ImportError:  # pragma: no cover - unavailable on Windows
    resource = None

from benchmarks.keyed_topk_block_canonical import (
    median_absolute_deviation,
)
from benchmarks.keyed_topk_fallback import (
    ADAPTIVE,
    DIRECTIONS,
    HEAPQ,
    ensure_identity,
    rotate,
)
from bielsort_native import _bielsort


PROTOCOL_COMMIT = "1c793b9"
SELECTION_CODE_COMMIT = "fdc9bb5"
TIME_ALGORITHMS = (HEAPQ, ADAPTIVE)
CALLABLE_NAMES = (
    "itemgetter-index",
    "lambda-index",
    "attrgetter-score",
    "lambda-score",
)
MEMORY_DOMAINS = ("dense-int64", "huge-int")
MEMORY_CALLABLE = "attrgetter-score"
CALLABLE_TARGET = 1.10
CALLABLE_REGRESSION_FLOOR = 0.90
MEMORY_REGRESSION_CEILING = 1.25
MEMORY_REDUCTION_TARGET = 0.80

PracticalRecord = namedtuple("PracticalRecord", ("score", "payload"))


KEY_FUNCTIONS = {
    "itemgetter-index": operator.itemgetter(0),
    "lambda-index": lambda record: record[0],
    "attrgetter-score": operator.attrgetter("score"),
    "lambda-score": lambda record: record.score,
}


class CountingKey:
    """Record key-call order for untimed semantic probes."""

    def __init__(self, inner):
        self.inner = inner
        self.record_ids = []

    def __call__(self, record):
        self.record_ids.append(id(record))
        return self.inner(record)


def peak_rss_bytes():
    if resource is None:
        raise RuntimeError("isolated peak RSS requires Linux or macOS")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def create_scores(size, domain, seed):
    rng = random.Random(seed)
    if domain in ("dense", "dense-int64"):
        return [rng.randint(-size // 4, size // 4) for _ in range(size)]
    if domain == "huge-int":
        return [
            rng.randint(-(1 << 40), (1 << 40)) * (1 << 80)
            + rng.randrange(1 << 40)
            for _ in range(size)
        ]
    raise ValueError(f"unknown score domain: {domain}")


def create_records(size, domain, seed):
    return [
        PracticalRecord(score, position)
        for position, score in enumerate(create_scores(size, domain, seed))
    ]


def run_algorithm(algorithm, records, k, key, largest):
    if algorithm == HEAPQ:
        function = heapq.nlargest if largest else heapq.nsmallest
        return function(k, records, key=key)
    if algorithm == ADAPTIVE:
        return _bielsort._topk_by_key_prototype(
            records,
            k,
            key,
            largest,
        )
    raise ValueError(f"unknown algorithm: {algorithm}")


def run_semantic_probes():
    records = create_records(257, "dense", 95_000)
    results = []
    input_ids = [id(record) for record in records]
    for callable_name in CALLABLE_NAMES:
        base_key = KEY_FUNCTIONS[callable_name]
        directions_passed = True
        direction_details = []
        for largest in (False, True):
            counting_key = CountingKey(base_key)
            expected = sorted(
                records,
                key=base_key,
                reverse=largest,
            )[:17]
            result = run_algorithm(
                ADAPTIVE,
                records,
                17,
                counting_key,
                largest,
            )
            ensure_identity(result, expected, ADAPTIVE)
            calls_once_in_order = counting_key.record_ids == input_ids
            directions_passed = directions_passed and calls_once_in_order
            direction_details.append(
                {
                    "direction": "largest" if largest else "smallest",
                    "call_count": len(counting_key.record_ids),
                    "calls_once_in_order": calls_once_in_order,
                }
            )

        zero_key = CountingKey(base_key)
        empty = run_algorithm(ADAPTIVE, records, 0, zero_key, False)
        zero_k_passed = empty == [] and not zero_key.record_ids
        results.append(
            {
                "callable": callable_name,
                "passed": directions_passed and zero_k_passed,
                "directions": direction_details,
                "zero_k_calls": len(zero_key.record_ids),
            }
        )
    return results


def warm_up(algorithms, records, k, key, largest, expected):
    for algorithm in algorithms:
        result = run_algorithm(algorithm, records, k, key, largest)
        ensure_identity(result, expected, algorithm)
        del result
    gc.collect()


def measure_blocks(
    records,
    k,
    key,
    largest,
    expected,
    blocks,
    calls_per_block,
):
    warm_up(TIME_ALGORITHMS, records, k, key, largest, expected)
    samples = {algorithm: [] for algorithm in TIME_ALGORITHMS}
    for block in range(blocks):
        for algorithm in rotate(TIME_ALGORITHMS, block):
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
                        key,
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


def execute_time(size, ks, blocks, calls_per_block):
    records = create_records(size, "dense", 95_100)
    reference_key = KEY_FUNCTIONS[MEMORY_CALLABLE]
    expected_by_direction = {
        direction: sorted(
            records,
            key=reference_key,
            reverse=direction == "largest",
        )
        for direction in DIRECTIONS
    }
    rows = []
    print("PRACTICAL CALLABLES (median paired speedup; higher is better)")
    print(
        f"{'callable':<20}  {'k':>7}  {'direction':<8}"
        f"  {'heapq':>10}  {'adaptive':>10}  {'paired':>8}"
    )
    print("-" * 75)
    for callable_name in CALLABLE_NAMES:
        key = KEY_FUNCTIONS[callable_name]
        for k in ks:
            effective_k = min(k, size)
            for direction in DIRECTIONS:
                largest = direction == "largest"
                expected = expected_by_direction[direction][:effective_k]
                samples = measure_blocks(
                    records,
                    effective_k,
                    key,
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
                paired_speedups = [
                    heapq_sample / adaptive_sample
                    for heapq_sample, adaptive_sample in zip(
                        samples[HEAPQ],
                        samples[ADAPTIVE],
                    )
                ]
                paired_median = statistics.median(paired_speedups)
                row = {
                    "size": size,
                    "callable": callable_name,
                    "k": effective_k,
                    "direction": direction,
                    "medians_s": medians,
                    "median_absolute_deviations_s": deviations,
                    "samples_s": samples,
                    "paired_speedups_over_heapq": paired_speedups,
                    "median_paired_speedup_over_heapq": paired_median,
                    "ratio_of_medians": medians[HEAPQ] / medians[ADAPTIVE],
                }
                rows.append(row)
                print(
                    f"{callable_name:<20}  {effective_k:>7,}"
                    f"  {direction:<8}  {medians[HEAPQ]:>9.6f}s"
                    f"  {medians[ADAPTIVE]:>9.6f}s"
                    f"  {paired_median:>7.2f}x"
                )
    del expected_by_direction, records
    gc.collect()
    return rows


def run_memory_worker(algorithm, domain, size, k, direction, seed):
    if resource is None:
        raise RuntimeError("isolated memory workers require Linux or macOS")
    records = create_records(size, domain, seed)
    key = KEY_FUNCTIONS[MEMORY_CALLABLE]
    largest = direction == "largest"
    gc.collect()
    tracemalloc.start()
    gc.collect()
    traced_baseline = tracemalloc.get_traced_memory()[0]
    rss_baseline = peak_rss_bytes()
    started = time.perf_counter()
    result = run_algorithm(algorithm, records, k, key, largest)
    elapsed = time.perf_counter() - started
    traced_peak = tracemalloc.get_traced_memory()[1]
    rss_peak = peak_rss_bytes()
    tracemalloc.stop()

    expected = sorted(records, key=key, reverse=largest)[:k]
    ensure_identity(result, expected, algorithm)
    return {
        "algorithm": algorithm,
        "domain": domain,
        "size": size,
        "k": min(k, size),
        "direction": direction,
        "seed": seed,
        "elapsed_s_diagnostic": elapsed,
        "traced_baseline_bytes": traced_baseline,
        "traced_peak_bytes": traced_peak,
        "incremental_traced_peak_bytes": max(
            0,
            traced_peak - traced_baseline,
        ),
        "rss_baseline_bytes": rss_baseline,
        "rss_peak_bytes": rss_peak,
        "incremental_rss_peak_bytes": max(0, rss_peak - rss_baseline),
        "identity_validated": True,
    }


def invoke_memory_worker(algorithm, domain, size, k, direction, seed):
    command = [
        sys.executable,
        "-m",
        "benchmarks.keyed_topk_practical",
        "--worker",
        algorithm,
        domain,
        str(size),
        str(k),
        direction,
        str(seed),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def execute_memory(size, ks, repetitions):
    rows = []
    print("ISOLATED PEAK MEMORY (median; lower adaptive/heapq is better)")
    print(
        f"{'domain':<13}  {'k':>8}  {'direction':<8}"
        f"  {'heapq traced':>13}  {'adaptive':>13}  {'ratio':>7}"
        f"  {'RSS ratio':>9}"
    )
    print("-" * 91)
    for domain_index, domain in enumerate(MEMORY_DOMAINS):
        for k in ks:
            effective_k = min(k, size)
            for direction in DIRECTIONS:
                samples = {algorithm: [] for algorithm in TIME_ALGORITHMS}
                for repetition in range(repetitions):
                    for algorithm in rotate(TIME_ALGORITHMS, repetition):
                        sample = invoke_memory_worker(
                            algorithm,
                            domain,
                            size,
                            effective_k,
                            direction,
                            96_000 + domain_index * 100 + repetition,
                        )
                        samples[algorithm].append(sample)
                traced_medians = {
                    algorithm: statistics.median(
                        sample["incremental_traced_peak_bytes"]
                        for sample in algorithm_samples
                    )
                    for algorithm, algorithm_samples in samples.items()
                }
                rss_medians = {
                    algorithm: statistics.median(
                        sample["incremental_rss_peak_bytes"]
                        for sample in algorithm_samples
                    )
                    for algorithm, algorithm_samples in samples.items()
                }
                traced_ratio = (
                    traced_medians[ADAPTIVE] / traced_medians[HEAPQ]
                    if traced_medians[HEAPQ]
                    else None
                )
                rss_ratio = (
                    rss_medians[ADAPTIVE] / rss_medians[HEAPQ]
                    if rss_medians[HEAPQ]
                    else None
                )
                row = {
                    "size": size,
                    "domain": domain,
                    "k": effective_k,
                    "direction": direction,
                    "callable": MEMORY_CALLABLE,
                    "median_incremental_traced_peak_bytes": traced_medians,
                    "adaptive_to_heapq_traced_peak_ratio": traced_ratio,
                    "median_incremental_rss_peak_bytes": rss_medians,
                    "adaptive_to_heapq_rss_peak_ratio_diagnostic": rss_ratio,
                    "samples": samples,
                }
                rows.append(row)
                traced_text = (
                    f"{traced_ratio:.2f}x" if traced_ratio is not None
                    else "n/a"
                )
                rss_text = (
                    f"{rss_ratio:.2f}x" if rss_ratio is not None else "n/a"
                )
                print(
                    f"{domain:<13}  {effective_k:>8,}  {direction:<8}"
                    f"  {traced_medians[HEAPQ] / 2**20:>11.2f} MiB"
                    f"  {traced_medians[ADAPTIVE] / 2**20:>11.2f} MiB"
                    f"  {traced_text:>7}  {rss_text:>9}"
                )
    return rows


def complete_time_shape(rows, size, ks, blocks):
    expected = {
        (callable_name, k, direction)
        for callable_name in CALLABLE_NAMES
        for k in ks
        for direction in DIRECTIONS
    }
    actual = {
        (row["callable"], row["k"], row["direction"])
        for row in rows
        if row["size"] == size
    }
    return (
        len(rows) == len(expected)
        and actual == expected
        and all(
            set(row["samples_s"]) == set(TIME_ALGORITHMS)
            and all(
                len(row["samples_s"][algorithm]) == blocks
                for algorithm in TIME_ALGORITHMS
            )
            for row in rows
        )
    )


def complete_memory_shape(rows, size, ks, repetitions):
    expected = {
        (domain, k, direction)
        for domain in MEMORY_DOMAINS
        for k in ks
        for direction in DIRECTIONS
    }
    actual = {
        (row["domain"], row["k"], row["direction"])
        for row in rows
        if row["size"] == size
    }
    return (
        len(rows) == len(expected)
        and actual == expected
        and all(
            set(row["samples"]) == set(TIME_ALGORITHMS)
            and all(
                len(row["samples"][algorithm]) == repetitions
                for algorithm in TIME_ALGORITHMS
            )
            for row in rows
        )
    )


def evaluate_gates(
    semantic_probes,
    time_rows,
    memory_rows,
    time_size,
    time_ks,
    time_blocks,
    calls_per_block,
    memory_size,
    memory_ks,
    memory_repetitions,
):
    callable_parameters = (
        time_size == 1_000_000
        and time_ks == [10, 100, 1_000]
        and time_blocks == 9
        and calls_per_block == 3
    )
    callable_shape = complete_time_shape(
        time_rows,
        time_size,
        (10, 100, 1_000),
        time_blocks,
    )
    semantics_passed = (
        len(semantic_probes) == len(CALLABLE_NAMES)
        and all(probe["passed"] for probe in semantic_probes)
    )
    callable_targets = [
        row
        for row in time_rows
        if row["median_paired_speedup_over_heapq"] >= CALLABLE_TARGET
    ]
    callable_regressions = [
        row
        for row in time_rows
        if row["median_paired_speedup_over_heapq"]
        < CALLABLE_REGRESSION_FLOOR
    ]
    callable_passed = (
        callable_parameters
        and callable_shape
        and semantics_passed
        and len(callable_targets) >= 18
        and not callable_regressions
    )

    memory_parameters = (
        memory_size == 1_000_000
        and memory_ks == [1_000, 100_000]
        and memory_repetitions == 3
    )
    memory_shape = complete_memory_shape(
        memory_rows,
        memory_size,
        (1_000, 100_000),
        memory_repetitions,
    )
    unmeasurable = [
        row
        for row in memory_rows
        if not row["median_incremental_traced_peak_bytes"][HEAPQ]
        or row["adaptive_to_heapq_traced_peak_ratio"] is None
    ]
    memory_regressions = [
        row
        for row in memory_rows
        if row["adaptive_to_heapq_traced_peak_ratio"] is not None
        and row["adaptive_to_heapq_traced_peak_ratio"]
        > MEMORY_REGRESSION_CEILING
    ]
    high_k_reductions = [
        row
        for row in memory_rows
        if row["k"] == 100_000
        and row["adaptive_to_heapq_traced_peak_ratio"] is not None
        and row["adaptive_to_heapq_traced_peak_ratio"]
        <= MEMORY_REDUCTION_TARGET
    ]
    memory_passed = (
        memory_parameters
        and memory_shape
        and not unmeasurable
        and not memory_regressions
        and len(high_k_reductions) >= 2
    )
    return {
        "passed": callable_passed and memory_passed,
        "callable_gate": {
            "passed": callable_passed,
            "canonical_parameters_present": callable_parameters,
            "canonical_shape_present": callable_shape,
            "semantic_probes_passed": semantics_passed,
            "cases_at_least_1_10x_over_heapq": len(callable_targets),
            "target_case_count": len(time_rows),
            "regressions_below_0_90x": [
                {
                    "callable": row["callable"],
                    "k": row["k"],
                    "direction": row["direction"],
                    "median_paired_speedup": (
                        row["median_paired_speedup_over_heapq"]
                    ),
                }
                for row in callable_regressions
            ],
        },
        "memory_gate": {
            "passed": memory_passed,
            "canonical_parameters_present": memory_parameters,
            "canonical_shape_present": memory_shape,
            "unmeasurable_cases": len(unmeasurable),
            "regressions_above_1_25x": [
                {
                    "domain": row["domain"],
                    "k": row["k"],
                    "direction": row["direction"],
                    "ratio": row["adaptive_to_heapq_traced_peak_ratio"],
                }
                for row in memory_regressions
            ],
            "high_k_cases_at_or_below_0_80x": len(high_k_reductions),
            "high_k_case_count": sum(
                row["k"] == 100_000 for row in memory_rows
            ),
            "rss_is_diagnostic_only": True,
            "structural_contract": {
                "retained_key_objects": "O(k)",
                "native_entry_buffers": "at most 2 * k",
                "key_array_for_reusable_input": False,
            },
        },
        "note": (
            "A pass authorizes a private API proposal and build-only wheel "
            "validation, not a public API, version, tag, merge, or release."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-size", type=int, default=1_000_000)
    parser.add_argument("--memory-size", type=int, default=1_000_000)
    parser.add_argument(
        "-k",
        "--ks",
        type=int,
        nargs="+",
        default=[10, 100, 1_000],
    )
    parser.add_argument("--time-blocks", type=int, default=9)
    parser.add_argument("--calls-per-block", type=int, default=3)
    parser.add_argument(
        "--memory-k",
        type=int,
        nargs="+",
        default=[1_000, 100_000],
    )
    parser.add_argument("--memory-repetitions", type=int, default=3)
    parser.add_argument("--implementation-commit")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--skip-time", action="store_true")
    parser.add_argument(
        "--worker",
        nargs=6,
        metavar=("ALGORITHM", "DOMAIN", "N", "K", "DIRECTION", "SEED"),
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args()

    if arguments.worker is not None:
        algorithm, domain, size, k, direction, seed = arguments.worker
        print(
            json.dumps(
                run_memory_worker(
                    algorithm,
                    domain,
                    int(size),
                    int(k),
                    direction,
                    int(seed),
                )
            )
        )
        return

    if arguments.implementation_commit is None:
        parser.error("--implementation-commit is required for supervisor runs")
    if (
        arguments.time_size < 1
        or arguments.memory_size < 1
        or arguments.time_blocks < 1
        or arguments.calls_per_block < 1
        or arguments.memory_repetitions < 1
        or any(k < 0 for k in arguments.ks)
        or any(k < 0 for k in arguments.memory_k)
    ):
        parser.error("sizes, blocks, calls, and repetitions must be positive")

    semantic_probes = run_semantic_probes()
    memory_rows = []
    if not arguments.skip_memory:
        memory_rows = execute_memory(
            arguments.memory_size,
            arguments.memory_k,
            arguments.memory_repetitions,
        )
    time_rows = []
    if not arguments.skip_time:
        time_rows = execute_time(
            arguments.time_size,
            arguments.ks,
            arguments.time_blocks,
            arguments.calls_per_block,
        )
    gates = evaluate_gates(
        semantic_probes,
        time_rows,
        memory_rows,
        arguments.time_size,
        arguments.ks,
        arguments.time_blocks,
        arguments.calls_per_block,
        arguments.memory_size,
        arguments.memory_k,
        arguments.memory_repetitions,
    )
    print(
        "\nPRACTICAL KEYED TOP-K GATE: "
        + ("PASS" if gates["passed"] else "NOT PASSED OR NON-CANONICAL")
    )

    if arguments.json_output is not None:
        payload = {
            "benchmark": "private-adaptive-keyed-topk-practical",
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
                "previous_results_preserved": True,
            },
            "configuration": {
                "time_size": arguments.time_size,
                "time_ks": arguments.ks,
                "time_blocks": arguments.time_blocks,
                "calls_per_block": arguments.calls_per_block,
                "callables": list(CALLABLE_NAMES),
                "memory_size": arguments.memory_size,
                "memory_ks": arguments.memory_k,
                "memory_repetitions": arguments.memory_repetitions,
                "memory_domains": list(MEMORY_DOMAINS),
                "memory_callable": MEMORY_CALLABLE,
                "memory_runs_before_timing": True,
            },
            "semantic_probes": semantic_probes,
            "callable_timing": time_rows,
            "isolated_memory": memory_rows,
            "decision_gates": gates,
        }
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Raw JSON written to {arguments.json_output}")


if __name__ == "__main__":
    main()
