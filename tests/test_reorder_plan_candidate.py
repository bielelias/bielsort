import gc
import inspect
import pickle
import random
import unittest
import weakref

import bielsort
import bielsort_native
from bielsort_native import _bielsort
from bielsort_native._reorder_plan import Permutation, argsort


def expected_argsort(values, reverse=False):
    return sorted(
        range(len(values)),
        key=values.__getitem__,
        reverse=reverse,
    )


class TrackedValue:
    __slots__ = ("value", "position", "__weakref__")

    def __init__(self, value, position):
        self.value = value
        self.position = position

    def __lt__(self, other):
        return self.value < other.value


class ReusableSequence:
    def __init__(self, values):
        self.values = list(values)

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        return self.values[index]


class SourceClearingValue:
    def __init__(self, value, source):
        self.value = value
        self.source = source

    def __lt__(self, other):
        self.source.clear()
        return self.value < other.value


class ReorderPlanCandidateTests(unittest.TestCase):
    """Frozen contract for the private reusable reorder-plan candidate."""

    def test_candidate_remains_outside_both_public_packages(self):
        for package in (bielsort, bielsort_native):
            for name in ("argsort", "Permutation"):
                with self.subTest(package=package.__name__, name=name):
                    self.assertFalse(hasattr(package, name))
                    self.assertNotIn(name, package.__all__)

    def test_provisional_signature_is_keyword_only(self):
        signature = inspect.signature(argsort)
        parameters = list(signature.parameters.values())

        self.assertEqual(
            [parameter.name for parameter in parameters],
            ["values", "reverse"],
        )
        self.assertIs(
            parameters[1].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIs(signature.return_annotation, _bielsort._Permutation)
        with self.assertRaises(TypeError):
            argsort([3, 1, 2], True)

    def test_signed_int64_order_is_stable_in_both_directions(self):
        rng = random.Random(30_030)
        values = [
            -(1 << 63),
            (1 << 63) - 1,
            0,
            0,
            *[rng.randint(-(1 << 63), (1 << 63) - 1) for _ in range(10_000)],
        ]
        original = values.copy()

        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                order = argsort(values, reverse=reverse)
                self.assertEqual(
                    list(order),
                    expected_argsort(values, reverse),
                )
                zero_indices = [index for index in order if values[index] == 0]
                self.assertEqual(zero_indices, sorted(zero_indices))

        self.assertEqual(values, original)

    def test_generic_and_large_integer_fallbacks_are_stable(self):
        cases = (
            [TrackedValue(index % 19, index) for index in range(4_096)],
            [
                ((1 << 200) + index % 31) * (-1 if index % 3 else 1)
                for index in range(4_096)
            ],
            tuple(f"group-{index % 23:02d}" for index in range(4_096)),
        )
        for values in cases:
            for reverse in (False, True):
                with self.subTest(
                    domain=type(values[0]).__name__,
                    reverse=reverse,
                ):
                    self.assertEqual(
                        list(argsort(values, reverse=reverse)),
                        expected_argsort(values, reverse),
                    )

    def test_fast_sequence_inputs_cover_every_private_route(self):
        rng = random.Random(90_051)
        cases = (
            [3],
            list(range(4_096)),
            [
                rng.randint(-(1 << 63), (1 << 63) - 1)
                for _ in range(4_096)
            ],
            [TrackedValue(index % 17, index) for index in range(4_096)],
            [(1 << 200) + index % 29 for index in range(4_096)],
        )
        for original in cases:
            for container in (list, tuple):
                values = container(original)
                for reverse in (False, True):
                    with self.subTest(
                        route=type(original[0]).__name__,
                        container=container.__name__,
                        reverse=reverse,
                    ):
                        self.assertEqual(
                            list(argsort(values, reverse=reverse)),
                            expected_argsort(values, reverse),
                        )

    def test_materialized_reusable_sequences_remain_compatible(self):
        class ListSubclass(list):
            pass

        original = [index % 31 for index in range(4_096, 0, -1)]
        for values in (
            ListSubclass(original),
            ReusableSequence(original),
        ):
            with self.subTest(container=type(values).__name__):
                self.assertEqual(
                    list(argsort(values)),
                    expected_argsort(values),
                )

    def test_comparison_can_resize_exact_source_without_corruption(self):
        source = []
        numeric_values = [index % 37 for index in range(4_096, 0, -1)]
        source.extend(
            SourceClearingValue(value, source)
            for value in numeric_values
        )
        expected = sorted(
            range(len(numeric_values)),
            key=numeric_values.__getitem__,
        )

        order = argsort(source)

        self.assertEqual(list(order), expected)
        self.assertEqual(len(order), len(numeric_values))
        self.assertEqual(source, [])

    def test_trivial_and_all_equal_inputs_return_identity(self):
        for values in ([], [7], [5] * 10_000):
            for reverse in (False, True):
                with self.subTest(size=len(values), reverse=reverse):
                    self.assertEqual(
                        list(argsort(values, reverse=reverse)),
                        list(range(len(values))),
                    )

    def test_compact_result_is_immutable_and_has_no_value_semantics(self):
        first = argsort([3, 1, 2] * 1_000)
        second = argsort([3, 1, 2] * 1_000)
        view = memoryview(first)

        self.assertIsInstance(first, Permutation)
        self.assertIs(Permutation, _bielsort._Permutation)
        self.assertEqual(first[-1], list(first)[-1])
        self.assertEqual(view.format, "I")
        self.assertEqual(view.itemsize, 4)
        self.assertEqual(view.nbytes, len(first) * 4)
        self.assertEqual(view.shape, (len(first),))
        self.assertEqual(view.strides, (4,))
        self.assertTrue(view.c_contiguous)
        self.assertTrue(view.readonly)
        self.assertIsNot(first, second)
        self.assertNotEqual(first, second)
        with self.assertRaises(TypeError):
            first[:1]
        with self.assertRaises(TypeError):
            view[0] = 0
        with self.assertRaises(TypeError):
            pickle.dumps(first)
        with self.assertRaises(TypeError):
            Permutation()

    def test_buffer_keeps_its_owner_alive(self):
        order = argsort([3, 1, 2] * 1_000)
        expected = list(order)
        view = memoryview(order)

        del order
        gc.collect()

        self.assertEqual(view.tolist(), expected)

    def test_private_fixture_covers_both_buffer_widths(self):
        for itemsize, format_code in ((4, "I"), (8, "Q")):
            with self.subTest(itemsize=itemsize):
                order = _bielsort._permutation_fixture(
                    [2, 0, 1],
                    3,
                    itemsize,
                )
                view = memoryview(order)

                self.assertEqual(list(order), [2, 0, 1])
                self.assertEqual(order.apply(["a", "b", "c"]), ["c", "a", "b"])
                self.assertEqual(view.format, format_code)
                self.assertEqual(view.itemsize, itemsize)
                self.assertEqual(view.nbytes, 3 * itemsize)
                self.assertTrue(view.readonly)

    def test_result_does_not_retain_source_values(self):
        values = [TrackedValue(index, index) for index in range(2_048)]
        references = [weakref.ref(value) for value in values]

        order = argsort(values)
        del values
        gc.collect()

        self.assertEqual(len(order), 2_048)
        self.assertTrue(all(reference() is None for reference in references))

    def test_apply_reuses_order_and_preserves_exact_identity(self):
        keys = [7, 2, 7, 1] * 2_500
        first = [object() for _ in keys]
        second = tuple(object() for _ in keys)
        order = argsort(keys, reverse=True)

        for source in (keys, first, second, "abcd" * 2_500):
            with self.subTest(source_type=type(source).__name__):
                result = order.apply(source)
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), len(source))
                self.assertTrue(
                    all(
                        item is source[index]
                        for item, index in zip(result, order)
                    )
                )

    def test_reusable_sequence_errors_are_public_quality(self):
        with self.assertRaisesRegex(
            TypeError,
            "argsort requires a reusable sequence",
        ) as captured:
            argsort(value for value in [3, 1, 2])
        self.assertNotIn("prototype", str(captured.exception))

        order = argsort([3, 1, 2])
        with self.assertRaisesRegex(
            TypeError,
            "Permutation.apply requires a reusable sequence",
        ) as captured:
            order.apply(value for value in range(3))
        self.assertNotIn("prototype", str(captured.exception))

        with self.assertRaisesRegex(
            ValueError,
            "source length 3 does not match sequence length 2",
        ):
            order.apply([1, 2])

    def test_comparison_errors_propagate_without_input_mutation(self):
        values = [1, "two", 3] * 1_000
        original = values.copy()

        with self.assertRaises(TypeError):
            argsort(values)

        self.assertEqual(values, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
