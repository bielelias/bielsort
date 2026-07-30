"""Compare BielSort with NumPy using both equivalent and native-array APIs."""

import argparse
import gc
import random
import statistics
import time

try:
    import numpy as np
except ImportError as error:
    raise SystemExit(
        "Install benchmark dependencies with `python -m pip install "
        "'.[benchmark]'`."
    ) from error

from bielsort import biel_sort


def measure(function, repetitions, validator):
    timings = []
    for _ in range(repetitions):
        gc.collect()
        gc.disable()
        started = time.perf_counter()
        result = function()
        elapsed = time.perf_counter() - started
        gc.enable()
        validator(result)
        timings.append(elapsed)
    return statistics.median(timings)


def create_cases(size, seed):
    rng = random.Random(seed)
    return {
        "dense": [rng.randint(-size // 4, size // 4) for _ in range(size)],
        "int64": [
            rng.randint(-(1 << 63), (1 << 63) - 1)
            for _ in range(size)
        ],
    }


def validate_list(result, expected):
    if result != expected:
        raise AssertionError("Incorrect list result")


def validate_array(result, expected):
    if not np.array_equal(result, expected):
        raise AssertionError("Incorrect NumPy result")


def execute(sizes, repetitions):
    print(f"NumPy {np.__version__}; stable sort; median of {repetitions} runs")
    print(
        f"{'n':>10}  {'case':<8}  {'sorted':>10}  {'BielSort':>10}"
        f"  {'NumPy E2E':>10}  {'NumPy array':>11}"
    )
    print("-" * 72)

    results = []
    for size in sizes:
        for case, values in create_cases(size, 2026 + size).items():
            expected = sorted(values)
            array = np.asarray(values, dtype=np.int64)
            expected_array = np.asarray(expected, dtype=np.int64)

            sorted_time = measure(
                lambda: sorted(values),
                repetitions,
                lambda result: validate_list(result, expected),
            )
            biel_time = measure(
                lambda: biel_sort(values),
                repetitions,
                lambda result: validate_list(result, expected),
            )
            numpy_e2e_time = measure(
                lambda: np.sort(
                    np.asarray(values, dtype=np.int64),
                    kind="stable",
                ).tolist(),
                repetitions,
                lambda result: validate_list(result, expected),
            )
            numpy_array_time = measure(
                lambda: np.sort(array, kind="stable"),
                repetitions,
                lambda result: validate_array(result, expected_array),
            )
            results.append(
                {
                    "n": size,
                    "case": case,
                    "sorted_s": sorted_time,
                    "bielsort_s": biel_time,
                    "numpy_e2e_s": numpy_e2e_time,
                    "numpy_array_s": numpy_array_time,
                }
            )
            print(
                f"{size:>10,}  {case:<8}  {sorted_time:>9.5f}s"
                f"  {biel_time:>9.5f}s  {numpy_e2e_time:>9.5f}s"
                f"  {numpy_array_time:>10.5f}s"
            )
    return results


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
    arguments = parser.parse_args()
    execute(arguments.sizes, arguments.repetitions)


if __name__ == "__main__":
    main()
