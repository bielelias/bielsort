"""Evaluate the frozen compact reusable reorder-plan candidate end to end.

The protocol is frozen in ``docs/reorder-plan-api-review.md``.  The primary
timed operation constructs one stable order from an ordinary Python key list
and returns every aligned column as an ordinary Python list.  The separate
NumPy-resident control starts and ends with arrays and is not a promotion
gate.
"""

import argparse
import gc
import importlib.metadata
import json
import platform
import random
import statistics
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

try:
    import resource
except ImportError:  # pragma: no cover - unavailable on Windows
    resource = None

try:
    import more_itertools
except ImportError:  # pragma: no cover - optional benchmark dependency
    more_itertools = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional benchmark dependency
    np = None

from bielsort_native._reorder_plan import argsort


PYTHON = "python-indices"
CANDIDATE = "biel-reorder-plan"
SORT_TOGETHER = "more-itertools-sort-together"
NUMPY_E2E = "numpy-python-e2e"
NUMPY_RESIDENT = "numpy-resident"
ALGORITHMS = (
    PYTHON,
    CANDIDATE,
    SORT_TOGETHER,
    NUMPY_E2E,
    NUMPY_RESIDENT,
)

EVENT = "event-batch"
EVENT_NEARLY = "event-batch-nearly-ordered"
RANKING = "ranking-export"
SIMULATION = "simulation-columns"
WORKLOADS = (EVENT, EVENT_NEARLY, RANKING, SIMULATION)
DISORDERED_WORKLOADS = frozenset((EVENT, RANKING, SIMULATION))

CANONICAL_SIZES = (10_000, 100_000, 1_000_000)
CANONICAL_REPETITIONS = 7
CANONICAL_MEMORY_REPETITIONS = 3
BASE_SEED = 80_600


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def peak_rss_bytes():
    if resource is None:
        raise RuntimeError("isolated peak RSS requires Linux or macOS")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def rotate(items, offset):
    offset %= len(items)
    return items[offset:] + items[:offset]


def workload_seed(workload, size):
    return BASE_SEED + WORKLOADS.index(workload) * 10_000_000 + size


def repeated_objects(size, period):
    sentinels = [object() for _ in range(period)]
    return [sentinels[index % period] for index in range(size)]


