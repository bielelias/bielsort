import random
import unittest

import bielsort
from bielsort_native import _bielsort


def expected_topk(values, k, largest=False):
    return sorted(
        range(len(values)),
        key=values.__getitem__,
        reverse=largest,
    )[:k]


class TopKPrototypeTests(unittest.TestCase):
    """Correctness contract for the private stable compact top-k experiment."""

    def topk(self, values, k, largest=False):
        return _bielsort._topk_int64_prototype(values, k, largest)

    def topk_with_strategy(self, values, k, largest=False):
        return _bielsort._topk_int64_prototype_with_strategy(
            values,
            k,
            largest,
        )

    def test_prototype_does_not_change_the_public_api(self):
        self.assertFalse(hasattr(bielsort, "topk"))
        self.assertFalse(hasattr(bielsort, "top_k"))

    def test_stable_smallest_and_largest_indices(self):
        values = [5, 1, 5, 2, 1, 5, 2, 1]
        original = values.copy()

        for largest in (False, True):
            with self.subTest(largest=largest):
                order = self.topk(values, 6, largest)
                expected = expected_topk(values, 6, largest)
                self.assertEqual(list(order), expected)
                self.assertEqual(order.apply(values), [values[i] for i in expected])

        self.assertEqual(values, original)

    def test_applies_partial_order_to_parallel_sequences(self):
        scores = [30, 10, 20, 10, 40, 20]
        names = [object() for _ in scores]
        groups = tuple(index % 3 for index in range(len(scores)))
        order = self.topk(scores, 4)
        expected = expected_topk(scores, 4)

        ordered_names = order.apply(names)

        self.assertEqual(order.apply(scores), [scores[index] for index in expected])
        self.assertEqual(order.apply(groups), [groups[index] for index in expected])
        self.assertTrue(
            all(
                ordered_names[position] is names[index]
                for position, index in enumerate(expected)
            )
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            order.apply(scores[:4])

    def test_apply_many_aligns_parallel_sequences_and_identity(self):
        scores = [30, 10, 20, 10, 40, 20]
        names = [object() for _ in scores]
        groups = tuple(index % 3 for index in range(len(scores)))
        order = self.topk(scores, 4)
        expected = expected_topk(scores, 4)

        ordered_scores, ordered_names, ordered_groups = order.apply_many(
            scores,
            names,
            groups,
        )

        self.assertEqual(
            ordered_scores,
            [scores[index] for index in expected],
        )
        self.assertEqual(
            ordered_groups,
            [groups[index] for index in expected],
        )
        self.assertTrue(
            all(
                ordered_names[position] is names[index]
                for position, index in enumerate(expected)
            )
        )

    def test_apply_many_validates_all_inputs_before_application(self):
        values = [3, 1, 2] * 1_000
        order = self.topk(values, 100)

        self.assertEqual(order.apply_many(), ())
        with self.assertRaisesRegex(TypeError, "argument 2"):
            order.apply_many(values, (value for value in values))
        with self.assertRaisesRegex(ValueError, "argument 2"):
            order.apply_many(values, values[:-1])

    def test_randomized_int64_differential(self):
        rng = random.Random(7070)
        values = [
            -(1 << 63),
            (1 << 63) - 1,
            *[
                rng.randint(-(1 << 63), (1 << 63) - 1)
                for _ in range(20_000)
            ],
        ]

        for k in (1, 10, 100, 1_000):
            for largest in (False, True):
                with self.subTest(k=k, largest=largest):
                    order, strategy = self.topk_with_strategy(
                        values,
                        k,
                        largest,
                    )
                    self.assertIn("heap nativo estável int64", strategy)
                    self.assertEqual(
                        list(order),
                        expected_topk(values, k, largest),
                    )

    def test_k_boundaries_and_compact_buffer(self):
        values = list(range(10, 0, -1))

        empty = self.topk(values, 0)
        clamped = self.topk(values, 100)

        self.assertEqual(list(empty), [])
        self.assertEqual(empty.apply(values), [])
        self.assertEqual(list(clamped), expected_topk(values, len(values)))
        view = memoryview(clamped)
        self.assertTrue(view.readonly)
        self.assertEqual(view.itemsize, 4)
        self.assertEqual(view.nbytes, len(values) * 4)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.topk(values, -1)

    def test_large_k_uses_adaptive_full_argsort(self):
        values = [index % 101 - 50 for index in range(10_000, 0, -1)]

        order, strategy = self.topk_with_strategy(values, 5_000)

        self.assertIn("k grande", strategy)
        self.assertEqual(list(order), expected_topk(values, 5_000))

    def test_generic_values_use_compatible_full_argsort(self):
        values = ["delta", "alpha", "charlie", "alpha", "bravo"] * 1_000

        order, strategy = self.topk_with_strategy(values, 100)

        self.assertIn("fora de int64", strategy)
        self.assertEqual(list(order), expected_topk(values, 100))

    def test_rejects_one_shot_iterables(self):
        with self.assertRaisesRegex(TypeError, "reusable sequence"):
            self.topk((value for value in range(10)), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
