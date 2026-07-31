import json
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "workload_validation.py"
)
SPEC = spec_from_file_location("bielsort_workload_validation", BENCHMARK_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load benchmark module from {BENCHMARK_PATH}")
workload_validation = module_from_spec(SPEC)
SPEC.loader.exec_module(workload_validation)


class WorkloadValidationTests(unittest.TestCase):
    def test_generators_are_deterministic_int64_lists(self):
        for case in workload_validation.CASE_DESCRIPTIONS:
            with self.subTest(case=case):
                first = workload_validation.create_case(case, 1_000, 42)
                second = workload_validation.create_case(case, 1_000, 42)
                self.assertEqual(first, second)
                self.assertEqual(len(first), 1_000)
                self.assertTrue(all(type(value) is int for value in first))
                self.assertTrue(
                    all(
                        workload_validation.INT64_MIN
                        <= value
                        <= workload_validation.INT64_MAX
                        for value in first
                    )
                )

    def test_report_without_optional_numpy_is_valid_json(self):
        report = workload_validation.run_validation(
            sizes=[2_048],
            repetitions=1,
            cases=["event-timestamps"],
            include_numpy=False,
            show_table=False,
        )

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(len(report["results"]), 1)
        result = report["results"][0]
        self.assertEqual(result["size"], 2_048)
        self.assertIsInstance(result["native_fast_path"], bool)
        self.assertEqual(
            set(result["median_seconds"]),
            {"sorted", "bielsort"},
        )
        self.assertIn(result["winner"], {"sorted", "bielsort"})
        json.dumps(report)

    def test_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            workload_validation.create_case("event-timestamps", 0, 42)
        with self.assertRaises(ValueError):
            workload_validation.run_validation(
                sizes=[10],
                repetitions=0,
                cases=["event-timestamps"],
                include_numpy=False,
                show_table=False,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
