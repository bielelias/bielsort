import operator
import random
import unittest
from dataclasses import FrozenInstanceError

import bielsort
import bielsort_native
from bielsort_native import _bielsort
from bielsort_native._topk_facade import _TopKInfo, top_k_adaptive


def assert_identity(test_case, actual, expected):
    test_case.assertEqual(len(actual), len(expected))
    test_case.assertTrue(
        all(item is wanted for item, wanted in zip(actual, expected))
    )


class IntegerIndex:
    def __init__(self, value):
        self.value = value

    def __index__(self):
        return self.value


class OneShot:
    def __init__(self, values):
        self.values = values
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("iterated twice")
        return iter(self.values)


class LessOnly:
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        raise AssertionError("stable selection must not require equality")


class ExplodingComparison:
    def __lt__(self, other):
        del other
        raise LookupError("comparison sentinel")


class MutatingComparison:
    def __init__(self, value, source):
        self.value = value
        self.source = source

    def __lt__(self, other):
        self.source.clear()
        return self.value < other.value


class UnifiedTopKFacadeTests(unittest.TestCase):
    """Contract for the private natural/keyed top-k façade."""

    def test_remains_outside_both_public_packages(self):
        for package in (bielsort, bielsort_native):
            for name in ("top_k", "top_k_with_info", "TopKInfo", "_TopKInfo"):
                with self.subTest(package=package.__name__, name=name):
                    self.assertFalse(hasattr(package, name))
                    self.assertNotIn(name, package.__all__)

    def test_natural_int64_and_string_match_stable_sort(self):
        rng = random.Random(12_345)
        domains = (
            [rng.randint(-500, 500) for _ in range(5_000)],
            [f"group-{rng.randrange(300):03d}" for _ in range(5_000)],
        )
        for values in domains:
            original = values.copy()
            for k in (1, 100, 625, 2_000, 10_000):
                for largest in (False, True):
                    with self.subTest(
                        domain=type(values[0]).__name__,
                        k=k,
                        largest=largest,
                    ):
                        result = top_k_adaptive(
                            values,
                            k,
                            largest=largest,
                        )
                        expected = sorted(values, reverse=largest)[:k]
                        assert_identity(self, result, expected)
            assert_identity(self, values, original)

    def test_explicit_key_domains_match_by_identity(self):
        rng = random.Random(54_321)
        domains = (
            [(rng.randint(-500, 500), object()) for _ in range(5_000)],
            [((1 << 100) + rng.randrange(1_000), object()) for _ in range(5_000)],
            [(f"key-{rng.randrange(500):03d}", object()) for _ in range(5_000)],
            [((rng.randrange(20), rng.randrange(30)), object()) for _ in range(5_000)],
        )
        key = operator.itemgetter(0)
        for records in domains:
            original = records.copy()
            for k in (1, 100, 625, 2_000, 10_000):
                for largest in (False, True):
                    with self.subTest(
                        key_type=type(records[0][0]).__name__,
                        k=k,
                        largest=largest,
                    ):
                        result = top_k_adaptive(
                            records,
                            k,
                            key=key,
                            largest=largest,
                        )
                        expected = sorted(
                            records,
                            key=key,
                            reverse=largest,
                        )[:k]
                        assert_identity(self, result, expected)
            assert_identity(self, records, original)

    def test_fixed_routes_and_normalized_diagnostics(self):
        rng = random.Random(7_777)
        int_values = [rng.randint(-2_500, 2_500) for _ in range(5_000)]
        strings = [f"key-{rng.randrange(503):03d}" for _ in range(5_000)]
        exact_records = [(value, object()) for value in int_values]
        generic_records = [((1 << 100) + value, object()) for value in int_values]

        cases = (
            (int_values, None, 100, "native-int64"),
            (int_values, None, 625, "native-int64"),
            (strings, None, 100, "heapq"),
            (strings, None, 625, "timsort"),
            (exact_records, operator.itemgetter(0), 100, "native-int64"),
            (exact_records, operator.itemgetter(0), 625, "native-int64"),
            (generic_records, operator.itemgetter(0), 100, "native-generic"),
            (generic_records, operator.itemgetter(0), 625, "timsort"),
        )
        for values, key, k, algorithm in cases:
            with self.subTest(key=key, k=k, algorithm=algorithm):
                result, info = top_k_adaptive(
                    values,
                    k,
                    key=key,
                    return_info=True,
                )
                expected = sorted(values, key=key)[:k]
                assert_identity(self, result, expected)
                self.assertEqual(info.algorithm, algorithm)
                self.assertEqual(info.used_native, algorithm.startswith("native-"))
                self.assertEqual(info.size, len(values))
                self.assertEqual(info.requested_k, k)
                self.assertEqual(info.selected, k)

    def test_small_partial_selection_uses_heapq(self):
        values = list(range(100, 0, -1))
        result, info = top_k_adaptive(values, 5, return_info=True)
        self.assertEqual(result, [1, 2, 3, 4, 5])
        self.assertEqual(info.algorithm, "heapq")

        records = [(value, object()) for value in values]
        result, info = top_k_adaptive(
            records,
            5,
            key=operator.itemgetter(0),
            return_info=True,
        )
        assert_identity(
            self,
            result,
            sorted(records, key=operator.itemgetter(0))[:5],
        )
        self.assertEqual(info.algorithm, "heapq")

    def test_key_is_called_once_in_order_on_partial_and_full_routes(self):
        records = [(position % 101, object()) for position in range(5_000)]
        expected_ids = [id(record) for record in records]
        for k in (100, 625):
            for largest in (False, True):
                calls = []

                def key(record):
                    calls.append(id(record))
                    return record[0]

                result = top_k_adaptive(
                    records,
                    k,
                    key=key,
                    largest=largest,
                )
                expected = sorted(
                    records,
                    key=operator.itemgetter(0),
                    reverse=largest,
                )[:k]
                assert_identity(self, result, expected)
                self.assertEqual(calls, expected_ids)

    def test_zero_k_does_not_consume_or_validate_key(self):
        consumed = []

        def values():
            consumed.append(True)
            yield 1

        result, info = top_k_adaptive(
            values(),
            0,
            key=object(),
            max_native_auxiliary_bytes=0,
            return_info=True,
        )
        self.assertEqual(result, [])
        self.assertEqual(consumed, [])
        self.assertEqual(info.algorithm, "trivial")
        self.assertEqual(info.max_native_auxiliary_bytes, 0)

    def test_k_accepts_index_and_rejects_invalid_values_before_iteration(self):
        values = OneShot([3, 1, 2])
        self.assertEqual(top_k_adaptive(values, IntegerIndex(2)), [1, 2])
        self.assertEqual(values.iterations, 1)

        for invalid, exception in (
            (True, TypeError),
            (1.0, TypeError),
            (-1, ValueError),
        ):
            source = OneShot([1])
            with self.subTest(invalid=invalid):
                with self.assertRaises(exception):
                    top_k_adaptive(source, invalid)
                self.assertEqual(source.iterations, 0)

    def test_one_shot_iterable_is_materialized_once(self):
        records = [(position % 97, object()) for position in range(5_000)]
        source = OneShot(records)
        calls = []

        result = top_k_adaptive(
            source,
            100,
            key=lambda record: calls.append(id(record)) or record[0],
        )
        expected = sorted(records, key=operator.itemgetter(0))[:100]
        assert_identity(self, result, expected)
        self.assertEqual(source.iterations, 1)
        self.assertEqual(calls, [id(record) for record in records])

    def test_less_only_generic_keys_keep_stable_ties(self):
        records = [(position % 19, object()) for position in range(5_000)]
        for k in (100, 625):
            for largest in (False, True):
                result = top_k_adaptive(
                    records,
                    k,
                    key=lambda record: LessOnly(record[0]),
                    largest=largest,
                )
                expected = sorted(
                    records,
                    key=lambda record: LessOnly(record[0]),
                    reverse=largest,
                )[:k]
                assert_identity(self, result, expected)

    def test_iteration_key_and_comparison_exceptions_propagate(self):
        def exploding_iterator():
            yield (1, object())
            raise LookupError("iterator sentinel")

        with self.assertRaisesRegex(LookupError, "iterator sentinel"):
            top_k_adaptive(
                exploding_iterator(),
                2,
                key=operator.itemgetter(0),
            )

        records = [(position, object()) for position in range(5_000)]
        with self.assertRaisesRegex(LookupError, "key sentinel"):
            top_k_adaptive(
                records,
                100,
                key=lambda record: (_ for _ in ()).throw(
                    LookupError("key sentinel")
                ),
            )
        with self.assertRaisesRegex(LookupError, "comparison sentinel"):
            top_k_adaptive(
                records,
                100,
                key=lambda record: ExplodingComparison(),
            )

    def test_callback_resize_is_safe_on_partial_native_route(self):
        records = [(position, object()) for position in range(5_000)]

        def mutating_key(record):
            records.clear()
            return record[0]

        with self.assertRaisesRegex(RuntimeError, "input changed size"):
            top_k_adaptive(records, 100, key=mutating_key)

        records = [(position, object()) for position in range(5_000)]
        with self.assertRaisesRegex(RuntimeError, "input changed size"):
            top_k_adaptive(
                records,
                100,
                key=lambda record: MutatingComparison(record[0], records),
            )

    def test_memory_guard_fallback_and_raise_happen_before_key(self):
        records = [(position % 101, object()) for position in range(5_000)]
        for k in (100, 625):
            calls = []
            result, info = top_k_adaptive(
                records,
                k,
                key=lambda record: calls.append(id(record)) or record[0],
                max_native_auxiliary_bytes=0,
                return_info=True,
            )
            expected = sorted(records, key=operator.itemgetter(0))[:k]
            assert_identity(self, result, expected)
            self.assertEqual(calls, [id(record) for record in records])
            self.assertEqual(info.algorithm, "heapq")
            self.assertTrue(info.native_memory_limit_exceeded)
            self.assertGreater(info.worst_case_native_auxiliary_bytes, 0)

            calls.clear()
            with self.assertRaises(MemoryError):
                top_k_adaptive(
                    records,
                    k,
                    key=lambda record: calls.append(id(record)) or record[0],
                    max_native_auxiliary_bytes=0,
                    on_memory_limit="raise",
                )
            self.assertEqual(calls, [])

    def test_natural_int64_memory_guard_and_generic_non_native_route(self):
        values = list(range(5_000, 0, -1))
        result, info = top_k_adaptive(
            values,
            100,
            max_native_auxiliary_bytes=0,
            return_info=True,
        )
        self.assertEqual(result, list(range(1, 101)))
        self.assertEqual(info.algorithm, "heapq")
        self.assertTrue(info.native_memory_limit_exceeded)

        strings = [f"value-{index:05d}" for index in range(5_000, 0, -1)]
        result, info = top_k_adaptive(
            strings,
            100,
            max_native_auxiliary_bytes=0,
            return_info=True,
        )
        self.assertEqual(result, sorted(strings)[:100])
        self.assertEqual(info.algorithm, "heapq")
        self.assertFalse(info.native_memory_limit_exceeded)
        self.assertEqual(info.worst_case_native_auxiliary_bytes, 0)

    def test_memory_guard_requires_exact_container_and_valid_options(self):
        with self.assertRaisesRegex(TypeError, "exact list or tuple"):
            top_k_adaptive(
                (value for value in range(10)),
                1,
                max_native_auxiliary_bytes=1_000,
            )
        with self.assertRaisesRegex(TypeError, "largest"):
            top_k_adaptive([], 1, largest=1)
        with self.assertRaisesRegex(TypeError, "max_native"):
            top_k_adaptive([], 1, max_native_auxiliary_bytes=True)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            top_k_adaptive([], 1, max_native_auxiliary_bytes=-1)
        with self.assertRaisesRegex(ValueError, "on_memory_limit"):
            top_k_adaptive([], 1, on_memory_limit="sort")
        with self.assertRaisesRegex(TypeError, "return_info"):
            top_k_adaptive([], 1, return_info=1)
        with self.assertRaisesRegex(TypeError, "key"):
            top_k_adaptive([1], 1, key=object())

    def test_info_is_frozen_complete_and_json_compatible(self):
        result, info = top_k_adaptive(
            [8, -4, 10, 3, -4],
            3,
            return_info=True,
        )
        self.assertEqual(result, [-4, -4, 3])
        self.assertIsInstance(info, _TopKInfo)
        with self.assertRaises(FrozenInstanceError):
            info.algorithm = "changed"
        fields = info.as_dict()
        self.assertEqual(fields["algorithm"], info.algorithm)
        self.assertEqual(fields["used_native"], info.used_native)
        self.assertEqual(
            set(fields),
            {
                "algorithm",
                "reason",
                "size",
                "requested_k",
                "selected",
                "largest",
                "key_domain",
                "estimated_native_auxiliary_bytes",
                "worst_case_native_auxiliary_bytes",
                "max_native_auxiliary_bytes",
                "native_memory_limit_exceeded",
                "used_native",
            },
        )

    def test_native_structured_diagnostics_and_classifier(self):
        self.assertTrue(
            _bielsort._is_exact_int64_sequence_prototype([-(1 << 63), 0, (1 << 63) - 1])
        )
        for values in ([1, True], [1, 1 << 100], [1, "2"]):
            with self.subTest(values=values):
                self.assertFalse(
                    _bielsort._is_exact_int64_sequence_prototype(values)
                )
        with self.assertRaisesRegex(TypeError, "reusable sequence"):
            _bielsort._is_exact_int64_sequence_prototype(
                (value for value in range(3))
            )

        records = [(position % 17, object()) for position in range(5_000)]
        result, info = _bielsort._topk_by_key_prototype_with_info(
            records,
            100,
            operator.itemgetter(0),
        )
        assert_identity(
            self,
            result,
            sorted(records, key=operator.itemgetter(0))[:100],
        )
        self.assertEqual(info["algorithm"], "native-int64")
        self.assertEqual(info["size"], len(records))
        self.assertEqual(info["selected"], 100)
        self.assertGreater(info["estimated_native_auxiliary_bytes"], 0)
        self.assertGreaterEqual(
            info["worst_case_native_auxiliary_bytes"],
            info["estimated_native_auxiliary_bytes"],
        )

    def test_randomized_differential(self):
        rng = random.Random(91_919)
        for size in (0, 1, 17, 100, 2_048, 5_000):
            values = [rng.randint(-500, 500) for _ in range(size)]
            records = [(value, object()) for value in values]
            for k in (0, 1, 7, size // 8, size // 2, size, size + 10):
                for largest in (False, True):
                    with self.subTest(size=size, k=k, largest=largest):
                        natural = top_k_adaptive(
                            values,
                            k,
                            largest=largest,
                        )
                        self.assertEqual(
                            natural,
                            sorted(values, reverse=largest)[:k],
                        )
                        keyed = top_k_adaptive(
                            records,
                            k,
                            key=operator.itemgetter(0),
                            largest=largest,
                        )
                        expected = sorted(
                            records,
                            key=operator.itemgetter(0),
                            reverse=largest,
                        )[:k]
                        assert_identity(self, keyed, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
