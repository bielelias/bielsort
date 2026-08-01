import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "workload_evaluator.py"
)
SPEC = spec_from_file_location("workload_evaluator", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load workload evaluator from {SCRIPT_PATH}")
evaluator = module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


class WorkloadEvaluatorTests(unittest.TestCase):
    def test_report_is_correct_and_does_not_contain_raw_values(self):
        private_marker = 918_273_645_546_372_819
        values = [private_marker - index * 97 for index in range(2_048)]
        original = values.copy()

        report = evaluator.evaluate_workload(
            values,
            label="private-test",
            repetitions=3,
            warmups=0,
            sample_size=32,
        )

        self.assertEqual(values, original)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["suite"], "bielsort-workload-evaluator")
        self.assertTrue(report["correctness"]["all_results_matched"])
        self.assertFalse(report["privacy"]["raw_values_included"])
        self.assertFalse(report["privacy"]["provider_path_included"])
        self.assertFalse(report["privacy"]["automatic_upload"])
        self.assertEqual(
            set(report["samples_ns"]),
            set(evaluator.OPERATION_NAMES),
        )
        for operation in evaluator.OPERATION_NAMES:
            self.assertEqual(len(report["samples_ns"][operation]), 3)
            self.assertGreater(report["median_ns"][operation], 0)

        serialized = json.dumps(report)
        self.assertNotIn(str(private_marker), serialized)
        self.assertNotIn(str(private_marker - 97), serialized)

    def test_minimal_metadata_omits_distribution_statistics(self):
        report = evaluator.evaluate_workload(
            [3, 1, 2],
            repetitions=3,
            warmups=0,
            minimal_metadata=True,
        )

        workload = report["workload"]
        self.assertEqual(workload["size"], 3)
        self.assertEqual(
            workload["distribution_metadata"],
            "omitted by user",
        )
        self.assertNotIn("sample_duplicate_ratio", workload)

    def test_provider_loader_uses_path_callable_format(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            provider_path = Path(temporary_directory) / "private_provider.py"
            provider_path.write_text(
                "def load_values():\n    return [4, 2, 3, 1]\n",
                encoding="utf-8",
            )

            provider = evaluator.load_provider(
                f"{provider_path}:load_values"
            )
            self.assertEqual(provider(), [4, 2, 3, 1])

            with self.assertRaises(ValueError):
                evaluator.load_provider(str(provider_path))
            with self.assertRaises(ValueError):
                evaluator.load_provider(f"{provider_path}:missing")

    def test_result_is_released_before_measurement_returns(self):
        calls = []
        releases = []

        class Result:
            def __eq__(self, other):
                return True

            def __del__(self):
                releases.append(len(calls))

        def operation(_):
            self.assertEqual(len(releases), len(calls))
            calls.append("called")
            return Result()

        for _ in range(3):
            evaluator._measure_once(
                lambda: None,
                operation,
                expected=object(),
                operation="probe",
            )

        self.assertEqual(len(calls), 3)
        self.assertEqual(len(releases), 3)

    def test_writes_reviewable_json_and_markdown(self):
        report = evaluator.evaluate_workload(
            [9, 4, 7, 1, 4],
            label="report-test",
            repetitions=3,
            warmups=0,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            evaluator.write_reports(report, json_path, markdown_path)

            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertEqual(loaded["configuration"]["label"], "report-test")
            self.assertIn("BielSort workload evaluation", markdown)
            self.assertIn("no raw workload values", markdown)
            self.assertIn(evaluator.USE_CASE_URL, markdown)

    def test_rejects_invalid_workloads_and_configuration(self):
        with self.assertRaises(TypeError):
            evaluator.evaluate_workload((3, 2, 1), repetitions=3)
        with self.assertRaises(ValueError):
            evaluator.evaluate_workload([1], repetitions=3)
        with self.assertRaises(ValueError):
            evaluator.evaluate_workload([2, 1], label="", repetitions=3)
        with self.assertRaises(ValueError):
            evaluator.evaluate_workload([2, 1], repetitions=2)
        with self.assertRaises(ValueError):
            evaluator.evaluate_workload([2, 1], repetitions=4)
        with self.assertRaises(ValueError):
            evaluator.describe_workload([2, 1], sample_size=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

