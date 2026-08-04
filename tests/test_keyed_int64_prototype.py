import ctypes
import struct
import unittest
from operator import attrgetter

import bielsort
from bielsort_native._keyed_int64_guard import (
    native_worst_case_variable_auxiliary_bytes,
    sort_by_int64_key_guarded,
)
from bielsort_native import _bielsort


POINTER_BYTES = struct.calcsize("P")
SSIZE_BYTES = ctypes.sizeof(ctypes.c_ssize_t)
RADIX_BYTES_PER_ITEM = 2 * POINTER_BYTES + 2 * 8
KEY_BUFFER_BYTES_PER_ITEM = POINTER_BYTES + 8


def counting_auxiliary_bytes(n, key_span):
    conversion_phase = n * (POINTER_BYTES + 8 + 4)
    sorting_phase = (
        n * (2 * POINTER_BYTES + 4)
        + (key_span + 1) * SSIZE_BYTES
    )
    return max(conversion_phase, sorting_phase)


class Record:
    __slots__ = ("key", "position")

    def __init__(self, key, position):
        self.key = key
        self.position = position


class KeyedInt64PrototypeTests(unittest.TestCase):
    """Correctness contract for the research-only keyed-int64 path."""

    def sort(self, values, key=attrgetter("key")):
        return _bielsort._sort_by_int64_key_prototype(values, key)

    def sort_with_strategy(self, values, key=attrgetter("key")):
        return _bielsort._sort_by_int64_key_prototype_with_strategy(
            values,
            key,
        )

    def sort_with_info(self, values, key=attrgetter("key")):
        return _bielsort._sort_by_int64_key_prototype_with_info(
            values,
            key,
        )

    def test_orders_records_stably_without_mutating_input(self):
        values = [
            Record(3, 0),
            Record(-1, 1),
            Record(3, 2),
            Record(-1, 3),
        ]

        result = self.sort(values)

        self.assertEqual([record.key for record in result], [-1, -1, 3, 3])
        self.assertEqual([record.position for record in result], [1, 3, 0, 2])
        self.assertEqual([record.position for record in values], [0, 1, 2, 3])
        self.assertCountEqual(map(id, result), map(id, values))

    def test_calls_key_exactly_once_per_record_in_input_order(self):
        values = [Record(key, position) for position, key in enumerate([2, 1, 2])]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result = self.sort(values, key)

        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual([record.position for record in result], [1, 0, 2])

    def test_supports_full_signed_int64_range(self):
        minimum = -(1 << 63)
        maximum = (1 << 63) - 1
        values = [
            Record(maximum, 0),
            Record(0, 1),
            Record(minimum, 2),
            Record(-1, 3),
        ]

        result, strategy = self.sort_with_strategy(values)

        self.assertEqual(
            [record.key for record in result],
            [minimum, -1, 0, maximum],
        )
        self.assertIn("radix nativo", strategy)

    def test_counting_path_is_stable_at_selection_threshold(self):
        values = [
            Record((position * 97) % 1_001 - 500, position)
            for position in range(250_000)
        ]

        result, info = self.sort_with_info(values)

        self.assertEqual(info["algorithm"], "counting")
        self.assertIn("counting nativo estável", info["strategy"])
        self.assertEqual(info["n"], 250_000)
        self.assertEqual(info["key_min"], -500)
        self.assertEqual(info["key_max"], 500)
        self.assertEqual(info["key_span"], 1_000)
        self.assertIsNone(info["radix_passes"])
        self.assertTrue(info["normalized"])
        self.assertEqual(info["key_calls"], 250_000)
        self.assertEqual(
            info["estimated_variable_auxiliary_bytes"],
            counting_auxiliary_bytes(250_000, 1_000),
        )
        self.assertEqual(
            info["worst_case_variable_auxiliary_bytes"],
            RADIX_BYTES_PER_ITEM * 250_000,
        )
        expected_positions = {}
        result_positions = {}
        for record in values:
            expected_positions.setdefault(record.key, []).append(
                record.position
            )
        for record in result:
            result_positions.setdefault(record.key, []).append(
                record.position
            )
        self.assertEqual(result_positions, expected_positions)

    def test_structured_radix_diagnostic_contract(self):
        minimum = -(1 << 63)
        maximum = (1 << 63) - 1
        values = [
            Record(maximum, 0),
            Record(0, 1),
            Record(minimum, 2),
            Record(-1, 3),
        ]

        result, info = self.sort_with_info(values)

        self.assertEqual(
            set(info),
            {
                "strategy",
                "algorithm",
                "reason",
                "n",
                "key_domain",
                "key_min",
                "key_max",
                "key_span",
                "radix_passes",
                "normalized",
                "stable",
                "key_calls",
                "estimated_variable_auxiliary_bytes",
                "worst_case_variable_auxiliary_bytes",
                "memory_estimate_scope",
                "prototype",
            },
        )
        self.assertEqual(
            [record.key for record in result],
            sorted([maximum, 0, minimum, -1]),
        )
        self.assertEqual(info["algorithm"], "radix")
        self.assertEqual(info["n"], 4)
        self.assertEqual(info["key_domain"], "signed-int64")
        self.assertEqual(info["key_min"], minimum)
        self.assertEqual(info["key_max"], maximum)
        self.assertEqual(info["key_span"], (1 << 64) - 1)
        self.assertEqual(info["radix_passes"], 6)
        self.assertFalse(info["normalized"])
        self.assertTrue(info["stable"])
        self.assertTrue(info["prototype"])
        self.assertEqual(info["key_calls"], 4)
        self.assertEqual(
            info["estimated_variable_auxiliary_bytes"],
            RADIX_BYTES_PER_ITEM * 4,
        )
        self.assertEqual(
            info["worst_case_variable_auxiliary_bytes"],
            RADIX_BYTES_PER_ITEM * 4,
        )

    def test_structured_diagnostic_for_empty_and_ordered_inputs(self):
        empty_result, empty_info = self.sort_with_info([], lambda value: value)
        self.assertEqual(empty_result, [])
        self.assertEqual(empty_info["algorithm"], "trivial")
        self.assertEqual(empty_info["key_calls"], 0)
        self.assertIsNone(empty_info["key_min"])
        self.assertIsNone(empty_info["key_max"])
        self.assertIsNone(empty_info["key_span"])
        self.assertIsNone(empty_info["radix_passes"])
        self.assertEqual(empty_info["estimated_variable_auxiliary_bytes"], 0)

        ordered = [Record(key, key) for key in range(10)]
        ordered_result, ordered_info = self.sort_with_info(ordered)
        self.assertEqual(ordered_result, ordered)
        self.assertEqual(ordered_info["algorithm"], "already-sorted")
        self.assertEqual(ordered_info["key_calls"], 10)
        self.assertEqual(ordered_info["key_min"], 0)
        self.assertEqual(ordered_info["key_max"], 9)
        self.assertEqual(ordered_info["key_span"], 9)
        self.assertEqual(
            ordered_info["estimated_variable_auxiliary_bytes"],
            KEY_BUFFER_BYTES_PER_ITEM * 10,
        )
        self.assertEqual(
            ordered_info["worst_case_variable_auxiliary_bytes"],
            RADIX_BYTES_PER_ITEM * 10,
        )

    def test_structured_prototype_is_not_in_public_api(self):
        self.assertFalse(hasattr(bielsort, "sort_by_int64_key"))
        self.assertFalse(hasattr(bielsort, "plan"))

    def test_guard_uses_native_path_at_exact_limit(self):
        values = [
            Record(key, position)
            for position, key in enumerate([2, 1, 2])
        ]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        limit = native_worst_case_variable_auxiliary_bytes(len(values))
        result, info = sort_by_int64_key_guarded(
            values,
            key,
            max_native_auxiliary_bytes=limit,
            return_info=True,
        )

        self.assertEqual([record.position for record in result], [1, 0, 2])
        self.assertEqual(calls, [0, 1, 2])
        self.assertNotEqual(info["algorithm"], "timsort")
        self.assertEqual(info["guard"]["decision"], "native")
        self.assertEqual(
            info["guard"]["native_worst_case_variable_auxiliary_bytes"],
            limit,
        )

    def test_guard_delegates_before_key_calls_and_preserves_stability(self):
        values = [
            Record(key, position)
            for position, key in enumerate([2, 1, 2])
        ]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        result, info = sort_by_int64_key_guarded(
            values,
            key,
            max_native_auxiliary_bytes=0,
            on_exceeded="timsort",
            return_info=True,
        )

        self.assertEqual([record.position for record in result], [1, 0, 2])
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(info["algorithm"], "timsort")
        self.assertEqual(info["key_calls"], len(values))
        self.assertEqual(info["guard"]["decision"], "timsort")
        self.assertIn("excludes Timsort", info["memory_estimate_scope"])

    def test_guard_raise_policy_runs_before_key(self):
        values = [Record(2, 0), Record(1, 1)]
        calls = []

        def key(record):
            calls.append(record.position)
            return record.key

        with self.assertRaisesRegex(MemoryError, "exceeds the configured limit"):
            sort_by_int64_key_guarded(
                values,
                key,
                max_native_auxiliary_bytes=0,
                on_exceeded="raise",
            )
        self.assertEqual(calls, [])
        self.assertEqual([record.position for record in values], [0, 1])

    def test_guard_rejects_unsized_input_and_invalid_options(self):
        values = (Record(key, key) for key in range(3))
        with self.assertRaisesRegex(TypeError, "exact list or tuple"):
            sort_by_int64_key_guarded(values, attrgetter("key"))

        class ListSubclass(list):
            pass

        with self.assertRaisesRegex(TypeError, "exact list or tuple"):
            sort_by_int64_key_guarded(
                ListSubclass([Record(1, 0)]),
                attrgetter("key"),
            )

        valid_values = [Record(1, 0)]
        invalid_cases = [
            ({"max_native_auxiliary_bytes": True}, TypeError),
            ({"max_native_auxiliary_bytes": -1}, ValueError),
            ({"on_exceeded": "unknown"}, ValueError),
            ({"return_info": 1}, TypeError),
        ]
        for options, error in invalid_cases:
            with self.subTest(options=options):
                with self.assertRaises(error):
                    sort_by_int64_key_guarded(
                        valid_values,
                        attrgetter("key"),
                        **options,
                    )

    def test_accepts_general_iterables(self):
        values = (Record(key, position) for position, key in enumerate([3, 1, 2]))
        result = self.sort(values)
        self.assertEqual([record.key for record in result], [1, 2, 3])

    def test_empty_and_single_item_still_obey_key_contract(self):
        calls = []
        self.assertEqual(self.sort([], lambda record: calls.append(record)), [])
        self.assertEqual(calls, [])

        value = Record(7, 0)

        def key(record):
            calls.append(record.position)
            return record.key

        self.assertEqual(self.sort([value], key), [value])
        self.assertEqual(calls, [0])

    def test_rejects_non_exact_integer_keys(self):
        class IntegerSubclass(int):
            pass

        cases = [
            (True, TypeError),
            (IntegerSubclass(1), TypeError),
            (1.0, TypeError),
            (-(1 << 63) - 1, OverflowError),
            (1 << 63, OverflowError),
        ]
        for key_value, error in cases:
            with self.subTest(key_value=key_value):
                with self.assertRaises(error):
                    self.sort([Record(key_value, 0)])

    def test_rejects_non_callable_key(self):
        with self.assertRaises(TypeError):
            self.sort([Record(1, 0)], None)

    def test_propagates_key_exception_and_keeps_input_unchanged(self):
        values = [Record(2, 0), Record(1, 1)]

        def broken_key(record):
            if record.position == 1:
                raise RuntimeError("intentional failure")
            return record.key

        with self.assertRaisesRegex(RuntimeError, "intentional failure"):
            self.sort(values, broken_key)
        self.assertEqual([record.position for record in values], [0, 1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
