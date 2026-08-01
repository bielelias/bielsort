"""Evaluate BielSort on a user-owned workload without exporting raw values.

The provider is a local Python file containing a zero-argument callable that
returns the exact list to evaluate. This script never uploads data.
"""

import argparse
import gc
import importlib.util
import json
import os
import platform
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import bielsort


REPORT_SCHEMA_VERSION = 1
DEFAULT_SEED = 20_260_803
DEFAULT_SAMPLE_SIZE = 2_048
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
USE_CASE_URL = (
    "https://github.com/bielelias/bielsort/issues/new?template=use_case.yml"
)

OPERATION_NAMES = (
    "new.sorted",
    "new.bielsort",
    "in-place.list-sort",
    "in-place.bielsort",
)


def load_provider(provider_spec):
    """Load ``PATH:CALLABLE`` and return the callable without retaining PATH."""
    path_text, separator, callable_name = provider_spec.rpartition(":")
    if not separator or not path_text or not callable_name:
        raise ValueError("provider must use the PATH:CALLABLE format")

    provider_path = Path(path_text).expanduser().resolve()
    if not provider_path.is_file():
        raise ValueError("provider file does not exist")

    module_name = "_bielsort_private_workload_provider"
    spec = importlib.util.spec_from_file_location(module_name, provider_path)
    if spec is None or spec.loader is None:
        raise ValueError("could not load provider file")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    provider = getattr(module, callable_name, None)
    if not callable(provider):
        raise ValueError("provider callable was not found")
    return provider


