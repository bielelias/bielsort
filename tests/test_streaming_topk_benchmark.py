import sys
import unittest
from pathlib import Path

from benchmarks.streaming_topk import (
    CANDIDATE,
    HEAPQ,
    MATERIALIZING_FACADE,
    render_report,
    run_memory_child,
)


class StreamingTopKBenchmarkTests(unittest.TestCase):
    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "parent-sampled RSS is a Linux benchmark probe",
    )
    def test_parent_samples_worker_after_ready_checkpoint(self):
        script = Path("benchmarks/streaming_topk.py").resolve()
        sample = run_memory_child(
            script,
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
