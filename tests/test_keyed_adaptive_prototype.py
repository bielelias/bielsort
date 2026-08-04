import gc
import random
import unittest
from operator import attrgetter

import bielsort
from benchmarks.keyed_adaptive_prototype import sort_by_key_adaptive
from benchmarks.keyed_int64_guard import (
    native_worst_case_variable_auxiliary_bytes,
)
from bielsort_native import _bielsort


class Record:
    __slots__ = ("key", "position")

    def __init__(self, key, position):
        self.key = key
        self.position = position


class LessThanOnlyKey:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        raise AssertionError("Timsort key ordering must not require equality")


class KeyedAdaptivePrototypeTests(unittest.TestCase):
    def test_int64_keys_select_native_and_call_key_once(self):
        key_values = [3, -1, 7, 0] * 1_024
        values = [
            Record(key, position)
            for position, key in enumerate(key_values)
        ]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_key_adaptive(
            values,
            key,
            return_info=True,
        )

        expected = sorted(values, key=attrgetter("key"))
        self.assertEqual(result, expected)
        self.assertEqual(calls, list(range(len(values))))
        self.assertTrue(info["native_eligible"])
        self.assertIn(info["algorithm"], {"counting", "radix"})
        self.assertFalse(info["cached_key_fallback"])
        self.assertEqual(info["guard"]["decision"], "native")
        self.assertEqual(
            [item.position for item in values],
            list(range(len(values))),
        )

    def test_dense_keyed_counting_boundary_is_stable(self):
        below = [
            Record(position % 128, position)
            for position in range(8_191)
        ]
        at_boundary = [
            Record(position % 128, position)
            for position in range(8_192)
        ]

        below_result, below_info = sort_by_key_adaptive(
            below,
            attrgetter("key"),
            return_info=True,
        )
        boundary_result, boundary_info = sort_by_key_adaptive(
            at_boundary,
            attrgetter("key"),
            return_info=True,
        )

        self.assertEqual(
            below_result,
            sorted(below, key=attrgetter("key")),
        )
        self.assertEqual(
            boundary_result,
            sorted(at_boundary, key=attrgetter("key")),
        )
        self.assertEqual(below_info["algorithm"], "radix")
        self.assertEqual(boundary_info["algorithm"], "counting")

    def test_sparse_nearly_ordered_prefix_selects_timsort_once(self):
        values = [
            Record(position * 1_000_000, position)
            for position in range(10_000)
        ]
        values[10].key, values[4_000].key = (
            values[4_000].key,
            values[10].key,
        )
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_key_adaptive(
            values,
            key,
            return_info=True,
        )

        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertEqual(calls, list(range(len(values))))
        self.assertEqual(info["algorithm"], "timsort-sparse-run-replay")
        self.assertEqual(info["cached_key_mode"], "adaptive-prefix")

    def test_ordered_prefix_with_random_tail_stays_native(self):
        rng = random.Random(2026080403)
        keys = [position * 1_000_000 for position in range(512)]
        keys.extend(
            rng.randint(-(1 << 63), (1 << 63) - 1)
            for _ in range(10_000 - len(keys))
        )
        values = [
            Record(key, position)
            for position, key in enumerate(keys)
        ]

        result, info = sort_by_key_adaptive(
            values,
            attrgetter("key"),
            return_info=True,
        )

        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertEqual(info["algorithm"], "radix")

    def test_sparse_monotonic_input_keeps_native_result(self):
        values = [
            Record(position * 1_000_000, position)
            for position in range(10_000)
        ]
        result, info = sort_by_key_adaptive(
            values,
            attrgetter("key"),
            return_info=True,
        )
        self.assertEqual(result, values)
        self.assertEqual(info["algorithm"], "already-sorted")

    def test_string_keys_use_cached_timsort_stably(self):
        key_values = ["b", "a", "b", "a"] * 1_024
        values = [
            Record(key, position)
            for position, key in enumerate(key_values)
        ]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_key_adaptive(
            values,
            key,
            return_info=True,
        )

        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertEqual(calls, list(range(len(values))))
        self.assertEqual(
            info["algorithm"],
            "timsort-progressive-key-replay",
        )
        self.assertFalse(info["native_eligible"])
        self.assertTrue(info["cached_key_fallback"])
        self.assertEqual(info["key_calls"], len(values))

    def test_cached_fallback_uses_less_than_not_equality(self):
        values = [
            Record(LessThanOnlyKey(value), position)
            for position, value in enumerate([2, 1, 2, 1] * 1_024)
        ]
        result = sort_by_key_adaptive(values, attrgetter("key"))
        self.assertEqual(result, sorted(values, key=attrgetter("key")))

    def test_huge_integer_keys_fallback_without_a_second_key_call(self):
        key_values = [1 << 100, -(1 << 100), 0] * 1_366
        values = [
            Record(key, position)
            for position, key in enumerate(key_values)
        ]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_key_adaptive(values, key, return_info=True)
        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertEqual(calls, list(range(len(values))))
        self.assertEqual(
            info["algorithm"],
            "timsort-progressive-key-replay",
        )

    def test_prefix_replay_propagates_late_key_exception_once(self):
        values = [Record(str(position), position) for position in range(4_096)]
        calls = []

        def key(record):
            calls.append(record.position)
            if record.position == 100:
                raise RuntimeError("late prefix-replay failure")
            return record.key

        with self.assertRaisesRegex(RuntimeError, "late prefix-replay failure"):
            sort_by_key_adaptive(values, key)
        self.assertEqual(calls, list(range(101)))
        self.assertEqual(
            [item.position for item in values],
            list(range(len(values))),
        )

    def test_late_incompatible_key_uses_progressive_replay_once(self):
        values = [
            Record(key, position)
            for position, key in enumerate([3, -1, 7, 0] * 1_024)
        ]
        values[-1].key = 1 << 100
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_key_adaptive(values, key, return_info=True)
        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertEqual(calls, list(range(len(values))))
        self.assertEqual(
            info["algorithm"],
            "timsort-progressive-key-replay",
        )
        self.assertEqual(info["cached_key_mode"], "progressive-prefix")

    def test_fused_prefix_entry_consumes_cache_and_calls_remaining_once(self):
        values = [
            Record(key, position)
            for position, key in enumerate([3, -1, 7, 0] * 1_024)
        ]
        prefix_size = 64
        cached_keys = [value.key for value in values[:prefix_size]]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result = (
            _bielsort._try_sort_by_prefix_cached_int64_keys_prototype(
                values,
                cached_keys,
                key,
            )
        )

        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertEqual(calls, list(range(prefix_size, len(values))))
        self.assertEqual(cached_keys, [])

    def test_fused_prefix_entry_preserves_late_fallback_values(self):
        values = [Record(position, position) for position in range(128)]
        values[65].key = -(1 << 63)
        values[66].key = (1 << 63) - 1
        values[70].key = 1 << 100
        prefix_size = 64
        cached_keys = [value.key for value in values[:prefix_size]]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result = (
            _bielsort._try_sort_by_prefix_cached_int64_keys_prototype(
                values,
                cached_keys,
                key,
            )
        )

        self.assertIsNone(result)
        self.assertEqual(calls, list(range(prefix_size, 71)))
        self.assertEqual(
            cached_keys,
            [value.key for value in values[:71]],
        )

        replay = _bielsort._make_prefix_cached_key_replay_prototype(
            values,
            cached_keys,
            key,
        )
        values.sort(key=replay)
        self.assertEqual(calls, list(range(prefix_size, 128)))
        self.assertEqual(
            [value.key for value in values],
            sorted(value.key for value in values),
        )

    def test_fused_int64_extraction_propagates_key_exception_once(self):
        values = [Record(position, position) for position in range(4_096)]
        calls = []

        def key(record):
            calls.append(record.position)
            if record.position == 100:
                raise RuntimeError("late fused-extraction failure")
            return record.key

        with self.assertRaisesRegex(
            RuntimeError,
            "late fused-extraction failure",
        ):
            sort_by_key_adaptive(values, key)
        self.assertEqual(calls, list(range(101)))
        self.assertEqual(
            [item.position for item in values],
            list(range(len(values))),
        )

    def test_vectorcall_replay_is_one_shot_and_argument_checked(self):
        values = [Record(2, 0), Record(1, 1)]
        replay = _bielsort._make_cached_key_replay_prototype(
            values,
            [2, 1],
        )

        with self.assertRaises(TypeError):
            replay()
        self.assertEqual(replay(values[0]), 2)
        self.assertEqual(replay(values[1]), 1)
        with self.assertRaisesRegex(RuntimeError, "uso único"):
            replay(values[0])

    def test_vectorcall_replay_participates_in_cycle_collection(self):
        finalized = []

        class Sentinel:
            def __del__(self):
                finalized.append(True)

        def create_cycle():
            holder = []
            sentinel = Sentinel()

            def key(record):
                _ = holder, sentinel
                return record.key

            values = [Record(1, 0)]
            replay = _bielsort._make_prefix_cached_key_replay_prototype(
                values,
                [],
                key,
            )
            self.assertTrue(gc.is_tracked(replay))
            holder.append(replay)

        create_cycle()
        gc.collect()
        self.assertEqual(finalized, [True])

    def test_general_iterable_matches_sorted_without_limit(self):
        values = [
            Record(str(key), position)
            for position, key in enumerate([3, 1, 2])
        ]
        result = sort_by_key_adaptive(
            (value for value in values),
            attrgetter("key"),
        )
        expected = sorted(values, key=attrgetter("key"))
        self.assertEqual(result, expected)

    def test_guard_timsort_decides_before_key_and_accepts_generic_keys(self):
        values = [Record(key, position) for position, key in enumerate("bac")]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_key_adaptive(
            values,
            key,
            max_native_auxiliary_bytes=0,
            on_exceeded="timsort",
            return_info=True,
        )

        self.assertEqual([item.key for item in result], ["a", "b", "c"])
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(info["algorithm"], "timsort")
        self.assertIsNone(info["native_eligible"])
        self.assertTrue(info["guard"]["pre_key"])

    def test_guard_raise_calls_no_user_key(self):
        values = [Record(2, 0), Record(1, 1)]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        with self.assertRaises(MemoryError):
            sort_by_key_adaptive(
                values,
                key,
                max_native_auxiliary_bytes=0,
                on_exceeded="raise",
            )
        self.assertEqual(calls, [])
        self.assertEqual([item.position for item in values], [0, 1])

    def test_guard_exact_boundary_enters_native_selector(self):
        values = [
            Record(key, position)
            for position, key in enumerate([3, -1, 7, 0] * 1_024)
        ]
        limit = native_worst_case_variable_auxiliary_bytes(len(values))
        result, info = sort_by_key_adaptive(
            values,
            attrgetter("key"),
            max_native_auxiliary_bytes=limit,
            return_info=True,
        )
        self.assertEqual(result, sorted(values, key=attrgetter("key")))
        self.assertTrue(info["native_eligible"])
        self.assertEqual(info["guard"]["decision"], "native")

    def test_small_uses_timsort_and_ordered_int64_uses_native_result(self):
        small = [Record(2, 0), Record(1, 1)]
        result, info = sort_by_key_adaptive(
            small,
            attrgetter("key"),
            return_info=True,
        )
        self.assertEqual([item.key for item in result], [1, 2])
        self.assertEqual(info["algorithm"], "timsort")
        self.assertEqual(info["guard"]["decision"], "small-input-timsort")

        monotonic = [Record(position, position) for position in range(4_096)]
        result, info = sort_by_key_adaptive(
            monotonic,
            attrgetter("key"),
            return_info=True,
        )
        self.assertEqual(result, monotonic)
        self.assertEqual(info["algorithm"], "already-sorted")
        self.assertTrue(info["native_eligible"])

    def test_key_exception_propagates_without_mutating_input(self):
        values = [Record(2, 0), Record(1, 1), Record(3, 2)]
        calls = []

        def key(record):
            calls.append(record.position)
            if record.position == 1:
                raise RuntimeError("intentional key failure")
            return record.key

        with self.assertRaisesRegex(RuntimeError, "intentional key failure"):
            sort_by_key_adaptive(values, key)
        self.assertEqual(calls, [0, 1])
        self.assertEqual([item.position for item in values], [0, 1, 2])

    def test_randomized_differential_for_int_string_and_huge_keys(self):
        rng = random.Random(20260804)
        key_factories = (
            lambda value: value,
            lambda value: f"{value:+05d}",
            lambda value: value * (1 << 80),
        )
        for key_factory in key_factories:
            for size in (0, 1, 2, 17, 257):
                with self.subTest(factory=key_factory, size=size):
                    values = [
                        Record(key_factory(rng.randint(-20, 20)), position)
                        for position in range(size)
                    ]
                    expected = sorted(values, key=attrgetter("key"))
                    result = sort_by_key_adaptive(
                        values,
                        attrgetter("key"),
                    )
                    self.assertEqual(result, expected)

    def test_randomized_differential_exercises_native_selector(self):
        rng = random.Random(2026080402)
        for size in (2_048, 8_192):
            with self.subTest(size=size):
                values = [
                    Record(rng.randint(-10_000, 10_000), position)
                    for position in range(size)
                ]
                expected = sorted(values, key=attrgetter("key"))
                result = sort_by_key_adaptive(values, attrgetter("key"))
                self.assertEqual(result, expected)

    def test_cached_native_entry_consumes_only_eligible_cache(self):
        items = [Record(2, 0), Record(1, 1)]
        keys = [2, 1]
        result = _bielsort._try_sort_by_cached_int64_keys_prototype(
            items,
            keys,
        )
        self.assertEqual([item.key for item in result], [1, 2])
        self.assertEqual(keys, [])

        items = [Record("b", 0), Record("a", 1)]
        keys = ["b", "a"]
        result = _bielsort._try_sort_by_cached_int64_keys_prototype(
            items,
            keys,
        )
        self.assertIsNone(result)
        self.assertEqual([item.key for item in items], ["b", "a"])
        self.assertEqual(keys, ["b", "a"])

    def test_prototype_is_not_public(self):
        self.assertFalse(hasattr(bielsort, "sort_by_key_adaptive"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
