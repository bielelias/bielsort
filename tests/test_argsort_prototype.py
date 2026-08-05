import gc
import random
import unittest
import weakref

import bielsort
from bielsort_native import _bielsort


def expected_argsort(values, reverse=False):
    return sorted(
        range(len(values)),
        key=values.__getitem__,
        reverse=reverse,
    )


class ComparableValue:
    __slots__ = ("value", "identity", "__weakref__")

    def __init__(self, value, identity):
        self.value = value
        self.identity = identity

    def __lt__(self, other):
        return self.value < other.value


class ArgsortPrototypeTests(unittest.TestCase):
    """Correctness contract for the private compact argsort experiment."""

    def argsort(self, values, reverse=False):
        return _bielsort._argsort_int64_prototype(values, reverse)

    def argsort_with_strategy(self, values, reverse=False):
        return _bielsort._argsort_int64_prototype_with_strategy(
            values,
            reverse,
        )

    def test_prototype_does_not_change_the_public_api(self):
        self.assertFalse(hasattr(bielsort, "argsort"))
        self.assertFalse(hasattr(bielsort, "Permutation"))

    def test_basic_indices_are_stable_and_do_not_mutate_input(self):
        values = [3, -1, 3, 0, -1]
        original = values.copy()

        ascending = self.argsort(values)
        descending = self.argsort(values, reverse=True)

        self.assertEqual(list(ascending), expected_argsort(values))
        self.assertEqual(
            list(descending),
            expected_argsort(values, reverse=True),
        )
        self.assertEqual(values, original)
        self.assertEqual(
            [index for index in descending if values[index] == 3],
            [0, 2],
        )
        self.assertEqual(
            [index for index in descending if values[index] == -1],
            [1, 4],
        )

    def test_native_radix_matches_sorted_for_full_int64_range(self):
        rng = random.Random(2050)
        values = [
            -(1 << 63),
            (1 << 63) - 1,
            0,
            -1,
            1,
            *[
                rng.randint(-(1 << 63), (1 << 63) - 1)
                for _ in range(20_000)
            ],
        ]

        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                permutation, strategy = self.argsort_with_strategy(
                    values,
                    reverse,
                )
                self.assertEqual(
                    list(permutation),
                    expected_argsort(values, reverse),
                )
                self.assertIn("radix nativo estável", strategy)

    def test_native_radix_preserves_duplicate_index_order(self):
        rng = random.Random(2051)
        values = [index % 37 - 18 for index in range(10_000)]
        rng.shuffle(values)

        permutation, strategy = self.argsort_with_strategy(values, True)

        self.assertIn("radix nativo estável", strategy)
        self.assertEqual(
            list(permutation),
            expected_argsort(values, reverse=True),
        )
        for value in range(-18, 19):
            self.assertEqual(
                [index for index in permutation if values[index] == value],
                [index for index, item in enumerate(values) if item == value],
            )

    def test_generic_and_arbitrary_integer_fallbacks_are_compatible(self):
        cases = [
            [ComparableValue(index % 11, index) for index in range(4_096)],
            [
                ((1 << 256) + index) * (-1 if index % 2 else 1)
                for index in range(4_096)
            ],
            tuple(range(4_096, 0, -1)),
        ]
        for values in cases:
            for reverse in (False, True):
                with self.subTest(
                    value_type=type(values[0]).__name__,
                    reverse=reverse,
                ):
                    permutation = self.argsort(values, reverse)
                    self.assertEqual(
                        list(permutation),
                        expected_argsort(values, reverse),
                    )

    def test_nearly_monotonic_inputs_retain_timsort(self):
        values = list(range(10_000))
        values[-2], values[-1] = values[-1], values[-2]

        permutation, strategy = self.argsort_with_strategy(values)

        self.assertEqual(list(permutation), expected_argsort(values))
        self.assertIn("quase monotônica", strategy)

    def test_result_is_an_immutable_compact_buffer_sequence(self):
        values = [3, 1, 2] * 1_000
        permutation = self.argsort(values)
        view = memoryview(permutation)

        self.assertIsInstance(permutation, _bielsort._Permutation)
        self.assertEqual(len(permutation), len(values))
        self.assertEqual(permutation[0], expected_argsort(values)[0])
        self.assertEqual(permutation[-1], expected_argsort(values)[-1])
        self.assertEqual(view.format, "I")
        self.assertEqual(view.itemsize, 4)
        self.assertEqual(view.nbytes, len(values) * 4)
        self.assertEqual(view.shape, (len(values),))
        self.assertEqual(view.strides, (4,))
        self.assertTrue(view.readonly)
        with self.assertRaises(TypeError):
            view[0] = 0
        with self.assertRaises(IndexError):
            _ = permutation[len(values)]
        with self.assertRaises(TypeError):
            _bielsort._Permutation()

    def test_result_does_not_retain_the_input_values(self):
        values = [ComparableValue(index, index) for index in range(2_048)]
        references = [weakref.ref(value) for value in values]

        permutation = self.argsort(values)
        del values
        gc.collect()

        self.assertEqual(len(permutation), 2_048)
        self.assertTrue(all(reference() is None for reference in references))

    def test_rejects_one_shot_iterables(self):
        with self.assertRaisesRegex(TypeError, "reusable sequence"):
            self.argsort(value for value in [3, 1, 2])

    def test_fallback_propagates_comparison_errors(self):
        values = [1, "two", 3] * 1_000
        original = values.copy()

        with self.assertRaises(TypeError):
            self.argsort(values)

        self.assertEqual(values, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
