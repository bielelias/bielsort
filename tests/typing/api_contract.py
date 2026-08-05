from typing import Literal, Optional

from typing_extensions import assert_type

import bielsort
import bielsort_native


numbers = [3, 1, 2]

assert_type(bielsort.sort(numbers), list[int])
assert_type(bielsort.sort_with_strategy(numbers), tuple[list[int], str])

ordered, info = bielsort.sort_with_info(numbers, key=lambda value: value)
assert_type(ordered, list[int])
assert_type(info, bielsort.SortInfo)
assert_type(
    info.algorithm,
    Literal["timsort", "counting", "radix", "already-sorted", "trivial"],
)
assert_type(info.used_native, bool)
assert_type(info.key_min, Optional[int])

assert_type(bielsort.biel_sort(numbers), list[int])
assert_type(bielsort_native.sort(numbers), list[int])

bielsort.sort_in_place(numbers)
assert_type(bielsort.sort_in_place_with_strategy(numbers), str)
