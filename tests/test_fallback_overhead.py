import json
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "fallback_overhead.py"
)
SPEC = spec_from_file_location("fallback_overhead", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load fallback profiler from {SCRIPT_PATH}")
profiler = module_from_spec(SPEC)
SPEC.loader.exec_module(profiler)


class FallbackOverheadTests(unittest.TestCase):
    def test_generators_are_deterministic(self):
        for case in profiler.CASE_DESCRIPTIONS:
            with self.subTest(case=case):
                first = profiler.create_case(case, 2_048, 42)
                second = profiler.create_case(case, 2_048, 42)
                self.assertEqual(first, second)
                self.assertEqual(len(first), 2_048)
                self.assertEqual(sorted(first), list(range(2_048)))

    def test_profile_contains_raw_samples_and_derived_metrics(self):
        report = profiler.run_profile(
            sizes=[2_048],
            repetitions=2,
            cases=["random-swaps"],
            show_table=False,
            context="test",
        )

        self.assertEqual(report["suite"], "fallback-overhead")
        self.assertEqual(report["configuration"]["context"], "test")
        result = report["results"][0]
        self.assertTrue(result["strategy"].startswith("timsort:"))
        self.assertEqual(set(result["median_ns"]), set(profiler.OPERATION_NAMES))
        for operation in profiler.OPERATION_NAMES:
            self.assertEqual(len(result["samples_ns"][operation]), 2)
        self.assertIn(
            "new_bielsort_over_sorted_ns",
            result["derived"],
        )
        json.dumps(report)

    def test_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            profiler.create_case("ordered", 1, 42)
        with self.assertRaises(ValueError):
            profiler.run_profile(
                sizes=[2_048],
                repetitions=0,
                cases=["ordered"],
                show_table=False,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