def _sample_evenly(values, sample_size):
    if sample_size < 2:
        raise ValueError("sample_size must be at least 2")
    size = len(values)
    if size <= sample_size:
        return list(values)
    return [
        values[(index * (size - 1)) // (sample_size - 1)]
        for index in range(sample_size)
    ]


def describe_workload(values, sample_size=DEFAULT_SAMPLE_SIZE, minimal=False):
    """Return aggregate shape metadata without retaining raw workload values."""
    if type(values) is not list:
        raise TypeError("the workload provider must return an exact list")
    if len(values) < 2:
        raise ValueError("the workload must contain at least two elements")
    description = {
        "container": "list",
        "size": len(values),
        "raw_values_included": False,
    }
    if minimal:
        description["distribution_metadata"] = "omitted by user"
        return description

    sample = _sample_evenly(values, sample_size)
    exact_ints = [value for value in sample if type(value) is int]
    sample_count = len(sample)
    exact_int_count = len(exact_ints)
    description.update(
        {
            "sample_size": sample_count,
            "sample_exact_int_ratio": exact_int_count / sample_count,
        }
    )

    if exact_int_count != sample_count:
        description["integer_distribution"] = "not computed for mixed types"
        return description

    transitions = max(1, sample_count - 1)
    nondecreasing = sum(
        sample[index - 1] <= sample[index]
        for index in range(1, sample_count)
    )
    nonincreasing = sum(
        sample[index - 1] >= sample[index]
        for index in range(1, sample_count)
    )
    signed_64_count = sum(INT64_MIN <= value <= INT64_MAX for value in sample)
    bit_lengths = [value.bit_length() for value in sample]
    description.update(
        {
            "sample_duplicate_ratio": 1.0 - len(set(sample)) / sample_count,
            "sample_nondecreasing_transition_ratio": nondecreasing / transitions,
            "sample_nonincreasing_transition_ratio": nonincreasing / transitions,
            "sample_signed_int64_ratio": signed_64_count / sample_count,
            "sample_negative_ratio": (
                sum(value < 0 for value in sample) / sample_count
            ),
            "sample_min_bit_length": min(bit_lengths),
            "sample_max_bit_length": max(bit_lengths),
        }
    )
    return description


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


def _operations(values):
    no_preparation = lambda: None
    return {
        "new.sorted": (no_preparation, lambda _: sorted(values)),
        "new.bielsort": (no_preparation, lambda _: bielsort.sort(values)),
        "in-place.list-sort": (values.copy, _list_sort),
        "in-place.bielsort": (values.copy, _bielsort_in_place),
    }


def _execute_once(prepare, run, expected, operation):
    prepared = prepare()
    result = run(prepared)
    if result != expected:
        raise AssertionError(f"incorrect result from {operation}")
    del result
    del prepared


def _measure_once(prepare, run, expected, operation):
    prepared = prepare()
    gc.collect()
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        started = time.perf_counter_ns()
        result = run(prepared)
        elapsed = time.perf_counter_ns() - started
    finally:
        if gc_was_enabled:
            gc.enable()

    if result != expected:
        raise AssertionError(f"incorrect result from {operation}")

    # Destroy outputs and prepared in-place copies before the next timer.
    del result
    del prepared
    return elapsed


def measure_operations(values, expected, repetitions, warmups, seed):
    """Return raw nanosecond samples in deterministic interleaved order."""
    if repetitions < 3 or repetitions % 2 == 0:
        raise ValueError("repetitions must be an odd number of at least 3")
    if warmups < 0:
        raise ValueError("warmups must be at least 0")

    operations = _operations(values)
    for _ in range(warmups):
        for operation in OPERATION_NAMES:
            prepare, run = operations[operation]
            _execute_once(prepare, run, expected, operation)

    samples = {operation: [] for operation in OPERATION_NAMES}
    order_rng = random.Random(seed)
    for _ in range(repetitions):
        order = list(OPERATION_NAMES)
        order_rng.shuffle(order)
        for operation in order:
            prepare, run = operations[operation]
            elapsed = _measure_once(
                prepare,
                run,
                expected,
                operation,
            )
            samples[operation].append(elapsed)
    return samples


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


def evaluate_workload(
    values,
    label="anonymous-workload",
    repetitions=7,
    warmups=1,
    seed=DEFAULT_SEED,
    sample_size=DEFAULT_SAMPLE_SIZE,
    minimal_metadata=False,
):
    """Evaluate one exact list and return a privacy-preserving report."""
    if type(values) is not list:
        raise TypeError("the workload provider must return an exact list")
    if len(values) < 2:
        raise ValueError("the workload must contain at least two elements")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("label must be a non-empty string")

    workload = describe_workload(
        values,
        sample_size=sample_size,
        minimal=minimal_metadata,
    )
    expected = sorted(values)
    diagnostic_result, strategy = bielsort.sort_with_strategy(values)
    if diagnostic_result != expected:
        raise AssertionError("diagnostic BielSort result differs from sorted()")
    del diagnostic_result

    samples = measure_operations(
        values,
        expected,
        repetitions,
        warmups,
        seed,
    )
    medians = {
        operation: int(statistics.median(timings))
        for operation, timings in samples.items()
    }
    new_speedup = medians["new.sorted"] / medians["new.bielsort"]
    in_place_speedup = (
        medians["in-place.list-sort"] / medians["in-place.bielsort"]
    )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "suite": "bielsort-workload-evaluator",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "raw_values_included": False,
            "provider_path_included": False,
            "automatic_upload": False,
            "review_before_sharing": True,
        },
        "environment": environment_metadata(),
        "configuration": {
            "label": label.strip(),
            "repetitions": repetitions,
            "warmups": warmups,
            "seed": seed,
            "sample_size_limit": sample_size,
            "minimal_metadata": minimal_metadata,
            "timing_policy": (
                "median perf_counter_ns; deterministic interleaved order; "
                "in-place copies, correctness checks, and output destruction "
                "outside timed intervals"
            ),
        },
        "workload": workload,
        "strategy": {
            "description": strategy,
            "native_fast_path": strategy.startswith(
                ("counting nativo", "radix nativo")
            ),
        },
        "correctness": {
            "reference": "sorted()",
            "all_results_matched": True,
        },
        "samples_ns": samples,
        "median_ns": medians,
        "comparison": {
            "new_list_speedup_vs_sorted": new_speedup,
            "in_place_speedup_vs_list_sort": in_place_speedup,
            "new_list_winner": (
                "bielsort"
                if medians["new.bielsort"] < medians["new.sorted"]
                else "sorted"
            ),
            "in_place_winner": (
                "bielsort"
                if medians["in-place.bielsort"]
                < medians["in-place.list-sort"]
                else "list.sort"
            ),
        },
    }


