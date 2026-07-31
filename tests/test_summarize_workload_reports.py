import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "summarize_workload_reports.py"
)
SPEC = spec_from_file_location("summarize_workload_reports", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load report summarizer from {SCRIPT_PATH}")
summarizer = module_from_spec(SPEC)
SPEC.loader.exec_module(summarizer)


def sample_report(context="ubuntu-py311"):
    return {
        "schema_version": 1,
        "created_at": "2026-07-31T00:00:00+00:00",
        "environment": {
            "platform": "Linux-test",
            "machine": "x86_64",
            "python": "3.11.0",
            "bielsort": "0.1.0",
            "numpy": "2.4.6",
        },
        "configuration": {
            "context": context,
            "sizes": [100_000],
            "repetitions": 5,
            "cases": ["event-timestamps"],
            "numpy_end_to_end": True,
        },
        "results": [
            {
                "case": "event-timestamps",
                "size": 100_000,
                "strategy": "radix nativo: 2 passagens",
                "native_fast_path": True,
                "median_seconds": {
                    "sorted": 0.020,
                    "bielsort": 0.005,
                    "numpy-e2e": 0.010,
                },
                "bielsort_speedup_vs_sorted": 4.0,
                "bielsort_speedup_vs_numpy_e2e": 2.0,
                "winner": "bielsort",
            }
        ],
    }


class SummarizeWorkloadReportsTests(unittest.TestCase):
    def test_discovers_and_summarizes_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "report.json").write_text(
                json.dumps(sample_report()),
                encoding="utf-8",
            )

            loaded = summarizer.discover_reports(root)
            markdown = summarizer.build_markdown(loaded)

        self.assertEqual(len(loaded), 1)
        self.assertIn("GitHub-hosted workload validation", markdown)
        self.assertIn("ubuntu-py311", markdown)
        self.assertIn("4.00×", markdown)
        self.assertIn("1/1", markdown)

    def test_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = sample_report()
            report["schema_version"] = 99
            path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "schema version"):
                summarizer.load_report(path)

    def test_rejects_duplicate_contexts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = json.dumps(sample_report())
            (root / "first.json").write_text(content, encoding="utf-8")
            (root / "second.json").write_text(content, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate report"):
                summarizer.discover_reports(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
