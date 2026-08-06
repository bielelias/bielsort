import sys
import unittest

from benchmarks import reorder_plan_candidate as benchmark


class ReorderPlanBenchmarkTests(unittest.TestCase):
    """Small deterministic checks for the frozen end-to-end harness."""

    def test_all_workload_shapes_match_by_exact_identity(self):
        for workload_name in benchmark.WORKLOADS:
            workload = benchmark.create_workload(
                workload_name,
                257,
                benchmark.workload_seed(workload_name, 257),
            )
            expected = benchmark.expected_order(workload)
            resident = benchmark.prepare_resident_arrays(workload)
            algorithms = [benchmark.PYTHON, benchmark.CANDIDATE]
            if benchmark.more_itertools is not None:
                algorithms.append(benchmark.SORT_TOGETHER)
            if benchmark.np is not None:
                algorithms.extend(
                    (benchmark.NUMPY_E2E, benchmark.NUMPY_RESIDENT)
                )

            for algorithm in algorithms:
                with self.subTest(
                    workload=workload_name,
                    algorithm=algorithm,
                ):
                    order, outputs = benchmark.run_algorithm(
                        algorithm,
                        workload,
                        resident,
                    )
                    benchmark.validate_result(
                        algorithm,
                        order,
                        outputs,
                        workload,
                        resident,
                        expected,
                    )

    def test_time_gate_implements_the_frozen_thresholds(self):
        rows = []
        for size in benchmark.CANONICAL_SIZES:
            for workload in benchmark.WORKLOADS:
                rows.append(
                    {
                        "workload": workload,
                        "size": size,
                        "candidate_speedup_over": {
                            benchmark.PYTHON: 2.0,
                            benchmark.SORT_TOGETHER: 1.5,
                            benchmark.NUMPY_E2E: 1.1,
                        },
                    }
                )

        self.assertTrue(benchmark.evaluate_time_gates(rows)["passed"])
        rows[-1]["candidate_speedup_over"][benchmark.PYTHON] = 0.5
        self.assertFalse(benchmark.evaluate_time_gates(rows)["passed"])

    def test_memory_gate_implements_reduction_and_payload_rules(self):
        rows = []
        for workload in benchmark.WORKLOADS:
            rows.append(
                {
                    "workload": workload,
                    "size": 1_000_000,
                    "candidate_memory_ratio_to": {
                        benchmark.PYTHON: 0.5,
                        benchmark.SORT_TOGETHER: 0.5,
                    },
                    "raw": {
                        benchmark.CANDIDATE: [
                            {
                                "permutation": {
                                    "payload_bytes": 4_000_000,
                                    "itemsize": 4,
                                    "readonly": True,
                                }
                            }
                        ]
                    },
                }
            )

        self.assertTrue(benchmark.evaluate_memory_gates(rows)["passed"])
        rows[0]["raw"][benchmark.CANDIDATE][0]["permutation"][
            "readonly"
        ] = False
        self.assertFalse(benchmark.evaluate_memory_gates(rows)["passed"])

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "parent-sampled RSS is a Linux benchmark probe",
    )
    def test_parent_samples_after_worker_ready_checkpoint(self):
        sample = benchmark.run_memory_child(
            benchmark.CANDIDATE,
            benchmark.EVENT,
            10_000,
            benchmark.workload_seed(benchmark.EVENT, 10_000),
        )

        self.assertEqual(sample["measurement"], "parent-sampled-linux-rss")
        self.assertGreater(sample["baseline_current_rss_bytes"], 0)
        self.assertGreaterEqual(
            sample["sampled_peak_rss_bytes"],
            sample["baseline_current_rss_bytes"],
        )
        self.assertGreaterEqual(sample["incremental_peak_bytes"], 0)

    def test_markdown_ratio_handles_zero_denominator(self):
        self.assertEqual(benchmark.format_ratio(None), "n/a")
        self.assertEqual(benchmark.format_ratio(0.5), "0.50x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
