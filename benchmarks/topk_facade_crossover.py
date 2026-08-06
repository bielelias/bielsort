"""Run the pre-registered unified stable top-k façade protocol.

The protocol was frozen in commit 0cc6989 before this harness and before the
private façade implementation. The one canonical execution must use the
unchanged defaults and a separately recorded implementation commit.
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
from dataclasses import FrozenInstanceError
from pathlib import Path

import bielsort
import bielsort_native
from bielsort_native._topk_facade import top_k_adaptive


PROTOCOL_COMMIT = "0cc6989"
FACADE = "facade"
BASELINE = "baseline"
DOMAINS = (
    "natural-int64",
    "natural-string",
    "keyed-int64",
    "keyed-huge-int",
    "keyed-string",
)
DIRECTIONS = ("smallest", "largest")
DENOMINATORS = (64, 16, 8, 4, 2)
FULL_SORT_DENOMINATORS = frozenset((8, 4, 2))
REGRESSION_FLOOR = 0.85
NEAR_PARITY_TARGET = 0.95
MINIMUM_NEAR_PARITY_CASES = 40


class CountingKey:
    """Retain callback order without changing the wrapped key's semantics."""

    def __init__(self, inner):
        self.inner = inner
        self.record_ids = []

    def __call__(self, record):
        self.record_ids.append(id(record))
        return self.inner(record)


class OneShot:
    """Raise if a façade tries to iterate the source more than once."""

    def __init__(self, values):
        self.values = values
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations != 1:
            raise AssertionError("one-shot iterable was consumed twice")
        return iter(self.values)


class ExplodingIterator:
    def __iter__(self):
        yield (3, 0)
        raise LookupError("iterator-probe")


class ExplodingKey:
    def __call__(self, record):
        raise LookupError("key-probe")


class ExplodingComparison:
    def __lt__(self, other):
        del other
        raise LookupError("comparison-probe")


class NaturalValue:
    comparisons = 0

    def __init__(self, value, position):
        self.value = value
        self.position = position

    def __lt__(self, other):
        type(self).comparisons += 1
        return self.value < other.value


def median_absolute_deviation(values):
    center = statistics.median(values)
    return statistics.median([abs(value - center) for value in values])


def rotate(values, offset):
    offset %= len(values)
    return values[offset:] + values[:offset]


def ensure_identity(actual, expected, label):
    if len(actual) != len(expected) or any(
        left is not right for left, right in zip(actual, expected)
    ):
        raise AssertionError(f"{label} result differs by value or identity")