def _milliseconds(nanoseconds):
    return f"{nanoseconds / 1_000_000:.4f}"


def render_markdown(report):
    """Render a report that can be reviewed before attaching to GitHub."""
    environment = report["environment"]
    configuration = report["configuration"]
    workload = report["workload"]
    strategy = report["strategy"]
    medians = report["median_ns"]
    comparison = report["comparison"]

    lines = [
        "# BielSort workload evaluation",
        "",
        "> [!IMPORTANT]",
        "> Review this report before sharing it. It contains aggregate shape",
        "> metadata and timings, but no raw workload values or provider path.",
        "",
        f"- Label: `{configuration['label']}`",
        f"- Elements: **{workload['size']:,}**",
        f"- Strategy: `{strategy['description']}`",
        f"- Native fast path: **{'yes' if strategy['native_fast_path'] else 'no'}**",
        f"- Repetitions: **{configuration['repetitions']}**",
        "",
        "## Environment",
        "",
        "| Python | BielSort | Platform | Machine |",
        "|---:|---:|---|---|",
        (
            f"| {environment['python']} | {environment['bielsort']} | "
            f"{environment['platform']} | {environment['machine']} |"
        ),
        "",
        "## Median timings",
        "",
        "| API shape | Baseline (ms) | BielSort (ms) | Speedup | Winner |",
        "|---|---:|---:|---:|---|",
        (
            f"| New list | {_milliseconds(medians['new.sorted'])} | "
            f"{_milliseconds(medians['new.bielsort'])} | "
            f"{comparison['new_list_speedup_vs_sorted']:.2f}× | "
            f"{comparison['new_list_winner']} |"
        ),
        (
            f"| In place | {_milliseconds(medians['in-place.list-sort'])} | "
            f"{_milliseconds(medians['in-place.bielsort'])} | "
            f"{comparison['in_place_speedup_vs_list_sort']:.2f}× | "
            f"{comparison['in_place_winner']} |"
        ),
        "",
        "## Aggregate workload metadata",
        "",
        "```json",
        json.dumps(workload, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Interpretation",
        "",
        "- All measured results matched `sorted()`.",
        "- A speedup above 1.00× favors BielSort.",
        "- Measure total application impact and peak memory before adoption.",
        "- Wins and losses are equally useful to the project.",
        "",
        f"Share reviewed results: {USE_CASE_URL}",
        "",
    ]
    return "\n".join(lines)


def write_reports(report, json_path, markdown_path):
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a private local workload without exporting raw values."
        )
    )
    parser.add_argument(
        "provider",
        help="local zero-argument provider in PATH:CALLABLE format",
    )
    parser.add_argument("--label", default="anonymous-workload")
    parser.add_argument("-r", "--repetitions", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument(
        "--minimal-metadata",
        action="store_true",
        help="omit sampled distribution statistics from the report",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("bielsort-workload-report.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("bielsort-workload-report.md"),
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    provider = load_provider(arguments.provider)
    print("Loading the workload locally; no values will be uploaded or saved.")
    values = provider()
    if type(values) is list:
        print(f"Loaded {len(values):,} elements. Starting evaluation.")
        print(
            "Keep memory headroom: the evaluator retains a sorted reference "
            "and creates one candidate result at a time."
        )

    report = evaluate_workload(
        values,
        label=arguments.label,
        repetitions=arguments.repetitions,
        warmups=arguments.warmups,
        seed=arguments.seed,
        sample_size=arguments.sample_size,
        minimal_metadata=arguments.minimal_metadata,
    )
    write_reports(report, arguments.json, arguments.markdown)

    comparison = report["comparison"]
    print(
        "Evaluation complete. New-list speedup: "
        f"{comparison['new_list_speedup_vs_sorted']:.2f}x; in-place speedup: "
        f"{comparison['in_place_speedup_vs_list_sort']:.2f}x."
    )
    print(f"Review before sharing: {arguments.json} and {arguments.markdown}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, TypeError, ValueError) as error:
        raise SystemExit(f"Evaluation failed: {error}") from error
