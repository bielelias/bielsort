import unittest

from benchmarks import reorder_plan_candidate as base
from benchmarks import reorder_plan_memory_continuation as continuation


def time_row(workload, size, speedup):
    return {
        "workload": workload,
        "size": size,
        "candidate_speedup_over": {base.PYTHON: speedup},
    }


def memory_sample(seed, peak, candidate=False):
    sample = {"seed": seed, "incremental_peak_bytes": peak}
    if candidate:
        sample["permutation"] = {
            "readonly": True,
            "itemsize": 4,
            "payload_bytes": 4_000_000,
        }
    return sample


class ReorderPlanMemoryContinuationTests(unittest.TestCase):
    def rows(self, candidate_peaks=(100, 104, 106)):
        times = [
            time_row(base.EVENT_NEARLY, 100_000, 0.91),
            time_row(base.EVENT_NEARLY, 1_000_000, 0.93),
        ]
        raw = {
            base.PYTHON: [
                memory_sample(1, 100),
                memory_sample(2, 100),
                memory_sample(3, 100),
            ],
            base.CANDIDATE: [
                memory_sample(seed, peak, candidate=True)
                for seed, peak in zip((1, 2, 3), candidate_peaks)
            ],
        }
        memory = [
            {
                "workload": base.EVENT_NEARLY,
                "size": 1_000_000,
                "candidate_memory_ratio_to": {base.PYTHON: 1.04},
                "raw": raw,
            }
        ]
        return times, memory

    def test_focused_gate_requires_median_pairs_time_and_payload(self):
        times, memory = self.rows()

        decision = continuation.evaluate_focused_gates(times, memory)

        self.assertTrue(decision["passed"])
        self.assertEqual(
            decision["nearly_ordered_memory"]["paired_pass_count"],
            3,
        )

        memory[0]["candidate_memory_ratio_to"][base.PYTHON] = 1.051
        self.assertFalse(
            continuation.evaluate_focused_gates(times, memory)["passed"]
        )

    def test_focused_gate_rejects_bad_pairs_time_or_payload(self):
        times, memory = self.rows(candidate_peaks=(111, 112, 100))
        self.assertFalse(
            continuation.evaluate_focused_gates(times, memory)["passed"]
        )

        times, memory = self.rows()
        times[0]["candidate_speedup_over"][base.PYTHON] = 0.899
        self.assertFalse(
            continuation.evaluate_focused_gates(times, memory)["passed"]
        )

        times, memory = self.rows()
        memory[0]["raw"][base.CANDIDATE][0]["permutation"][
            "payload_bytes"
        ] = 8_000_000
        self.assertFalse(
            continuation.evaluate_focused_gates(times, memory)["passed"]
        )

    def test_paired_memory_requires_identical_seeds(self):
        _, memory = self.rows()
        memory[0]["raw"][base.CANDIDATE][0]["seed"] = 99

        with self.assertRaisesRegex(ValueError, "seeds do not match"):
            continuation.paired_memory_ratios(memory[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
