"""Measure the private compact stable argsort prototype.

The primary comparison gives both implementations the same Python ``list``:

* ``sorted(range(len(values)), key=values.__getitem__)`` returns ``list[int]``;
* BielSort returns an immutable compact native index buffer.

NumPy is reported as two deliberately separate scenarios. ``numpy-array``
starts with values already stored in an ndarray, while ``numpy-python-e2e``
includes conversion from the Python list. Peak RSS is measured in isolated
subprocesses and every raw timing sample is retained in the JSON report.
"""

import argparse
import gc
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource
except ImportError as error:  # pragma: no cover - unavailable on Windows
    raise SystemExit(
        "The argsort prototype memory benchmark requires Linux or macOS."
    ) from error

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional benchmark dependency
    np = None

from bielsort_native import _bielsort


PYTHON = "python-sorted-indices"
BIELSORT = "biel-compact-argsort"
NUMPY_ARRAY = "numpy-array"
NUMPY_E2E = "numpy-python-e2e"
PYTHON_REUSE = "python-build-and-apply-three"
BIELSORT_REUSE = "biel-build-and-apply-three"
PRIMARY_ALGORITHMS = (PYTHON, BIELSORT)
NUMPY_ALGORITHMS = (NUMPY_ARRAY, NUMPY_E2E)
CASES = ("dense", "int32", "int64", "nearly-sorted", "ascending")
DISORDERED_CASES = frozenset(("dense", "int32", "int64"))


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


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
    if case == "nearly-sorted":
        values = list(range(size))
        for _ in range(max(1, size // 500)):
            left = rng.randrange(size)
            right = rng.randrange(size)
            values[left], values[right] = values[right], values[left]
        return values
    if case == "ascending":
        return list(range(size))
    raise ValueError(f"Unknown case: {case}")


def create_numpy_values(size, case, seed):
    """Create the already-array scenario without a temporary Python list."""
    require_numpy()
    rng = np.random.default_rng(seed)
    if case == "dense":
        return rng.integers(
            -size // 4,
            size // 4 + 1,
            size=size,
            dtype=np.int64,
        )
    if case == "int32":
        return rng.integers(
            -(1 << 31),
            1 << 31,
            size=size,
            dtype=np.int64,
        )
    if case == "int64":
        return rng.integers(
            -(1 << 63),
            (1 << 63) - 1,
            size=size,
            dtype=np.int64,
            endpoint=True,
        )
    if case == "nearly-sorted":
        values = np.arange(size, dtype=np.int64)
        swaps = rng.integers(0, size, size=(max(1, size // 500), 2))
        for left, right in swaps:
            values[left], values[right] = values[right], values[left]
        return values
    if case == "ascending":
        return np.arange(size, dtype=np.int64)
    raise ValueError(f"Unknown case: {case}")


def require_numpy():
    if np is None:
        raise RuntimeError(
            "NumPy is unavailable; install the benchmark extra first"
        )


def run_construction(algorithm, values, array=None):
    if algorithm == PYTHON:
        return sorted(range(len(values)), key=values.__getitem__)
    if algorithm == BIELSORT:
        return _bielsort._argsort_int64_prototype(values)
    if algorithm == NUMPY_ARRAY:
        require_numpy()
        if array is None:
            raise AssertionError("numpy-array requires a prepared ndarray")
        return np.argsort(array, kind="stable")
    if algorithm == NUMPY_E2E:
        require_numpy()
        converted = np.asarray(values, dtype=np.int64)
        return np.argsort(converted, kind="stable")
    raise ValueError(f"Unknown algorithm: {algorithm}")


def permutation_as_list(result):
    if np is not None and isinstance(result, np.ndarray):
        return result.tolist()
    return list(result)


def ensure_permutation(result, expected):
    if len(result) != len(expected):
        raise AssertionError("Incorrect permutation length")
    if permutation_as_list(result) != expected:
        raise AssertionError("Incorrect or unstable permutation")


def result_storage(result):
    if isinstance(result, _bielsort._Permutation):
        view = memoryview(result)
        return {
            "kind": "compact-native-buffer",
            "itemsize": view.itemsize,
            "payload_bytes": view.nbytes,
        }
    if np is not None and isinstance(result, np.ndarray):
        return {
            "kind": "numpy-ndarray",
            "itemsize": result.itemsize,
            "payload_bytes": result.nbytes,
        }
    return {
        "kind": "python-list",
        "shallow_bytes": sys.getsizeof(result),
        "note": "Excludes memory owned by Python integer objects.",
    }


def rotate(items, offset):
    offset %= len(items)
    return items[offset:] + items[:offset]


def measure_construction(values, repetitions, include_numpy):
    algorithms = list(PRIMARY_ALGORITHMS)
    array = None
    if include_numpy:
        require_numpy()
        array = np.asarray(values, dtype=np.int64)
        algorithms.extend(NUMPY_ALGORITHMS)

    expected = sorted(range(len(values)), key=values.__getitem__)
    samples = {algorithm: [] for algorithm in algorithms}
    storage = {}
    for repetition in range(repetitions):
        for algorithm in rotate(algorithms, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_construction(algorithm, values, array)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_permutation(result, expected)
            samples[algorithm].append(elapsed)
            storage[algorithm] = result_storage(result)
            del result
    gc.collect()
    return samples, storage


def apply_permutation(values, order):
    return [values[index] for index in order]


def run_application(name, values, python_order, biel_order):
    if name == "python-list-indices":
        return apply_permutation(values, python_order)
    if name == "biel-compact-iteration":
        return apply_permutation(values, biel_order)
    if name == "biel-native-apply":
        return biel_order.apply(values)
    raise ValueError(f"Unknown application operation: {name}")


def measure_application(values, repetitions):
    python_order = run_construction(PYTHON, values)
    biel_order = run_construction(BIELSORT, values)
    expected = sorted(values)
    names = [
        "python-list-indices",
        "biel-compact-iteration",
        "biel-native-apply",
    ]
    samples = {name: [] for name in names}
    for repetition in range(repetitions):
        for name in rotate(names, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_application(
                    name,
                    values,
                    python_order,
                    biel_order,
                )
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            if result != expected:
                raise AssertionError("Applying the permutation was incorrect")
            samples[name].append(elapsed)
            del result
    del expected, python_order, biel_order
    gc.collect()
    return samples


def create_parallel_sequences(values):
    size = len(values)
    return [
        values,
        list(range(size)),
        [index % 97 for index in range(size)],
    ]


def run_reuse(name, values, sequences):
    if name == PYTHON_REUSE:
        order = run_construction(PYTHON, values)
        results = [apply_permutation(sequence, order) for sequence in sequences]
        return order, results
    if name == BIELSORT_REUSE:
        order = run_construction(BIELSORT, values)
        results = [order.apply(sequence) for sequence in sequences]
        return order, results
    raise ValueError(f"Unknown reuse operation: {name}")


def measure_reuse(values, repetitions):
    sequences = create_parallel_sequences(values)
    expected_order = run_construction(PYTHON, values)
    expected = [
        apply_permutation(sequence, expected_order)
        for sequence in sequences
    ]
    names = [
        PYTHON_REUSE,
        BIELSORT_REUSE,
    ]
    samples = {name: [] for name in names}
    for repetition in range(repetitions):
        for name in rotate(names, repetition):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                order, results = run_reuse(name, values, sequences)
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            if results != expected:
                raise AssertionError("Reused permutation produced wrong rows")
            samples[name].append(elapsed)
            del results, order
    del expected, expected_order, sequences
    gc.collect()
    return samples


def strategy_for(values):
    result, strategy = (
        _bielsort._argsort_int64_prototype_with_strategy(values)
    )
    storage = result_storage(result)
    del result
    return strategy, storage


def execute_time_benchmark(sizes, repetitions, cases, include_numpy):
    print("\nCONSTRUCTION TIME (median; speedup above 1.00x favors BielSort)")
    heading = (
        f"{'n':>10}  {'case':<15}  {'Python':>11}  {'Biel':>11}"
        f"  {'speedup':>8}"
    )
    if include_numpy:
        heading += f"  {'NumPy arr':>11}  {'NumPy E2E':>11}"
    print(heading)
    print("-" * len(heading))

    rows = []
    for size in sizes:
        for case in cases:
            values = create_values(size, case, 2026 + size)
            samples, storage = measure_construction(
                values,
                repetitions,
                include_numpy,
            )
            python_median = statistics.median(samples[PYTHON])
            biel_median = statistics.median(samples[BIELSORT])
            strategy, biel_storage = strategy_for(values)
            row = {
                "size": size,
                "case": case,
                "strategy": strategy,
                "python_median_s": python_median,
                "biel_median_s": biel_median,
                "biel_speedup": python_median / biel_median,
                "samples_s": samples,
                "result_storage": storage,
                "biel_result_storage": biel_storage,
            }
            line = (
                f"{size:>10,}  {case:<15}  {python_median:>10.6f}s"
                f"  {biel_median:>10.6f}s"
                f"  {row['biel_speedup']:>7.2f}x"
            )
            if include_numpy:
                numpy_array_median = statistics.median(
                    samples[NUMPY_ARRAY]
                )
                numpy_e2e_median = statistics.median(samples[NUMPY_E2E])
                row.update(
                    {
                        "numpy_array_median_s": numpy_array_median,
                        "numpy_python_e2e_median_s": numpy_e2e_median,
                    }
                )
                line += (
                    f"  {numpy_array_median:>10.6f}s"
                    f"  {numpy_e2e_median:>10.6f}s"
                )
            rows.append(row)
            print(line)
            del values
            gc.collect()
    return rows


def execute_application_benchmark(sizes, repetitions, cases):
    print("\nPYTHON-LIST APPLICATION TIME (median; lower is better)")
    print(
        f"{'n':>10}  {'case':<15}  {'list[int]':>12}"
        f"  {'compact iter':>12}  {'native':>12}"
        f"  {'list/native':>12}"
    )
    print("-" * 87)
    rows = []
    for size in sizes:
        for case in cases:
            values = create_values(size, case, 3030 + size)
            samples = measure_application(values, repetitions)
            python_median = statistics.median(
                samples["python-list-indices"]
            )
            compact_median = statistics.median(
                samples["biel-compact-iteration"]
            )
            native_median = statistics.median(
                samples["biel-native-apply"]
            )
            row = {
                "size": size,
                "case": case,
                "python_list_median_s": python_median,
                "biel_compact_iteration_median_s": compact_median,
                "biel_native_apply_median_s": native_median,
                "native_speedup_over_python_list": (
                    python_median / native_median
                ),
                "native_speedup_over_compact_iteration": (
                    compact_median / native_median
                ),
                "samples_s": samples,
            }
            rows.append(row)
            print(
                f"{size:>10,}  {case:<15}  {python_median:>11.6f}s"
                f"  {compact_median:>11.6f}s"
                f"  {native_median:>11.6f}s"
                f"  {row['native_speedup_over_python_list']:>11.2f}x"
            )
            del values
            gc.collect()
    return rows


def execute_reuse_benchmark(sizes, repetitions, cases):
    print("\nBUILD ONCE + APPLY TO THREE LISTS (median; higher gain is better)")
    print(
        f"{'n':>10}  {'case':<15}  {'Python':>12}"
        f"  {'Biel native':>12}  {'gain':>9}"
    )
    print("-" * 67)
    rows = []
    for size in sizes:
        for case in cases:
            values = create_values(size, case, 5050 + size)
            samples = measure_reuse(values, repetitions)
            python_median = statistics.median(
                samples[PYTHON_REUSE]
            )
            biel_median = statistics.median(
                samples[BIELSORT_REUSE]
            )
            row = {
                "size": size,
                "case": case,
                "sequence_count": 3,
                "python_median_s": python_median,
                "biel_median_s": biel_median,
                "biel_speedup": python_median / biel_median,
                "samples_s": samples,
            }
            rows.append(row)
            print(
                f"{size:>10,}  {case:<15}  {python_median:>11.6f}s"
                f"  {biel_median:>11.6f}s"
                f"  {row['biel_speedup']:>8.2f}x"
            )
            del values
            gc.collect()
    return rows


def run_memory_worker(algorithm, case, size, seed):
    if algorithm in (PYTHON_REUSE, BIELSORT_REUSE):
        values = create_values(size, case, seed)
        sequences = create_parallel_sequences(values)
        gc.collect()
        baseline = peak_rss_bytes()
        started = time.perf_counter()
        order, results = run_reuse(algorithm, values, sequences)
        elapsed = time.perf_counter() - started
        incremental_peak = max(0, peak_rss_bytes() - baseline)
        expected_order = run_construction(PYTHON, values)
        expected = [
            apply_permutation(sequence, expected_order)
            for sequence in sequences
        ]
        if results != expected:
            raise AssertionError("Reused permutation produced wrong rows")
        return {
            "algorithm": algorithm,
            "case": case,
            "size": size,
            "elapsed_s": elapsed,
            "incremental_peak_bytes": incremental_peak,
            "order_storage": result_storage(order),
            "sequence_count": len(sequences),
        }

    array = None
    if algorithm == NUMPY_ARRAY:
        values = create_numpy_values(size, case, seed)
        array = values
    else:
        values = create_values(size, case, seed)

    gc.collect()
    baseline = peak_rss_bytes()
    started = time.perf_counter()
    result = run_construction(algorithm, values, array)
    elapsed = time.perf_counter() - started
    incremental_peak = max(0, peak_rss_bytes() - baseline)

    if algorithm == NUMPY_ARRAY:
        expected = np.argsort(values, kind="stable").tolist()
    else:
        expected = sorted(range(len(values)), key=values.__getitem__)
    ensure_permutation(result, expected)
    return {
        "algorithm": algorithm,
        "case": case,
        "size": size,
        "elapsed_s": elapsed,
        "incremental_peak_bytes": incremental_peak,
        "result_storage": result_storage(result),
    }


def invoke_memory_worker(algorithm, case, size, seed):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        algorithm,
        case,
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


def execute_memory_benchmark(
    size,
    repetitions,
    cases,
    include_numpy,
):
    algorithms = list(PRIMARY_ALGORITHMS)
    if include_numpy:
        algorithms.extend(NUMPY_ALGORITHMS)

    print("\nPEAK RSS (median incremental peak; lower is better)")
    heading = (
        f"{'case':<15}  {'Python':>12}  {'Biel':>12}"
        f"  {'Biel/Python':>12}"
    )
    if include_numpy:
        heading += f"  {'NumPy arr':>12}  {'NumPy E2E':>12}"
    print(heading)
    print("-" * len(heading))

    rows = []
    for case in cases:
        by_algorithm = {}
        for algorithm in algorithms:
            samples = [
                invoke_memory_worker(
                    algorithm,
                    case,
                    size,
                    4040 + repetition,
                )
                for repetition in range(repetitions)
            ]
            by_algorithm[algorithm] = {
                "median_incremental_peak_bytes": statistics.median(
                    sample["incremental_peak_bytes"] for sample in samples
                ),
                "samples": samples,
            }

        python_peak = by_algorithm[PYTHON][
            "median_incremental_peak_bytes"
        ]
        biel_peak = by_algorithm[BIELSORT][
            "median_incremental_peak_bytes"
        ]
        ratio = biel_peak / python_peak if python_peak else None
        row = {
            "size": size,
            "case": case,
            "python_peak_bytes": python_peak,
            "biel_peak_bytes": biel_peak,
            "biel_to_python_ratio": ratio,
            "raw": by_algorithm,
        }
        line = (
            f"{case:<15}  {python_peak / 2**20:>10.2f} MiB"
            f"  {biel_peak / 2**20:>10.2f} MiB"
            f"  {ratio if ratio is not None else float('nan'):>11.2f}x"
        )
        if include_numpy:
            numpy_array_peak = by_algorithm[NUMPY_ARRAY][
                "median_incremental_peak_bytes"
            ]
            numpy_e2e_peak = by_algorithm[NUMPY_E2E][
                "median_incremental_peak_bytes"
            ]
            row.update(
                {
                    "numpy_array_peak_bytes": numpy_array_peak,
                    "numpy_python_e2e_peak_bytes": numpy_e2e_peak,
                }
            )
            line += (
                f"  {numpy_array_peak / 2**20:>10.2f} MiB"
                f"  {numpy_e2e_peak / 2**20:>10.2f} MiB"
            )
        rows.append(row)
        print(line)
    return rows


def execute_reuse_memory_benchmark(size, repetitions, cases):
    print("\nTHREE-LIST REUSE PEAK RSS (median incremental peak)")
    print(
        f"{'case':<15}  {'Python':>12}  {'Biel native':>12}"
        f"  {'Biel/Python':>12}"
    )
    print("-" * 59)
    rows = []
    for case in cases:
        by_algorithm = {}
        for algorithm in (PYTHON_REUSE, BIELSORT_REUSE):
            samples = [
                invoke_memory_worker(
                    algorithm,
                    case,
                    size,
                    6060 + repetition,
                )
                for repetition in range(repetitions)
            ]
            by_algorithm[algorithm] = {
                "median_incremental_peak_bytes": statistics.median(
                    sample["incremental_peak_bytes"] for sample in samples
                ),
                "samples": samples,
            }
        python_peak = by_algorithm[PYTHON_REUSE][
            "median_incremental_peak_bytes"
        ]
        biel_peak = by_algorithm[BIELSORT_REUSE][
            "median_incremental_peak_bytes"
        ]
        ratio = biel_peak / python_peak if python_peak else None
        row = {
            "size": size,
            "case": case,
            "sequence_count": 3,
            "python_peak_bytes": python_peak,
            "biel_peak_bytes": biel_peak,
            "biel_to_python_ratio": ratio,
            "raw": by_algorithm,
        }
        rows.append(row)
        print(
            f"{case:<15}  {python_peak / 2**20:>10.2f} MiB"
            f"  {biel_peak / 2**20:>10.2f} MiB"
            f"  {ratio if ratio is not None else float('nan'):>11.2f}x"
        )
    return rows


def evaluate_gate(time_rows, memory_rows):
    speed_cases = [
        {"size": row["size"], "case": row["case"], "speedup": row["biel_speedup"]}
        for row in time_rows
        if row["size"] >= 100_000
        and row["case"] in DISORDERED_CASES
        and row["biel_speedup"] >= 1.50
    ]
    timing = {
        (row["size"], row["case"]): row for row in time_rows
    }
    memory_cases = []
    for row in memory_rows:
        ratio = row["biel_to_python_ratio"]
        time_row = timing.get((row["size"], row["case"]))
        if (
            ratio is not None
            and ratio <= 0.70
            and time_row is not None
            and time_row["biel_median_s"]
            <= time_row["python_median_s"] * 1.10
        ):
            memory_cases.append(
                {
                    "size": row["size"],
                    "case": row["case"],
                    "memory_ratio": ratio,
                    "time_ratio": (
                        time_row["biel_median_s"]
                        / time_row["python_median_s"]
                    ),
                }
            )
    return {
        "passed": len(speed_cases) >= 2 or bool(memory_cases),
        "speed_gate_passed": len(speed_cases) >= 2,
        "speed_gate_cases": speed_cases,
        "memory_gate_passed": bool(memory_cases),
        "memory_gate_cases": memory_cases,
        "note": (
            "A pass justifies continued private engineering; it is not a "
            "market-adoption or universal-performance claim."
        ),
    }


def evaluate_application_gate(application_rows, reuse_rows):
    native_application_cases = [
        {
            "size": row["size"],
            "case": row["case"],
            "speedup": row["native_speedup_over_python_list"],
        }
        for row in application_rows
        if row["size"] == 1_000_000
        and row["native_speedup_over_python_list"] >= 1.50
    ]
    reuse_cases = [
        {
            "size": row["size"],
            "case": row["case"],
            "speedup": row["biel_speedup"],
        }
        for row in reuse_rows
        if row["size"] >= 100_000
        and row["case"] in DISORDERED_CASES
        and row["biel_speedup"] >= 1.50
    ]
    nearly_sorted_regressions = [
        {
            "size": row["size"],
            "case": row["case"],
            "ratio": 1.0 / row["biel_speedup"],
        }
        for row in reuse_rows
        if row["size"] >= 100_000
        and row["case"] == "nearly-sorted"
        and row["biel_speedup"] < (1.0 / 1.10)
    ]
    return {
        "passed": (
            len(native_application_cases) >= 4
            and len(reuse_cases) >= 2
            and not nearly_sorted_regressions
        ),
        "native_application_passed": (
            len(native_application_cases) >= 4
        ),
        "native_application_cases": native_application_cases,
        "three_sequence_reuse_passed": len(reuse_cases) >= 2,
        "three_sequence_reuse_cases": reuse_cases,
        "nearly_sorted_bound_passed": not nearly_sorted_regressions,
        "nearly_sorted_regressions": nearly_sorted_regressions,
        "note": (
            "This gate evaluates the private native apply experiment, not a "
            "public API or release decision."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--sizes",
        nargs="+",
        type=int,
        default=[10_000, 100_000, 1_000_000],
    )
    parser.add_argument("-r", "--repetitions", type=int, default=5)
    parser.add_argument("--memory-repetitions", type=int, default=3)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=CASES,
        default=list(CASES),
    )
    parser.add_argument(
        "--without-numpy",
        action="store_true",
        help="Skip the optional NumPy scenarios.",
    )
    parser.add_argument(
        "--skip-memory",
        action="store_true",
        help="Skip isolated-process peak RSS measurement.",
    )
    parser.add_argument(
        "--skip-application",
        action="store_true",
        help="Skip applying precomputed permutations to Python lists.",
    )
    parser.add_argument(
        "--skip-reuse",
        action="store_true",
        help="Skip constructing once and applying to three parallel lists.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path for raw, reviewable benchmark results.",
    )
    parser.add_argument(
        "--worker",
        nargs=4,
        metavar=("ALGORITHM", "CASE", "SIZE", "SEED"),
        help=argparse.SUPPRESS,
    )
    arguments = parser.parse_args()

    if arguments.worker:
        algorithm, case, size, seed = arguments.worker
        print(
            json.dumps(
                run_memory_worker(
                    algorithm,
                    case,
                    int(size),
                    int(seed),
                )
            )
        )
        return

    include_numpy = not arguments.without_numpy
    if include_numpy and np is None:
        raise SystemExit(
            "NumPy is unavailable. Install the benchmark extra or pass "
            "--without-numpy."
        )

    memory_rows = []
    reuse_memory_rows = []
    if not arguments.skip_memory:
        memory_rows = execute_memory_benchmark(
            max(arguments.sizes),
            arguments.memory_repetitions,
            arguments.cases,
            include_numpy,
        )
        if not arguments.skip_reuse:
            reuse_memory_rows = execute_reuse_memory_benchmark(
                max(arguments.sizes),
                arguments.memory_repetitions,
                arguments.cases,
            )
    time_rows = execute_time_benchmark(
        arguments.sizes,
        arguments.repetitions,
        arguments.cases,
        include_numpy,
    )
    application_rows = []
    if not arguments.skip_application:
        application_rows = execute_application_benchmark(
            arguments.sizes,
            arguments.repetitions,
            arguments.cases,
        )
    reuse_rows = []
    if not arguments.skip_reuse:
        reuse_rows = execute_reuse_benchmark(
            arguments.sizes,
            arguments.repetitions,
            arguments.cases,
        )
    gate = evaluate_gate(time_rows, memory_rows)
    application_gate = evaluate_application_gate(
        application_rows,
        reuse_rows,
    )
    print(
        "\nPRE-REGISTERED GATE: "
        + ("PASS" if gate["passed"] else "NOT YET PASSED")
    )
    print(
        "NATIVE APPLY GATE: "
        + (
            "PASS"
            if application_gate["passed"]
            else "NOT YET PASSED"
        )
    )

    if arguments.json_output:
        payload = {
            "schema_version": 1,
            "benchmark": "compact-stable-argsort-prototype",
            "python": sys.version,
            "python_compiler": platform.python_compiler(),
            "platform": platform.platform(),
            "numpy": None if np is None else np.__version__,
            "configuration": {
                "sizes": arguments.sizes,
                "cases": arguments.cases,
                "repetitions": arguments.repetitions,
                "memory_repetitions": (
                    0
                    if arguments.skip_memory
                    else arguments.memory_repetitions
                ),
                "numpy_included": include_numpy,
            },
            "construction_time": time_rows,
            "application_time": application_rows,
            "reuse_time": reuse_rows,
            "memory": memory_rows,
            "reuse_memory": reuse_memory_rows,
            "decision_gate": gate,
            "application_decision_gate": application_gate,
        }
        arguments.json_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.json_output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Raw results written to {arguments.json_output}")


if __name__ == "__main__":
    main()
