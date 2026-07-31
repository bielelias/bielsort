"""Profile BielSort's Timsort fallback without changing its heuristics."""

import argparse
import gc
import json
import os
import platform
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import bielsort


CASE_DESCRIPTIONS = {
    "ordered": "an already ordered integer list",
    "adjacent-swaps": (
        "an ordered list with sparse adjacent swaps"
    ),
    "random-swaps": (
        "an ordered list with sparse long-distance swaps"
    ),
}

OPERATION_NAMES = (
    "copy.list-copy",
    "copy.list-slice",
    "new.sorted",
    "new.copy-sort",
    "new.slice-sort",
    "new.bielsort",
    "in-place.list-sort",
    "in-place.bielsort",
)


def create_case(name, size, seed):
    """Create a deterministic, nearly ordered fallback workload."""
    if size < 2:
        raise ValueError("size must be at least 2")

    values = list(range(size))
    rng = random.Random(seed)
    disruptions = max(1, size // 500)

    if name == "ordered":
        return values
    if name == "adjacent-swaps":
        for _ in range(disruptions):
            index = rng.randrange(size - 1)
            values[index], values[index + 1] = (
                values[index + 1],
                values[index],
            )
        return values
    if name == "random-swaps":
        for _ in range(disruptions):
            left = rng.randrange(size)
            right = rng.randrange(size)
            values[left], values[right] = values[right], values[left]
        return values
    raise ValueError(f"unknown case: {name}")


def _copy_sort(values):
    result = values.copy()
    result.sort()
    return result


def _slice_sort(values):
    result = values[:]
    result.sort()
    return result


def _list_sort(values):
    returned = values.sort()
    if returned is not None:
        raise AssertionError("list.sort() did not return None")
    return values


def _bielsort_in_place(values):
    returned = bielsort.sort_in_place(values)
    if returned is not None:
        raise AssertionError("bielsort.sort_in_place() did not return None")
    return values


def _operations(values, expected):
    no_preparation = lambda: None
    return {
        "copy.list-copy": (
            no_preparation,
            lambda _: values.copy(),
            values,
        ),
        "copy.list-slice": (
            no_preparation,
            lambda _: values[:],
            values,
        ),
        "new.sorted": (
            no_preparation,
            lambda _: sorted(values),
            expected,
        ),
        "new.copy-sort": (
            no_preparation,
            lambda _: _copy_sort(values),
            expected,
        ),
        "new.slice-sort": (
            no_preparation,
            lambda _: _slice_sort(values),
            expected,
        ),
        "new.bielsort": (
            no_preparation,
            lambda _: bielsort.sort(values),
            expected,
        ),
        "in-place.list-sort": (
            values.copy,
            _list_sort,
            expected,
        ),
        "in-place.bielsort": (
            values.copy,
            _bielsort_in_place,
            expected,
        ),
    }


def measure_case(name, values, repetitions, seed):
    """Return raw samples, medians, strategies, and derived overheads."""
    expected = sorted(values)
    diagnostic_result, strategy = bielsort.sort_with_strategy(values)
    if diagnostic_result != expected:
        raise AssertionError("incorrect diagnostic BielSort result")
    if not strategy.startswith("timsort:"):
        raise AssertionError(
            f"fallback profiler received native strategy: {strategy}"
        )
    del diagnostic_result

    operations = _operations(values, expected)
    samples = {operation: [] for operation in OPERATION_NAMES}
    order_rng = random.Random(seed)

    for _ in range(repetitions):
        order = list(OPERATION_NAMES)
        order_rng.shuffle(order)
        for operation in order:
            prepare, run, expected_result = operations[operation]
            prepared = prepare()
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter_ns()
                result = run(prepared)
                elapsed = time.perf_counter_ns() - started
            finally:
                gc.enable()

            if result != expected_result:
                raise AssertionError(f"incorrect result from {operation}")
            samples[operation].append(elapsed)
            # Keep output destruction out of the next operation's timer.
            # This matters especially when operation order is randomized.
            del result

    medians = {
        operation: int(statistics.median(timings))
        for operation, timings in samples.items()
    }
    new_bielsort = medians["new.bielsort"]
    new_sorted = medians["new.sorted"]
    in_place_bielsort = medians["in-place.bielsort"]
    in_place_list_sort = medians["in-place.list-sort"]

    return {
        "case": name,
        "description": CASE_DESCRIPTIONS[name],
        "size": len(values),
        "strategy": strategy,
        "disruptions": 0 if name == "ordered" else max(1, len(values) // 500),
        "samples_ns": samples,
        "median_ns": medians,
        "derived": {
            "new_bielsort_over_sorted_ns": new_bielsort - new_sorted,
            "new_bielsort_speedup_vs_sorted": new_sorted / new_bielsort,
            "new_dispatch_estimate_vs_slice_sort_ns": (
                new_bielsort - medians["new.slice-sort"]
            ),
            "in_place_bielsort_over_list_sort_ns": (
                in_place_bielsort - in_place_list_sort
            ),
            "in_place_bielsort_speedup_vs_list_sort": (
                in_place_list_sort / in_place_bielsort
            ),
        },
    }


def environment_metadata():
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "bielsort": bielsort.__version__,
    }


def run_profile(
    sizes,
    repetitions,
    cases,
    show_table=True,
    context=None,
):
    """Run the fallback profile and return a JSON-serializable report."""
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    results = []
    if show_table:
        print(
            f"{'n':>10}  {'case':<17}  {'sorted':>10}  {'Biel new':>10}"
            f"  {'delta':>10}  {'gain':>7}  {'list.sort':>10}"
            f"  {'Biel ip':>10}  {'delta':>10}  {'gain':>7}"
        )
        print("-" * 125)

    for size in sizes:
        for case_index, case in enumerate(cases):
            seed = 20_260_731 + size + case_index
            values = create_case(case, size, seed)
            result = measure_case(case, values, repetitions, seed)
            results.append(result)

            if show_table:
                medians = result["median_ns"]
                derived = result["derived"]
                print(
                    f"{size:>10,}  {case:<17}"
                    f"  {medians['new.sorted'] / 1e6:>9.4f}ms"
                    f"  {medians['new.bielsort'] / 1e6:>9.4f}ms"
                    f"  {derived['new_bielsort_over_sorted_ns'] / 1e6:>+9.4f}ms"
                    f"  {derived['new_bielsort_speedup_vs_sorted']:>6.2f}x"
                    f"  {medians['in-place.list-sort'] / 1e6:>9.4f}ms"
                    f"  {medians['in-place.bielsort'] / 1e6:>9.4f}ms"
                    f"  {derived['in_place_bielsort_over_list_sort_ns'] / 1e6:>+9.4f}ms"
                    f"  {derived['in_place_bielsort_speedup_vs_list_sort']:>6.2f}x"
                )

    return {
        "schema_version": 1,
        "suite": "fallback-overhead",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": environment_metadata(),
        "configuration": {
            "context": context,
            "sizes": list(sizes),
            "repetitions": repetitions,
            "cases": list(cases),
            "timing_policy": (
                "median perf_counter_ns; deterministic interleaved operation "
                "order; in-place input copies and output destruction outside "
                "timing"
            ),
        },
        "results": results,
    }


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Profile BielSort's nearly ordered Timsort fallback."
    )
    parser.add_argument(
        "-n",
        "--sizes",
        nargs="+",
        type=int,
        default=[10_000, 100_000, 1_000_000],
    )
    parser.add_argument("-r", "--repetitions", type=int, default=15)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=tuple(CASE_DESCRIPTIONS),
        default=list(CASE_DESCRIPTIONS),
    )
    parser.add_argument("--context")
    parser.add_argument("--json", type=Path, metavar="PATH")
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    print(
        "Timsort fallback overhead; medians of "
        f"{arguments.repetitions} interleaved runs. Gains above 1.00x favor "
        "BielSort."
    )
    report = run_profile(
        arguments.sizes,
        arguments.repetitions,
        arguments.cases,
        context=arguments.context,
    )
    if arguments.json:
        arguments.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote report to {arguments.json}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, ValueError) as error:
        raise SystemExit(str(error)) from error
