import importlib.util
import sys
import unittest
from pathlib import Path


BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "streaming_topk.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bielsort_streaming_topk_benchmark",
    BENCHMARK_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load the streaming top-k benchmark")
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)

CANDIDATE = BENCHMARK.CANDIDATE
HEAPQ = BENCHMARK.HEAPQ
MATERIALIZING_FACADE = BENCHMARK.MATERIALIZING_FACADE
render_report = BENCHMARK.render_report
run_memory_child = BENCHMARK.run_memory_child


class StreamingTopKBenchmarkTests(unittest.TestCase):
    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "parent-sampled RSS is a Linux benchmark probe",
    )
    def test_parent_samples_worker_after_ready_checkpoint(self):
        sample = run_memory_child(
            BENCHMARK_PATH,
            CANDIDATE,
            10_000,
            "keyed-int64",
            100,
        )
        self.assertEqual(sample["selected"], 100)
        self.assertEqual(sample["measurement"], "parent-sampled-linux-rss")
        self.assertGreater(sample["baseline_current_rss_bytes"], 0)
        self.assertGreaterEqual(
            sample["sampled_peak_rss_bytes"],
            sample["baseline_current_rss_bytes"],
        )
        self.assertGreaterEqual(sample["incremental_peak_rss_bytes"], 0)

    def test_report_handles_a_zero_memory_denominator(self):
        payload = {
            "protocol_commit": "protocol",
            "implementation_commit": "implementation",
            "timing": [],
            "memory": [
                {
                    "domain": "keyed-int64",
                    "k": 100,
                    "median_incremental_peak_rss_bytes": {
                        CANDIDATE: 0,
                        HEAPQ: 0,
                        MATERIALIZING_FACADE: 1,
                    },
                    "candidate_to_heapq_ratio": None,
                    "candidate_to_materializing_facade_ratio": 0.0,
                }
            ],
            "decision": {
                "canonical_configuration": True,
                "passed": False,
                "minimum_speedup": 0.0,
                "exact_target_count": 0,
                "exact_case_count": 0,
                "generic_target_count": 0,
                "generic_case_count": 0,
                "checks": {},
            },
        }
        report = render_report(payload)
        self.assertIn("n/a", report)
        self.assertIn("0.00x", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
