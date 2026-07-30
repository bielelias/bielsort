import random
import unittest

from bielsort import (
    biel_sort,
    biel_sort_diagnostico,
    biel_sort_in_place,
    biel_sort_in_place_diagnostico,
)


class BielSortStressTests(unittest.TestCase):
    """Deterministic stress coverage for native strategy boundaries."""

    def assert_matches_python(self, values):
        original = values.copy()
        expected = sorted(original)

        self.assertEqual(biel_sort(values), expected)
        self.assertEqual(values, original)

        in_place = original.copy()
        self.assertIsNone(biel_sort_in_place(in_place))
        self.assertEqual(in_place, expected)

    def test_deterministic_randomized_distributions(self):
        rng = random.Random(0xB1E15047)
        sizes = (0, 1, 2, 31, 127, 2_047, 2_048, 2_049, 8_192)

        for iteration in range(72):
            size = sizes[iteration % len(sizes)]
            distribution = iteration % 4

            if distribution == 0:
                values = [rng.randint(-16, 16) for _ in range(size)]
            elif distribution == 1:
                values = [
                    rng.randint(-(1 << 31), (1 << 31) - 1)
                    for _ in range(size)
                ]
            elif distribution == 2:
                values = [
                    rng.randint(-(1 << 63), (1 << 63) - 1)
                    for _ in range(size)
                ]
            else:
                values = list(range(size))
                rng.shuffle(values)

            with self.subTest(
                iteration=iteration,
                size=size,
                distribution=distribution,
            ):
                self.assert_matches_python(values)

    def test_counting_sort_at_selection_threshold(self):
        rng = random.Random(0xC017)
        values = [rng.randint(-125_000, 125_000) for _ in range(250_000)]
        expected = sorted(values)

        result, strategy = biel_sort_diagnostico(values)
        self.assertEqual(result, expected)
        self.assertEqual(strategy, "counting nativo estável")

        in_place = values.copy()
        strategy_in_place = biel_sort_in_place_diagnostico(in_place)
        self.assertEqual(in_place, expected)
        self.assertEqual(strategy_in_place, "counting nativo estável")

    def test_radix_repeated_full_int64_range(self):
        rng = random.Random(0x64B1E1)

        for iteration in range(16):
            values = [
                rng.randint(-(1 << 63), (1 << 63) - 1)
                for _ in range(8_192)
            ]
            with self.subTest(iteration=iteration):
                result, strategy = biel_sort_diagnostico(values)
                self.assertEqual(result, sorted(values))
                self.assertIn("radix nativo", strategy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
