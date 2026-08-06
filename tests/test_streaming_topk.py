import gc
import operator
import random
import unittest
import weakref
from dataclasses import FrozenInstanceError

import bielsort
import bielsort_native
from bielsort_native import _bielsort
from bielsort_native._streaming_topk import (
    _StreamTopKInfo,
    stream_top_k,
)


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
        if self.iterations != 1:
            raise AssertionError("stream was iterated more than once")
        return iter(self.values)


class LessOnly:
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        raise AssertionError("selection must not require equality")


class ExplodingComparison:
    def __lt__(self, other):
        del other
        raise LookupError("comparison sentinel")


class TrackedRecord:
    def __init__(self, value, position):
        self.value = value
        self.position = position


class StreamingTopKTests(unittest.TestCase):
    """Contract for the private bounded-memory streaming experiment."""

    def test_remains_outside_both_public_packages(self):
        for package in (bielsort, bielsort_native):
            for name in (
                "stream_top_k",
                "StreamTopKInfo",
                "top_k",
                "TopKInfo",
            ):
                with self.subTest(package=package.__name__, name=name):
                    self.assertFalse(hasattr(package, name))
                    self.assertNotIn(name, package.__all__)

    def test_natural_and_keyed_domains_match_stable_sort(self):
        rng = random.Random(26_806)
        natural_domains = (
            [rng.randint(-500, 500) for _ in range(5_000)],
            [f"group-{rng.randrange(300):03d}" for _ in range(5_000)],
            [(rng.randrange(50), rng.randrange(70)) for _ in range(5_000)],
        )
        keyed_domains = (
            [(rng.randint(-500, 500), object()) for _ in range(5_000)],
            [((1 << 100) + rng.randrange(500), object()) for _ in range(5_000)],
            [(f"key-{rng.randrange(300):03d}", object()) for _ in range(5_000)],
        )
        for values in natural_domains:
            for k in (1, 100, 1_000, 10_000):
                for largest in (False, True):
                    with self.subTest(
                        domain=type(values[0]).__name__,
                        k=k,
                        largest=largest,
                    ):
                        result = stream_top_k(
                            (value for value in values),
                            k,
                            largest=largest,
                        )
                        expected = sorted(values, reverse=largest)[:k]
                        self.assertEqual(result, expected)

        key = operator.itemgetter(0)
        for records in keyed_domains:
            for k in (1, 100, 1_000, 10_000):
                for largest in (False, True):
                    with self.subTest(
                        domain=type(records[0][0]).__name__,
                        k=k,
                        largest=largest,
                    ):
                        result = stream_top_k(
                            (record for record in records),
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

    def test_one_shot_and_key_once_in_encounter_order(self):
        records = [(position % 97, object()) for position in range(5_000)]
        source = OneShot(records)
        calls = []

        result = stream_top_k(
            source,
            100,
            key=lambda record: calls.append(record) or record[0],
        )
        expected = sorted(records, key=operator.itemgetter(0))[:100]
        assert_identity(self, result, expected)
        self.assertEqual(source.iterations, 1)
        assert_identity(self, calls, records)

    def test_stable_ties_survive_cutoff_replacements(self):
        records = [
            TrackedRecord(5, 0),
            TrackedRecord(5, 1),
            TrackedRecord(4, 2),
            TrackedRecord(6, 3),
            TrackedRecord(6, 4),
            TrackedRecord(7, 5),
        ]
        for largest in (False, True):
            result = stream_top_k(
                records,
                2,
                key=lambda record: LessOnly(record.value),
                largest=largest,
            )
            expected = sorted(
                records,
                key=lambda record: LessOnly(record.value),
                reverse=largest,
            )[:2]
            assert_identity(self, result, expected)

    def test_late_int64_to_generic_switch_reconstructs_cached_keys(self):
        records = [
            (position % 31, object())
            for position in range(300)
        ]
        records.extend(
            ((1 << 100) + position % 17, object())
            for position in range(300, 600)
        )
        for largest in (False, True):
            calls = []

            def key(record):
                calls.append(record)
                return int(record[0])

            result, info = stream_top_k(
                (record for record in records),
                200,
                key=key,
                largest=largest,
                return_info=True,
            )
            expected = sorted(
                records,
                key=operator.itemgetter(0),
                reverse=largest,
            )[:200]
            assert_identity(self, result, expected)
            assert_identity(self, calls, records)
            self.assertEqual(info.algorithm, "native-stream-generic")

    def test_zero_k_does_not_consume_or_validate_key(self):
        source = OneShot([1])
        result, info = stream_top_k(
            source,
            0,
            key=object(),
            max_native_auxiliary_bytes=0,
            return_info=True,
        )
        self.assertEqual(result, [])
        self.assertEqual(source.iterations, 0)
        self.assertEqual(info.algorithm, "trivial")
        self.assertEqual(info.processed, 0)

    def test_k_index_and_invalid_options_precede_iteration(self):
        source = OneShot([3, 1, 2])
        self.assertEqual(stream_top_k(source, IntegerIndex(2)), [1, 2])
        self.assertEqual(source.iterations, 1)

        cases = (
            ({"k": True}, TypeError),
            ({"k": 1.0}, TypeError),
            ({"k": -1}, ValueError),
            ({"k": 1, "largest": 1}, TypeError),
            ({"k": 1, "max_native_auxiliary_bytes": True}, TypeError),
            ({"k": 1, "max_native_auxiliary_bytes": -1}, ValueError),
            ({"k": 1, "on_memory_limit": "sort"}, ValueError),
            ({"k": 1, "return_info": 1}, TypeError),
            ({"k": 1, "key": object()}, TypeError),
        )
        for options, exception in cases:
            source = OneShot([1])
            with self.subTest(options=options):
                with self.assertRaises(exception):
                    stream_top_k(source, **options)
                self.assertEqual(source.iterations, 0)

    def test_memory_guard_decides_before_consumption(self):
        records = [(position % 17, object()) for position in range(200)]
        guarded = OneShot(records)
        calls = []
        with self.assertRaises(MemoryError):
            stream_top_k(
                guarded,
                20,
                key=lambda record: calls.append(record) or record[0],
                max_native_auxiliary_bytes=0,
                on_memory_limit="raise",
            )
        self.assertEqual(guarded.iterations, 0)
        self.assertEqual(calls, [])

        fallback = OneShot(records)
        result, info = stream_top_k(
            fallback,
            20,
            key=operator.itemgetter(0),
            max_native_auxiliary_bytes=0,
            return_info=True,
        )
        expected = sorted(records, key=operator.itemgetter(0))[:20]
        assert_identity(self, result, expected)
        self.assertEqual(fallback.iterations, 1)
        self.assertEqual(info.algorithm, "heapq")
        self.assertEqual(info.processed, len(records))
        self.assertTrue(info.native_memory_limit_exceeded)

    def test_diagnostics_are_frozen_complete_and_truthful(self):
        result, info = stream_top_k(
            ((position % 11, position) for position in range(100)),
            20,
            key=operator.itemgetter(0),
            return_info=True,
        )
        self.assertEqual(len(result), 20)
        self.assertIsInstance(info, _StreamTopKInfo)
        self.assertEqual(info.algorithm, "native-stream-int64")
        self.assertEqual(info.processed, 100)
        self.assertEqual(info.selected, 20)
        self.assertTrue(info.used_native)
        self.assertGreater(info.estimated_native_auxiliary_bytes, 0)
        self.assertGreaterEqual(
            info.worst_case_native_auxiliary_bytes,
            info.estimated_native_auxiliary_bytes,
        )
        with self.assertRaises(FrozenInstanceError):
            info.algorithm = "changed"
        self.assertEqual(
            set(info.as_dict()),
            {
                "algorithm",
                "reason",
                "processed",
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

        _, generic = stream_top_k(
            ["c", "a", "b"],
            2,
            return_info=True,
        )
        self.assertEqual(generic.algorithm, "native-stream-generic")

    def test_rejected_records_are_released_during_iteration(self):
        rejected = []

        def records():
            for position in range(2_000):
                record = TrackedRecord(2_000 - position, position)
                if position < 1_000:
                    rejected.append(weakref.ref(record))
                yield record
                if position == 1_500:
                    gc.collect()
                    self.assertLessEqual(
                        sum(reference() is not None for reference in rejected),
                        16,
                    )

        result = stream_top_k(records(), 10, key=lambda record: record.value)
        self.assertEqual(len(result), 10)

    def test_iteration_key_and_comparison_exceptions_propagate(self):
        def exploding_iterator():
            yield 2
            raise LookupError("iterator sentinel")

        with self.assertRaisesRegex(LookupError, "iterator sentinel"):
            stream_top_k(exploding_iterator(), 1)

        calls = []

        def exploding_key(value):
            calls.append(value)
            if value == 2:
                raise LookupError("key sentinel")
            return value

        with self.assertRaisesRegex(LookupError, "key sentinel"):
            stream_top_k([3, 2, 1], 2, key=exploding_key)
        self.assertEqual(calls, [3, 2])

        with self.assertRaisesRegex(LookupError, "comparison sentinel"):
            stream_top_k(
                range(10),
                3,
                key=lambda value: ExplodingComparison(),
            )

    def test_native_entry_points_and_bound(self):
        values = (value for value in [8, -4, 10, 3, -4])
        result, processed, exact, estimated = (
            _bielsort._stream_topk_prototype_with_info(
                values,
                3,
                None,
                False,
            )
        )
        self.assertEqual(result, [-4, -4, 3])
        self.assertEqual(processed, 5)
        self.assertTrue(exact)
        self.assertGreater(estimated, 0)
        self.assertGreater(
            _bielsort._stream_topk_worst_auxiliary_bytes(3),
            0,
        )
        self.assertEqual(
            _bielsort._stream_topk_worst_auxiliary_bytes(0),
            0,
        )

    def test_randomized_differential(self):
        rng = random.Random(91_926)
        for size in (0, 1, 17, 100, 2_048):
            values = [rng.randint(-500, 500) for _ in range(size)]
            records = [(value, object()) for value in values]
            for k in (0, 1, 7, size // 8, size // 2, size, size + 10):
                for largest in (False, True):
                    with self.subTest(size=size, k=k, largest=largest):
                        natural = stream_top_k(
                            (value for value in values),
                            k,
                            largest=largest,
                        )
                        self.assertEqual(
                            natural,
                            sorted(values, reverse=largest)[:k],
                        )
                        keyed = stream_top_k(
                            (record for record in records),
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
