import random
import unittest

import bielsort
from bielsort_native import _bielsort


def expected_records(records, k, largest=False):
    return sorted(records, key=lambda record: record[0], reverse=largest)[:k]


class KeyedTopKPrototypeTests(unittest.TestCase):
    """Contract for the private direct stable keyed top-k experiment."""

    def topk(self, records, k, key, largest=False):
        return _bielsort._topk_by_int64_key_prototype(
            records,
            k,
            key,
            largest,
        )

    def test_prototype_does_not_change_the_public_api(self):
        self.assertFalse(hasattr(bielsort, "top_k"))
        self.assertFalse(hasattr(bielsort, "topk"))

    def test_stable_smallest_and_largest_preserve_identity(self):
        records = [
            (5, object()),
            (1, object()),
            (5, object()),
            (2, object()),
            (1, object()),
            (5, object()),
            (1, object()),
        ]
        original = records.copy()

        for largest in (False, True):
            with self.subTest(largest=largest):
                result = self.topk(records, 5, lambda record: record[0], largest)
                expected = expected_records(records, 5, largest)
                self.assertEqual(len(result), len(expected))
                self.assertTrue(
                    all(actual is wanted for actual, wanted in zip(result, expected))
                )

        self.assertEqual(records, original)
        self.assertTrue(
            all(actual is wanted for actual, wanted in zip(records, original))
        )

    def test_key_is_called_exactly_once_per_record(self):
        records = [(index % 7, object()) for index in range(100)]
        calls = []

        def key(record):
            calls.append(record)
            return record[0]

        self.topk(records, 10, key)

        self.assertEqual(len(calls), len(records))
        self.assertTrue(
            all(actual is wanted for actual, wanted in zip(calls, records))
        )

    def test_zero_and_negative_k_do_not_consume_iterable(self):
        consumed = []

        def records():
            consumed.append(True)
            yield (1, object())

        self.assertEqual(self.topk(records(), 0, object()), [])
        self.assertEqual(consumed, [])
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.topk(records(), -1, object())
        self.assertEqual(consumed, [])

    def test_accepts_one_shot_iterable_and_clamps_k(self):
        records = [(3, object()), (1, object()), (2, object())]
        result = self.topk((record for record in records), 100, lambda item: item[0])

        expected = expected_records(records, len(records))
        self.assertTrue(
            all(actual is wanted for actual, wanted in zip(result, expected))
        )

    def test_rejects_non_callable_for_nonempty_selection(self):
        with self.assertRaisesRegex(TypeError, "callable"):
            self.topk([(1, object())], 1, object())

    def test_rejects_non_exact_or_out_of_range_integer_keys(self):
        with self.assertRaisesRegex(TypeError, "exact int"):
            self.topk([(True, object())], 1, lambda record: record[0])
        with self.assertRaises(OverflowError):
            self.topk([((1 << 63), object())], 1, lambda record: record[0])
        with self.assertRaisesRegex(TypeError, "exact int"):
            self.topk([(1.0, object())], 1, lambda record: record[0])

    def test_key_exception_propagates_without_repeating_calls(self):
        records = [(3, object()), (2, object()), (1, object())]
        calls = []

        def key(record):
            calls.append(record)
            if record is records[1]:
                raise LookupError("sentinel")
            return record[0]

        with self.assertRaisesRegex(LookupError, "sentinel"):
            self.topk(records, 2, key)
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0], records[0])
        self.assertIs(calls[1], records[1])

    def test_randomized_int64_differential(self):
        rng = random.Random(8080)
        records = [
            (rng.randint(-(1 << 63), (1 << 63) - 1), object())
            for _ in range(20_000)
        ]

        for k in (1, 10, 100, 1_000):
            for largest in (False, True):
                with self.subTest(k=k, largest=largest):
                    result = self.topk(
                        records,
                        k,
                        lambda record: record[0],
                        largest,
                    )
                    expected = expected_records(records, k, largest)
                    self.assertTrue(
                        all(
                            actual is wanted
                            for actual, wanted in zip(result, expected)
                        )
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