def create_workload(workload, size, seed):
    rng = random.Random(seed)
    if workload == EVENT:
        keys = [
            rng.randint(-(1 << 63), (1 << 63) - 1)
            for _ in range(size)
        ]
        if size >= 2:
            keys[0] = -(1 << 63)
            keys[1] = (1 << 63) - 1
        columns = [keys, repeated_objects(size, 257)]
        reverse = False
    elif workload == EVENT_NEARLY:
        keys = list(range(size))
        for _ in range(max(1, size // 500)):
            left = rng.randrange(size)
            right = rng.randrange(size)
            keys[left], keys[right] = keys[right], keys[left]
        columns = [keys, repeated_objects(size, 257)]
        reverse = False
    elif workload == RANKING:
        maximum = max(20, size // 100)
        keys = [rng.randint(0, maximum) for _ in range(size)]
        identifiers = list(range(size))
        metadata = repeated_objects(size, 193)
        columns = [keys, identifiers, metadata]
        reverse = True
    elif workload == SIMULATION:
        keys = [
            rng.randint(-(1 << 31), (1 << 31) - 1)
            for _ in range(size)
        ]
        row_ids = list(range(size))
        groups = [index % 97 for index in range(size)]
        payloads = repeated_objects(size, 251)
        labels = [f"phase-{index % 31:02d}" for index in range(size)]
        columns = [keys, row_ids, groups, payloads, labels]
        reverse = False
    else:
        raise ValueError(f"unknown workload: {workload}")
    return {
        "name": workload,
        "size": size,
        "seed": seed,
        "keys": keys,
        "columns": columns,
        "reverse": reverse,
    }


def stable_numpy_order(keys_array, reverse):
    if not reverse:
        return np.argsort(keys_array, kind="stable")
    if np.any(keys_array == np.iinfo(np.int64).min):
        raise ValueError(
            "the descending NumPy baseline cannot negate INT64_MIN"
        )
    return np.argsort(-keys_array, kind="stable")


def to_object_array(sequence):
    array = np.empty(len(sequence), dtype=object)
    array[:] = sequence
    return array


def prepare_resident_arrays(workload):
    if np is None:
        return None
    keys = np.asarray(workload["keys"], dtype=np.int64)
    return [
        keys,
        *[
            to_object_array(column)
            for column in workload["columns"][1:]
        ],
    ]


def run_algorithm(algorithm, workload, resident_arrays=None):
    keys = workload["keys"]
    columns = workload["columns"]
    reverse = workload["reverse"]
    if algorithm == PYTHON:
        order = sorted(
            range(len(keys)),
            key=keys.__getitem__,
            reverse=reverse,
        )
        outputs = [
            [column[index] for index in order]
            for column in columns
        ]
        return order, outputs
    if algorithm == CANDIDATE:
        order = argsort(keys, reverse=reverse)
        return order, [order.apply(column) for column in columns]
    if algorithm == SORT_TOGETHER:
        if more_itertools is None:
            raise RuntimeError(
                "more-itertools is unavailable; install the benchmark extra"
            )
        outputs = more_itertools.sort_together(
            columns,
            key_list=(0,),
            reverse=reverse,
            strict=True,
        )
        return None, [list(output) for output in outputs]
    if algorithm == NUMPY_E2E:
        if np is None:
            raise RuntimeError(
                "NumPy is unavailable; install the benchmark extra"
            )
        keys_array = np.asarray(keys, dtype=np.int64)
        order = stable_numpy_order(keys_array, reverse)
        arrays = [to_object_array(column) for column in columns]
        return order, [array[order].tolist() for array in arrays]
    if algorithm == NUMPY_RESIDENT:
        if np is None:
            raise RuntimeError(
                "NumPy is unavailable; install the benchmark extra"
            )
        if resident_arrays is None:
            raise AssertionError("NumPy-resident requires prepared arrays")
        order = stable_numpy_order(resident_arrays[0], reverse)
        return order, [array[order] for array in resident_arrays]
    raise ValueError(f"unknown algorithm: {algorithm}")


def expected_order(workload):
    keys = workload["keys"]
    return sorted(
        range(len(keys)),
        key=keys.__getitem__,
        reverse=workload["reverse"],
    )


def ensure_python_outputs(order, outputs, workload, expected):
    if order is not None and list(order) != expected:
        raise AssertionError("algorithm returned an incorrect stable order")
    columns = workload["columns"]
    if len(outputs) != len(columns):
        raise AssertionError("algorithm returned an incorrect column count")
    for output, source in zip(outputs, columns):
        if len(output) != len(expected):
            raise AssertionError("algorithm returned an incorrect row count")
        if any(
            item is not source[index]
            for item, index in zip(output, expected)
        ):
            raise AssertionError("algorithm did not preserve exact identity")


def ensure_resident_outputs(order, outputs, resident_arrays, expected):
    expected_array = np.asarray(expected, dtype=np.intp)
    if not np.array_equal(order, expected_array):
        raise AssertionError("NumPy-resident returned an incorrect order")
    if len(outputs) != len(resident_arrays):
        raise AssertionError("NumPy-resident returned a wrong column count")
    for output, source in zip(outputs, resident_arrays):
        if not np.array_equal(output, source[expected_array]):
            raise AssertionError("NumPy-resident returned incorrect values")


def selected_algorithms(include_optional=True):
    algorithms = [PYTHON, CANDIDATE]
    if include_optional:
        if more_itertools is None:
            raise RuntimeError(
                "canonical comparison requires more-itertools"
            )
        if np is None:
            raise RuntimeError("canonical comparison requires NumPy")
        algorithms.extend((SORT_TOGETHER, NUMPY_E2E, NUMPY_RESIDENT))
    return algorithms


def validate_result(
    algorithm,
    order,
    outputs,
    workload,
    resident_arrays,
    expected,
):
    if algorithm == NUMPY_RESIDENT:
        ensure_resident_outputs(
            order,
            outputs,
            resident_arrays,
            expected,
        )
    else:
        ensure_python_outputs(order, outputs, workload, expected)


def measure_workload(workload, repetitions, algorithms, rotation_offset):
    expected = expected_order(workload)
    resident_arrays = (
        prepare_resident_arrays(workload)
        if NUMPY_RESIDENT in algorithms
        else None
    )
    samples = {algorithm: [] for algorithm in algorithms}
    execution_order = []
    for repetition in range(repetitions):
        order_this_round = rotate(
            algorithms,
            repetition + rotation_offset,
        )
        execution_order.append(order_this_round)
        for algorithm in order_this_round:
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                order, outputs = run_algorithm(
                    algorithm,
                    workload,
                    resident_arrays,
                )
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            validate_result(
                algorithm,
                order,
                outputs,
                workload,
                resident_arrays,
                expected,
            )
            samples[algorithm].append(elapsed)
            del order, outputs
            gc.collect()

    medians = {
        algorithm: statistics.median(values)
        for algorithm, values in samples.items()
    }
    candidate = medians[CANDIDATE]
    speedups = {
        algorithm: median / candidate
        for algorithm, median in medians.items()
        if algorithm != CANDIDATE
    }
    return {
        "workload": workload["name"],
        "size": workload["size"],
        "seed": workload["seed"],
        "sequence_count": len(workload["columns"]),
        "reverse": workload["reverse"],
        "samples_s": samples,
        "medians_s": medians,
        "candidate_speedup_over": speedups,
        "execution_order": execution_order,
    }


def run_time_matrix(sizes, repetitions, workloads, algorithms):
    print("COMPLETE REORDER FLOW (median seconds; speedup favors BielSort)")
    print(
        f"{'n':>10}  {'workload':<28}  {'Python':>9}  {'Biel':>9}  "
        f"{'more-it':>9}  {'NumPy E2E':>9}  {'B/Py':>7}"
    )
    print("-" * 102)
    rows = []
    for size in sizes:
        for workload_index, workload_name in enumerate(workloads):
            workload = create_workload(
                workload_name,
                size,
                workload_seed(workload_name, size),
            )
            row = measure_workload(
                workload,
                repetitions,
                algorithms,
                workload_index + size,
            )
            rows.append(row)
            medians = row["medians_s"]
            more_value = medians.get(SORT_TOGETHER, float("nan"))
            numpy_value = medians.get(NUMPY_E2E, float("nan"))
            print(
                f"{size:>10,}  {workload_name:<28}  "
                f"{medians[PYTHON]:>8.4f}s  {medians[CANDIDATE]:>8.4f}s  "
                f"{more_value:>8.4f}s  {numpy_value:>8.4f}s  "
                f"{row['candidate_speedup_over'][PYTHON]:>6.2f}x"
            )
            del workload
            gc.collect()
    return rows


def memory_worker(algorithm, workload_name, size, seed):
    workload = create_workload(workload_name, size, seed)
    resident_arrays = (
        prepare_resident_arrays(workload)
        if algorithm == NUMPY_RESIDENT
        else None
    )
    gc.collect()
    baseline = peak_rss_bytes()
    started = time.perf_counter()
    order, outputs = run_algorithm(algorithm, workload, resident_arrays)
    elapsed = time.perf_counter() - started
    incremental_peak = max(0, peak_rss_bytes() - baseline)
    expected = expected_order(workload)
    validate_result(
        algorithm,
        order,
        outputs,
        workload,
        resident_arrays,
        expected,
    )
    result = {
        "algorithm": algorithm,
        "workload": workload_name,
        "size": size,
        "seed": seed,
        "elapsed_s": elapsed,
        "incremental_peak_bytes": incremental_peak,
    }
    if algorithm == CANDIDATE:
        view = memoryview(order)
        result["permutation"] = {
            "format": view.format,
            "itemsize": view.itemsize,
            "payload_bytes": view.nbytes,
            "readonly": view.readonly,
        }
    return result


def invoke_memory_worker(algorithm, workload, size, seed):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        algorithm,
        workload,
        str(size),
        str(seed),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def run_memory_matrix(size, repetitions, workloads, algorithms):
    print("\nISOLATED INCREMENTAL PEAK RSS (median MiB)")
    print(
        f"{'workload':<28}  {'Python':>9}  {'Biel':>9}  "
        f"{'more-it':>9}  {'B/Py':>7}"
    )
    print("-" * 72)
    rows = []
    for workload_name in workloads:
        raw = {}
        medians = {}
        for algorithm in algorithms:
            samples = [
                invoke_memory_worker(
                    algorithm,
                    workload_name,
                    size,
                    workload_seed(workload_name, size) + repetition,
                )
                for repetition in range(repetitions)
            ]
            raw[algorithm] = samples
            medians[algorithm] = statistics.median(
                sample["incremental_peak_bytes"] for sample in samples
            )
        candidate = medians[CANDIDATE]
        ratios = {
            algorithm: (
                candidate / peak if peak else None
            )
            for algorithm, peak in medians.items()
            if algorithm != CANDIDATE
        }
        row = {
            "workload": workload_name,
            "size": size,
            "median_incremental_peak_bytes": medians,
            "candidate_memory_ratio_to": ratios,
            "raw": raw,
        }
        rows.append(row)
        more_peak = medians.get(SORT_TOGETHER, float("nan"))
        python_ratio = ratios[PYTHON]
        print(
            f"{workload_name:<28}  {medians[PYTHON] / 2**20:>8.2f}  "
            f"{candidate / 2**20:>8.2f}  {more_peak / 2**20:>8.2f}  "
            f"{python_ratio if python_ratio is not None else float('nan'):>6.2f}x"
        )
    return rows


def time_row_map(rows):
    return {(row["workload"], row["size"]): row for row in rows}


def evaluate_time_gates(rows):
    mapped = time_row_map(rows)
    target_rows = [
        mapped[(workload, size)]
        for workload in DISORDERED_WORKLOADS
        for size in (100_000, 1_000_000)
    ]
    large_rows = [
        mapped[(workload, size)]
        for workload in WORKLOADS
        for size in (100_000, 1_000_000)
    ]
    small_rows = [mapped[(workload, 10_000)] for workload in WORKLOADS]
    nearly_rows = [
        mapped[(EVENT_NEARLY, size)]
        for size in (100_000, 1_000_000)
    ]

    direct_target_count = sum(
        row["candidate_speedup_over"][PYTHON] >= 1.50
        for row in target_rows
    )
    direct_floor = all(
        row["candidate_speedup_over"][PYTHON] >= 0.85
        for row in target_rows
    )
    nearly_floor = all(
        row["candidate_speedup_over"][PYTHON] >= 0.85
        for row in nearly_rows
    )
    small_floor = all(
        row["candidate_speedup_over"][PYTHON] >= 0.80
        for row in small_rows
    )

    more_target_count = sum(
        row["candidate_speedup_over"][SORT_TOGETHER] >= 1.25
        for row in target_rows
    )
    more_floor = all(
        row["candidate_speedup_over"][SORT_TOGETHER] >= 0.85
        for row in large_rows
    )

    numpy_target_count = sum(
        row["candidate_speedup_over"][NUMPY_E2E] >= 1.00
        for row in target_rows
    )
    numpy_floor = all(
        row["candidate_speedup_over"][NUMPY_E2E] >= 0.80
        for row in target_rows
    )

    direct_passed = (
        direct_target_count >= 5
        and direct_floor
        and nearly_floor
        and small_floor
    )
    more_passed = more_target_count >= 5 and more_floor
    numpy_passed = numpy_target_count >= 4 and numpy_floor
    return {
        "passed": direct_passed and more_passed and numpy_passed,
        "direct_python": {
            "passed": direct_passed,
            "target_count_at_least_1_50x": direct_target_count,
            "target_required": 5,
            "disordered_large_floor_passed": direct_floor,
            "nearly_ordered_floor_passed": nearly_floor,
            "small_input_floor_passed": small_floor,
        },
        "sort_together": {
            "passed": more_passed,
            "target_count_at_least_1_25x": more_target_count,
            "target_required": 5,
            "large_floor_passed": more_floor,
        },
        "numpy_python_e2e": {
            "passed": numpy_passed,
            "target_count_at_least_1_00x": numpy_target_count,
            "target_required": 4,
            "disordered_large_floor_passed": numpy_floor,
        },
    }


def evaluate_memory_gates(rows):
    mapped = {row["workload"]: row for row in rows}
    targets = [mapped[workload] for workload in DISORDERED_WORKLOADS]
    all_rows = [mapped[workload] for workload in WORKLOADS]
    python_reduction_count = sum(
        row["candidate_memory_ratio_to"][PYTHON] is not None
        and row["candidate_memory_ratio_to"][PYTHON] <= 0.70
        for row in targets
    )
    more_reduction_count = sum(
        row["candidate_memory_ratio_to"][SORT_TOGETHER] is not None
        and row["candidate_memory_ratio_to"][SORT_TOGETHER] <= 0.70
        for row in targets
    )
    python_floor = all(
        row["candidate_memory_ratio_to"][PYTHON] is not None
        and row["candidate_memory_ratio_to"][PYTHON] <= 1.10
        for row in all_rows
    )
    more_floor = all(
        row["candidate_memory_ratio_to"][SORT_TOGETHER] is not None
        and row["candidate_memory_ratio_to"][SORT_TOGETHER] <= 1.10
        for row in all_rows
    )
    payload_passed = all(
        sample["permutation"]["payload_bytes"] == row["size"] * 4
        and sample["permutation"]["itemsize"] == 4
        and sample["permutation"]["readonly"]
        for row in rows
        for sample in row["raw"][CANDIDATE]
    )
    passed = (
        python_reduction_count >= 2
        and more_reduction_count >= 2
        and python_floor
        and more_floor
        and payload_passed
    )
    return {
        "passed": passed,
        "direct_python": {
            "reduction_count_at_most_0_70x": python_reduction_count,
            "required": 2,
            "regression_floor_passed": python_floor,
        },
        "sort_together": {
            "reduction_count_at_most_0_70x": more_reduction_count,
            "required": 2,
            "regression_floor_passed": more_floor,
        },
        "compact_payload_passed": payload_passed,
    }


def git_state():
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": dirty}


def cpu_description():
    path = Path("/proc/cpuinfo")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def environment_metadata():
    return {
        "python": sys.version,
        "python_compiler": platform.python_compiler(),
        "python_cflags": sysconfig.get_config_var("CFLAGS"),
        "project_optimized_compile_flags": ["-O3"],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu_description(),
        "numpy": None if np is None else np.__version__,
        "more_itertools": package_version("more-itertools"),
    }


def render_markdown(payload, json_name):
    time_gate = payload["decision"]["time"]
    memory_gate = payload["decision"]["memory"]
    local_passed = payload["decision"]["local_performance_passed"]
    lines = [
        "# Reusable reorder-plan canonical result — 2026-08-06",
        "",
        "## Decision",
        "",
        (
            "**The frozen local time and memory gates pass.**"
            if local_passed
            else "**The frozen local time and memory gates do not pass.**"
        ),
        "",
        "This result evaluates a private candidate. It does not add a public",
        "`argsort` or `Permutation`, approve a release, or establish external",
        "market demand. Hosted portability and final API review remain separate",
        "promotion gates.",
        "",
        "## Complete-flow timing",
        "",
        "Medians include construction of one order and application to every",
        "aligned column. Higher speedup values favor BielSort.",
        "",
        "| n | Workload | Python | Biel | `sort_together` | NumPy E2E | "
        "Biel/Python | Biel/`sort_together` | Biel/NumPy E2E |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["time_rows"]:
        medians = row["medians_s"]
        speedups = row["candidate_speedup_over"]
        lines.append(
            f"| {row['size']:,} | {row['workload']} | "
            f"{medians[PYTHON]:.6f} s | {medians[CANDIDATE]:.6f} s | "
            f"{medians[SORT_TOGETHER]:.6f} s | "
            f"{medians[NUMPY_E2E]:.6f} s | "
            f"{speedups[PYTHON]:.2f}x | "
            f"{speedups[SORT_TOGETHER]:.2f}x | "
            f"{speedups[NUMPY_E2E]:.2f}x |"
        )
    lines.extend(
        [
            "",
            "The NumPy-resident control is retained in the raw JSON. It begins",
            "and ends with arrays and is deliberately not a BielSort gate.",
            "",
            "## Incremental peak RSS at one million records",
            "",
            "| Workload | Python | Biel | `sort_together` | Biel/Python | "
            "Biel/`sort_together` |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["memory_rows"]:
        medians = row["median_incremental_peak_bytes"]
        ratios = row["candidate_memory_ratio_to"]
        lines.append(
            f"| {row['workload']} | {medians[PYTHON] / 2**20:.2f} MiB | "
            f"{medians[CANDIDATE] / 2**20:.2f} MiB | "
            f"{medians[SORT_TOGETHER] / 2**20:.2f} MiB | "
            f"{ratios[PYTHON]:.2f}x | {ratios[SORT_TOGETHER]:.2f}x |"
        )
    lines.extend(
        [
            "",
            "## Frozen gate summary",
            "",
            "- Direct Python time gate: "
            f"**{'pass' if time_gate['direct_python']['passed'] else 'fail'}**.",
            "- `sort_together()` time gate: "
            f"**{'pass' if time_gate['sort_together']['passed'] else 'fail'}**.",
            "- End-to-end NumPy boundary: "
            f"**{'pass' if time_gate['numpy_python_e2e']['passed'] else 'fail'}**.",
            "- Peak-memory gate: "
            f"**{'pass' if memory_gate['passed'] else 'fail'}**.",
            "",
            "Thresholds were not changed after execution. Existing older",
            "argsort results did not count toward this decision.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "python benchmarks/reorder_plan_candidate.py --canonical \\",
            f"  --json-output benchmarks/results/{json_name} \\",
            "  --markdown-output "
            "benchmarks/results/2026-08-06-reorder-plan-canonical.md",
            "```",
            "",
            f"Raw samples and rotation order: [{json_name}]({json_name}).",
            "",
            "## Environment",
            "",
        ]
    )
    environment = payload["environment"]
    lines.extend(
        [
            f"- Commit: `{payload['git']['commit']}`",
            f"- Python compiler: {environment['python_compiler']}",
            f"- Platform: {environment['platform']}",
            f"- CPU: {environment['cpu']}",
            f"- NumPy: {environment['numpy']}",
            f"- more-itertools: {environment['more_itertools']}",
            "",
        ]
    )
    return "\n".join(lines)


def validate_canonical_arguments(arguments):
    if tuple(arguments.sizes) != CANONICAL_SIZES:
        raise SystemExit("canonical sizes do not match the frozen protocol")
    if tuple(arguments.workloads) != WORKLOADS:
        raise SystemExit(
            "canonical workloads do not match the frozen protocol"
        )
    if arguments.repetitions != CANONICAL_REPETITIONS:
        raise SystemExit(
            "canonical timing repetitions do not match the frozen protocol"
        )
    if arguments.memory_repetitions != CANONICAL_MEMORY_REPETITIONS:
        raise SystemExit(
            "canonical memory repetitions do not match the frozen protocol"
        )
    if arguments.skip_memory or arguments.without_optional:
        raise SystemExit("canonical run requires every frozen baseline")
    if arguments.json_output is None or arguments.markdown_output is None:
        raise SystemExit("canonical run requires JSON and Markdown outputs")
    for output in (arguments.json_output, arguments.markdown_output):
        if output.exists():
            raise SystemExit(
                "canonical output already exists and will not be "
                f"overwritten: {output}"
            )
    state = git_state()
    if state["dirty"]:
        raise SystemExit("canonical run requires a clean committed worktree")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--sizes",
        nargs="+",
        type=int,
        default=list(CANONICAL_SIZES),
    )
    parser.add_argument(
        "-r",
        "--repetitions",
        type=int,
        default=CANONICAL_REPETITIONS,
    )
    parser.add_argument(
        "--memory-repetitions",
        type=int,
        default=CANONICAL_MEMORY_REPETITIONS,
    )
    parser.add_argument(
        "--workloads",
        nargs="+",
        choices=WORKLOADS,
        default=list(WORKLOADS),
    )
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument(
        "--without-optional",
        action="store_true",
        help="Run only direct Python and the private candidate.",
    )
    parser.add_argument("--canonical", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--worker",
        nargs=4,
        metavar=("ALGORITHM", "WORKLOAD", "SIZE", "SEED"),
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args()

    if arguments.worker:
        algorithm, workload, size, seed = arguments.worker
        print(
            json.dumps(
                memory_worker(
                    algorithm,
                    workload,
                    int(size),
                    int(seed),
                )
            )
        )
        return

    if arguments.canonical:
        validate_canonical_arguments(arguments)
    algorithms = selected_algorithms(not arguments.without_optional)
    git = git_state()
    time_rows = run_time_matrix(
        arguments.sizes,
        arguments.repetitions,
        arguments.workloads,
        algorithms,
    )
    memory_rows = []
    if not arguments.skip_memory:
        memory_rows = run_memory_matrix(
            max(arguments.sizes),
            arguments.memory_repetitions,
            arguments.workloads,
            algorithms,
        )

    decision = None
    if (
        not arguments.without_optional
        and tuple(arguments.sizes) == CANONICAL_SIZES
        and tuple(arguments.workloads) == WORKLOADS
        and not arguments.skip_memory
    ):
        time_gate = evaluate_time_gates(time_rows)
        memory_gate = evaluate_memory_gates(memory_rows)
        decision = {
            "time": time_gate,
            "memory": memory_gate,
            "local_performance_passed": (
                time_gate["passed"] and memory_gate["passed"]
            ),
            "note": (
                "A local pass authorizes only the remaining engineering and "
                "public-API promotion review; it does not authorize release."
            ),
        }
        print(
            "\nFROZEN LOCAL PERFORMANCE GATE: "
            + (
                "PASS"
                if decision["local_performance_passed"]
                else "FAIL"
            )
        )

    payload = {
        "schema_version": 1,
        "benchmark": "compact-reusable-reorder-plan-candidate",
        "canonical": arguments.canonical,
        "git": git,
        "environment": environment_metadata(),
        "configuration": {
            "sizes": arguments.sizes,
            "workloads": arguments.workloads,
            "repetitions": arguments.repetitions,
            "memory_repetitions": (
                0 if arguments.skip_memory else arguments.memory_repetitions
            ),
            "algorithms": algorithms,
            "seeds": {
                f"{workload}-{size}": workload_seed(workload, size)
                for workload in arguments.workloads
                for size in arguments.sizes
            },
        },
        "time_rows": time_rows,
        "memory_rows": memory_rows,
        "decision": decision,
    }
    if arguments.json_output:
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {arguments.json_output}")
    if arguments.markdown_output:
        if decision is None or arguments.json_output is None:
            raise SystemExit(
                "Markdown output requires a complete decision and JSON path"
            )
        arguments.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.markdown_output.write_text(
            render_markdown(payload, arguments.json_output.name),
            encoding="utf-8",
        )
        print(f"Wrote {arguments.markdown_output}")


if __name__ == "__main__":
    main()