def create_domain(size, domain, seed):
    rng = random.Random(seed)
    if domain == "natural-int64":
        return [rng.randint(-size // 4, size // 4) for _ in range(size)], None
    if domain == "natural-string":
        return [
            "group-{0:06d}".format(rng.randrange(max(1, size // 4)))
            for _ in range(size)
        ], None
    if domain == "keyed-int64":
        values = [rng.randint(-size // 4, size // 4) for _ in range(size)]
    elif domain == "keyed-huge-int":
        values = [
            (rng.randint(-(1 << 40), 1 << 40) << 80)
            + rng.randrange(1 << 40)
            for _ in range(size)
        ]
    elif domain == "keyed-string":
        values = [
            "group-{0:06d}".format(rng.randrange(max(1, size // 4)))
            for _ in range(size)
        ]
    else:
        raise ValueError(f"unknown domain: {domain}")
    return [(value, position) for position, value in enumerate(values)], operator.itemgetter(0)


def full_reference(values, k, key, largest):
    return sorted(values, key=key, reverse=largest)[:k]


def run_baseline(values, k, key, largest, denominator):
    if denominator in FULL_SORT_DENOMINATORS:
        return full_reference(values, k, key, largest)
    selection = heapq.nlargest if largest else heapq.nsmallest
    return selection(k, values, key=key)


def run_algorithm(algorithm, values, k, key, largest, denominator):
    if algorithm == FACADE:
        return top_k_adaptive(values, k, key=key, largest=largest)
    if algorithm == BASELINE:
        return run_baseline(values, k, key, largest, denominator)
    raise ValueError(f"unknown algorithm: {algorithm}")


def expected_algorithm(domain, denominator):
    if domain in ("natural-int64", "keyed-int64"):
        return "native-int64"
    if denominator in FULL_SORT_DENOMINATORS:
        return "timsort"
    if domain == "natural-string":
        return "heapq"
    return "native-generic"


def measure_case(
    values,
    k,
    key,
    largest,
    denominator,
    expected,
    blocks,
    calls_per_block,
):
    algorithms = [BASELINE, FACADE]
    for algorithm in algorithms:
        result = run_algorithm(
            algorithm,
            values,
            k,
            key,
            largest,
            denominator,
        )
        ensure_identity(result, expected, algorithm)
        del result
    gc.collect()

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
                        values,
                        k,
                        key,
                        largest,
                        denominator,
                    )
                    elapsed += time.perf_counter() - started
                    ensure_identity(result, expected, algorithm)
                    del result
            finally:
                gc.enable()
            samples[algorithm].append(elapsed / calls_per_block)
    gc.collect()

    medians = {
        algorithm: statistics.median(durations)
        for algorithm, durations in samples.items()
    }
    deviations = {
        algorithm: median_absolute_deviation(durations)
        for algorithm, durations in samples.items()
    }
    paired_speedups = [
        baseline / facade
        for baseline, facade in zip(samples[BASELINE], samples[FACADE])
    ]
    return {
        "samples_s": samples,
        "medians_s": medians,
        "median_absolute_deviations_s": deviations,
        "paired_speedups": paired_speedups,
        "median_paired_speedup": statistics.median(paired_speedups),
        "ratio_of_medians": medians[BASELINE] / medians[FACADE],
    }


def run_timing_matrix(size, denominators, domains, directions, blocks, calls_per_block):
    rows = []
    print("UNIFIED TOP-K FACADE (median paired speedup; higher is better)")
    print(
        f"{'domain':<19}  {'k/n':>6}  {'direction':<8}  {'baseline':>10}"
        f"  {'facade':>10}  {'paired':>8}  {'route':<14}"
    )
    print("-" * 93)
    for domain_index, domain in enumerate(domains):
        values, key = create_domain(size, domain, 101_000 + domain_index)
        expected_by_direction = {
            direction: sorted(
                values,
                key=key,
                reverse=direction == "largest",
            )
            for direction in directions
        }
        for denominator in denominators:
            k = min(size, size // denominator)
            for direction in directions:
                largest = direction == "largest"
                expected = expected_by_direction[direction][:k]
                timing = measure_case(
                    values,
                    k,
                    key,
                    largest,
                    denominator,
                    expected,
                    blocks,
                    calls_per_block,
                )
                diagnostic_result, info = top_k_adaptive(
                    values,
                    k,
                    key=key,
                    largest=largest,
                    return_info=True,
                )
                ensure_identity(diagnostic_result, expected, "diagnostic")
                expected_route = expected_algorithm(domain, denominator)
                route_passed = info.algorithm == expected_route
                row = {
                    "size": size,
                    "k": k,
                    "k_denominator": denominator,
                    "domain": domain,
                    "direction": direction,
                    "baseline_algorithm": (
                        "timsort"
                        if denominator in FULL_SORT_DENOMINATORS
                        else "heapq"
                    ),
                    "expected_facade_algorithm": expected_route,
                    "observed_facade_info": info.as_dict(),
                    "routing_passed": route_passed,
                    **timing,
                }
                rows.append(row)
                print(
                    f"{domain:<19}  {'1/' + str(denominator):>6}"
                    f"  {direction:<8}"
                    f"  {timing['medians_s'][BASELINE]:>9.6f}s"
                    f"  {timing['medians_s'][FACADE]:>9.6f}s"
                    f"  {timing['median_paired_speedup']:>7.2f}x"
                    f"  {info.algorithm:<14}"
                )
                del diagnostic_result
        del expected_by_direction, values
        gc.collect()
    return rows


def probe(name, operation):
    try:
        details = operation()
    except Exception as error:  # pragma: no cover - retained in JSON on fail
        return {
            "name": name,
            "passed": False,
            "error": f"{type(error).__name__}: {error}",
        }
    if details is None:
        details = {}
    return {"name": name, "passed": True, **details}


def probe_key_calls():
    records = [(position % 37, position) for position in range(4_096)]
    expected_ids = [id(record) for record in records]
    details = []
    for k, route in ((31, "partial"), (1_024, "full")):
        for largest in (False, True):
            key = CountingKey(operator.itemgetter(0))
            expected = full_reference(
                records,
                k,
                operator.itemgetter(0),
                largest,
            )
            result, info = top_k_adaptive(
                records,
                k,
                key=key,
                largest=largest,
                return_info=True,
            )
            ensure_identity(result, expected, "key-call-probe")
            if key.record_ids != expected_ids:
                raise AssertionError("explicit key was not called once in order")
            details.append(
                {
                    "route": route,
                    "direction": "largest" if largest else "smallest",
                    "calls": len(key.record_ids),
                    "algorithm": info.algorithm,
                }
            )
    return {"cases": details}


def probe_zero_and_invalid_k():
    consumed = []

    def source():
        consumed.append(True)
        yield 1

    result = top_k_adaptive(source(), 0, key=object())
    if result != [] or consumed:
        raise AssertionError("k=0 consumed or validated the source key")
    for invalid, exception in ((-1, ValueError), (True, TypeError)):
        try:
            top_k_adaptive(source(), invalid)
        except exception:
            pass
        else:
            raise AssertionError(f"k={invalid!r} did not raise {exception.__name__}")
    if consumed:
        raise AssertionError("invalid k consumed the iterable")
    return {"source_consumptions": len(consumed)}


def probe_natural_and_one_shot():
    NaturalValue.comparisons = 0
    natural = [NaturalValue(value, position) for position, value in enumerate((4, 1, 4, 2))]
    expected = sorted(natural)[:3]
    result = top_k_adaptive(natural, 3)
    ensure_identity(result, expected, "natural-order-probe")

    records = [(position % 19, position) for position in range(4_096)]
    source = OneShot(records)
    key = CountingKey(operator.itemgetter(0))
    expected = full_reference(records, 31, operator.itemgetter(0), False)
    result = top_k_adaptive(source, 31, key=key)
    ensure_identity(result, expected, "one-shot-probe")
    if source.iterations != 1 or len(key.record_ids) != len(records):
        raise AssertionError("one-shot/key-call contract failed")
    return {
        "natural_comparisons": NaturalValue.comparisons,
        "one_shot_iterations": source.iterations,
        "key_calls": len(key.record_ids),
    }


def probe_exceptions():
    for operation, expected_text in (
        (
            lambda: top_k_adaptive(
                ExplodingIterator(),
                2,
                key=operator.itemgetter(0),
            ),
            "iterator-probe",
        ),
        (
            lambda: top_k_adaptive([(1, 0)] * 4_096, 31, key=ExplodingKey()),
            "key-probe",
        ),
        (
            lambda: top_k_adaptive(
                [(position, position) for position in range(4_096)],
                31,
                key=lambda record: ExplodingComparison(),
            ),
            "comparison-probe",
        ),
    ):
        try:
            operation()
        except LookupError as error:
            if str(error) != expected_text:
                raise
        else:
            raise AssertionError(f"{expected_text} was not propagated")
    return {"propagated": ["iterator", "key", "comparison"]}


def probe_memory_guard():
    records = [(position % 37, position) for position in range(4_096)]
    key = CountingKey(operator.itemgetter(0))
    result, info = top_k_adaptive(
        records,
        31,
        key=key,
        max_native_auxiliary_bytes=0,
        on_memory_limit="heapq",
        return_info=True,
    )
    expected = full_reference(records, 31, operator.itemgetter(0), False)
    ensure_identity(result, expected, "guard-fallback")
    if len(key.record_ids) != len(records) or not info.native_memory_limit_exceeded:
        raise AssertionError("guard fallback diagnostics or key calls failed")

    raise_key = CountingKey(operator.itemgetter(0))
    try:
        top_k_adaptive(
            records,
            31,
            key=raise_key,
            max_native_auxiliary_bytes=0,
            on_memory_limit="raise",
        )
    except MemoryError:
        pass
    else:
        raise AssertionError("guard raise policy did not raise")
    if raise_key.record_ids:
        raise AssertionError("guard raise policy called key")
    return {
        "fallback_algorithm": info.algorithm,
        "fallback_key_calls": len(key.record_ids),
        "raise_key_calls": len(raise_key.record_ids),
    }


def probe_info_and_isolation():
    _, info = top_k_adaptive([3, 1, 2], 2, return_info=True)
    try:
        info.algorithm = "changed"
    except (FrozenInstanceError, AttributeError):
        immutable = True
    else:
        immutable = False
    if not immutable:
        raise AssertionError("diagnostic record is mutable")
    forbidden = ("top_k", "top_k_with_info", "TopKInfo")
    leaked = [
        f"{module.__name__}.{name}"
        for module in (bielsort, bielsort_native)
        for name in forbidden
        if hasattr(module, name) or name in getattr(module, "__all__", ())
    ]
    if leaked:
        raise AssertionError("private API leaked: " + ", ".join(leaked))
    return {"immutable": immutable, "public_leaks": leaked, "info": info.as_dict()}


def probe_callback_resize():
    records = [(position, position) for position in range(4_096)]
    calls = []

    def resizing_key(record):
        calls.append(id(record))
        if len(calls) == 1:
            records.clear()
        return record[0]

    try:
        top_k_adaptive(records, 31, key=resizing_key)
    except RuntimeError:
        return {"raised": "RuntimeError", "key_calls_before_raise": len(calls)}
    raise AssertionError("callback source resize did not raise RuntimeError")


def run_semantic_probes():
    probes = [
        probe("one-key-call-partial-and-full", probe_key_calls),
        probe("zero-and-invalid-k-before-consumption", probe_zero_and_invalid_k),
        probe("natural-order-and-one-shot", probe_natural_and_one_shot),
        probe("exception-propagation", probe_exceptions),
        probe("pre-key-memory-guard", probe_memory_guard),
        probe("immutable-info-and-public-isolation", probe_info_and_isolation),
        probe("callback-resize-safety", probe_callback_resize),
    ]
    return {"passed": all(item["passed"] for item in probes), "probes": probes}


def evaluate_gate(rows, semantics, size, denominators, domains, directions, blocks, calls_per_block):
    expected_cases = {
        (domain, denominator, direction)
        for domain in DOMAINS
        for denominator in DENOMINATORS
        for direction in DIRECTIONS
    }
    actual_cases = {
        (row["domain"], row["k_denominator"], row["direction"])
        for row in rows
    }
    canonical_parameters = (
        size == 200_000
        and denominators == list(DENOMINATORS)
        and domains == list(DOMAINS)
        and directions == list(DIRECTIONS)
        and blocks == 7
        and calls_per_block == 1
    )
    canonical_shape = (
        len(rows) == 50
        and actual_cases == expected_cases
        and all(
            len(row["samples_s"][algorithm]) == blocks
            for row in rows
            for algorithm in (BASELINE, FACADE)
        )
    )
    regressions = [
        row for row in rows
        if row["median_paired_speedup"] < REGRESSION_FLOOR
    ]
    near_parity = [
        row for row in rows
        if row["median_paired_speedup"] >= NEAR_PARITY_TARGET
    ]
    routing_passed = all(row["routing_passed"] for row in rows)
    passed = (
        canonical_parameters
        and canonical_shape
        and semantics["passed"]
        and routing_passed
        and not regressions
        and len(near_parity) >= MINIMUM_NEAR_PARITY_CASES
    )
    return {
        "passed": passed,
        "canonical_parameters_present": canonical_parameters,
        "canonical_shape_present": canonical_shape,
        "semantic_probes_passed": semantics["passed"],
        "routing_assertions_passed": routing_passed,
        "cases_at_or_above_0_95x": len(near_parity),
        "required_cases_at_or_above_0_95x": MINIMUM_NEAR_PARITY_CASES,
        "regressions_below_0_85x": [
            {
                "domain": row["domain"],
                "k_denominator": row["k_denominator"],
                "direction": row["direction"],
                "median_paired_speedup": row["median_paired_speedup"],
            }
            for row in regressions
        ],
        "fixed_thresholds": {
            "regression_floor": REGRESSION_FLOOR,
            "near_parity_target": NEAR_PARITY_TARGET,
            "minimum_near_parity_cases": MINIMUM_NEAR_PARITY_CASES,
        },
        "note": (
            "A pass permits only a separate public API proposal; it does not "
            "approve a version, tag, merge, TestPyPI, or PyPI publication."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=200_000)
    parser.add_argument(
        "--denominators",
        type=int,
        nargs="+",
        default=list(DENOMINATORS),
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        choices=DOMAINS,
        default=list(DOMAINS),
    )
    parser.add_argument(
        "--directions",
        nargs="+",
        choices=DIRECTIONS,
        default=list(DIRECTIONS),
    )
    parser.add_argument("--blocks", type=int, default=7)
    parser.add_argument("--calls-per-block", type=int, default=1)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--json-output", type=Path)
    arguments = parser.parse_args()
    if (
        arguments.size < 1
        or arguments.blocks < 1
        or arguments.calls_per_block < 1
        or any(denominator < 1 for denominator in arguments.denominators)
    ):
        raise SystemExit("size, denominators, blocks, and calls must be >= 1")

    semantics = run_semantic_probes()
    rows = run_timing_matrix(
        arguments.size,
        arguments.denominators,
        arguments.domains,
        arguments.directions,
        arguments.blocks,
        arguments.calls_per_block,
    )
    gate = evaluate_gate(
        rows,
        semantics,
        arguments.size,
        arguments.denominators,
        arguments.domains,
        arguments.directions,
        arguments.blocks,
        arguments.calls_per_block,
    )
    print(
        "\nUNIFIED STABLE TOP-K FACADE GATE: "
        + ("PASS" if gate["passed"] else "NOT PASSED OR NON-CANONICAL")
    )

    if arguments.json_output:
        payload = {
            "benchmark": "private-unified-stable-topk-facade",
            "environment": {
                "platform": platform.platform(),
                "python": sys.version,
                "compiler": platform.python_compiler(),
            },
            "provenance": {
                "pre_registered_protocol_commit": PROTOCOL_COMMIT,
                "benchmark_implementation_commit": arguments.implementation_commit,
            },
            "configuration": {
                "size": arguments.size,
                "denominators": arguments.denominators,
                "domains": arguments.domains,
                "directions": arguments.directions,
                "blocks": arguments.blocks,
                "calls_per_block": arguments.calls_per_block,
                "warmups_per_algorithm": 1,
                "full_sort_when": "selected * 8 >= n",
                "primary_statistic": "median paired block speedup",
                "spread_statistic": "unscaled median absolute deviation",
            },
            "semantic_probes": semantics,
            "timing_cases": rows,
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

