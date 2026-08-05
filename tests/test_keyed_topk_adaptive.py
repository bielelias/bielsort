import gc
import random
import unittest
import weakref

import bielsort
from bielsort_native import _bielsort
from bielsort_native._keyed_topk import topk_by_key_adaptive


def assert_identity(test_case, actual, expected):
    test_case.assertEqual(len(actual), len(expected))
    test_case.assertTrue(
        all(item is wanted for item, wanted in zip(actual, expected))
    )


class LessOnlyKey:
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        raise AssertionError("stable top-k must not require key equality")


class ExplodingKey:
    def __init__(self, value, explode=False):
        self.value = value
        self.explode = explode

    def __lt__(self, other):
        if self.explode or other.explode:
            raise LookupError("comparison sentinel")
        return self.value < other.value


class TrackedKey:
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value < other.value


class AdaptiveKeyedTopKTests(unittest.TestCase):
    """Semantics for the private adaptive generic-key top-k stage."""

    def test_stage_two_remains_outside_public_api(self):
        self.assertFalse(hasattr(bielsort, "top_k"))
        self.assertFalse(hasattr(bielsort, "topk"))

    def test_generic_domains_match_stable_sort_by_identity(self):
        domains = {
            "huge-int": [
                ((1 << 100) + value % 19, object())
                for value in range(200, 0, -1)
            ],
            "string": [
                (f"{value % 17:02d}", object())
                for value in range(200, 0, -1)
            ],
            "tuple": [
                ((value % 11, value % 7), object())
                for value in range(200, 0, -1)
            ],
            "float": [
                (float(value % 23) / 3.0, object())
                for value in range(200, 0, -1)
            ],
        }
        for name, records in domains.items():
            original = records.copy()
            for largest in (False, True):
                with self.subTest(domain=name, largest=largest):
                    result = topk_by_key_adaptive(
                        records,
                        75,
                        lambda record: record[0],
                        largest=largest,
                    )
                    expected = sorted(
                        records,
                        key=lambda record: record[0],
                        reverse=largest,
                    )[:75]
                    assert_identity(self, result, expected)
            assert_identity(self, records, original)

    def test_late_huge_integer_switches_without_repeating_key(self):
        records = [
            (value if value != 750 else 1 << 100, object())
            for value in range(1_000)
        ]
        calls = []

        def key(record):
            calls.append(record)
            return record[0]

        result, strategy = topk_by_key_adaptive(
            records,
            100,
            key,
            return_strategy=True,
        )
        expected = sorted(records, key=lambda record: record[0])[:100]

        assert_identity(self, result, expected)
        assert_identity(self, calls, records)
        self.assertIn("key Python", strategy)

    def test_exact_int64_keeps_normalized_strategy(self):
        records = [(value % 31 - 15, object()) for value in range(1_000)]

        result, strategy = topk_by_key_adaptive(
            records,
            100,
            lambda record: record[0],
            return_strategy=True,
        )

        expected = sorted(records, key=lambda record: record[0])[:100]
        assert_identity(self, result, expected)
        self.assertIn("key int64", strategy)

    def test_less_only_keys_preserve_stable_ties(self):
        records = [(value % 9, object()) for value in range(500)]

        for largest in (False, True):
            with self.subTest(largest=largest):
                result = topk_by_key_adaptive(
                    records,
                    200,
                    lambda record: LessOnlyKey(record[0]),
                    largest=largest,
                )
                expected = sorted(
                    records,
                    key=lambda record: LessOnlyKey(record[0]),
                    reverse=largest,
                )[:200]
                assert_identity(self, result, expected)

    def test_key_calls_once_and_zero_k_consumes_nothing(self):
        consumed = []

        def values():
            consumed.append(True)
            yield (1, object())

        self.assertEqual(topk_by_key_adaptive(values(), 0, object()), [])
        self.assertEqual(consumed, [])

        records = [(value % 5, object()) for value in range(100)]
        calls = []
        topk_by_key_adaptive(
            (record for record in records),
            10,
            lambda record: calls.append(record) or record[0],
        )
        assert_identity(self, calls, records)

    def test_key_and_comparison_exceptions_propagate(self):
        records = [(value, object()) for value in range(20)]
        calls = []

        def key(record):
            calls.append(record)
            if record is records[7]:
                raise RuntimeError("key sentinel")
            return record[0]

        with self.assertRaisesRegex(RuntimeError, "key sentinel"):
            topk_by_key_adaptive(records, 5, key)
        self.assertEqual(len(calls), 8)
        self.assertEqual(len({id(record) for record in calls}), len(calls))

        exploding = [
            (ExplodingKey(value, explode=value == 7), object())
            for value in range(20)
        ]
        with self.assertRaisesRegex(LookupError, "comparison sentinel"):
            topk_by_key_adaptive(exploding, 5, lambda record: record[0])

    def test_temporary_selected_keys_are_released(self):
        records = [(value, object()) for value in range(100)]
        references = []

        def key(record):
            key_object = TrackedKey(record[0])
            references.append(weakref.ref(key_object))
            return key_object

        result = topk_by_key_adaptive(records, 10, key)
        self.assertEqual(len(result), 10)
        gc.collect()
        self.assertTrue(all(reference() is None for reference in references))

    def test_memory_guard_falls_back_or_raises_before_key(self):
        records = [(value % 17, object()) for value in range(1_000)]
        calls = []

        result, strategy = topk_by_key_adaptive(
            records,
            100,
            lambda record: calls.append(record) or record[0],
            max_native_auxiliary_bytes=0,
            return_strategy=True,
        )
        expected = sorted(records, key=lambda record: record[0])[:100]
        assert_identity(self, result, expected)
        assert_identity(self, calls, records)
        self.assertIn("heapq", strategy)

        calls.clear()
        with self.assertRaises(MemoryError):
            topk_by_key_adaptive(
                records,
                100,
                lambda record: calls.append(record) or record[0],
                max_native_auxiliary_bytes=0,
                on_exceeded="raise",
            )
        self.assertEqual(calls, [])

    def test_memory_guard_exact_boundary_uses_native_path(self):
        records = [(value % 17, object()) for value in range(1_000)]
        boundary = _bielsort._topk_by_key_worst_auxiliary_bytes(100)

        result, strategy = topk_by_key_adaptive(
            records,
            100,
            lambda record: record[0],
            max_native_auxiliary_bytes=boundary,
            return_strategy=True,
        )
        expected = sorted(records, key=lambda record: record[0])[:100]
        assert_identity(self, result, expected)
        self.assertIn("key int64", strategy)
        self.assertGreater(boundary, 0)

    def test_memory_guard_and_options_validate(self):
        with self.assertRaisesRegex(TypeError, "exact list or tuple"):
            topk_by_key_adaptive(
                (value for value in range(10)),
                3,
                lambda value: value,
                max_native_auxiliary_bytes=1_000,
            )
        with self.assertRaisesRegex(TypeError, "k must"):
            topk_by_key_adaptive([], True, lambda value: value)
        with self.assertRaisesRegex(TypeError, "largest"):
            topk_by_key_adaptive([], 1, lambda value: value, largest=1)
        with self.assertRaisesRegex(ValueError, "on_exceeded"):
            topk_by_key_adaptive([], 1, lambda value: value, on_exceeded="x")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            _bielsort._topk_by_key_worst_auxiliary_bytes(-1)

    def test_randomized_generic_differential(self):
        rng = random.Random(9090)
        factories = (
            lambda value: (1 << 100) + value,
            lambda value: f"{value:08d}",
            lambda value: (value % 101, value),
            lambda value: value / 17.0,
        )
        for factory in factories:
            records = [
                (factory(rng.randrange(10_000)), object())
                for _ in range(5_000)
            ]
            for k in (1, 10, 100, 1_000):
                for largest in (False, True):
                    result = topk_by_key_adaptive(
                        records,
                        k,
                        lambda record: record[0],
                        largest=largest,
                    )
                    expected = sorted(
                        records,
                        key=lambda record: record[0],
                        reverse=largest,
                    )[:k]
                    assert_identity(self, result, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
