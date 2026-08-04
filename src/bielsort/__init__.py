"""Canonical public API for BielSort.

The implementation remains in ``bielsort_native`` so existing users keep a
compatible import path. New code should import this package.
"""

from bielsort_native import (
    SortInfo,
    __version__,
    biel_sort,
    biel_sort_diagnostico,
    biel_sort_in_place,
    biel_sort_in_place_diagnostico,
    biel_sort_in_place_with_strategy,
    biel_sort_with_strategy,
    sort,
    sort_in_place,
    sort_in_place_with_strategy,
    sort_with_info,
    sort_with_strategy,
)

__all__ = [
    "SortInfo",
    "sort",
    "sort_with_strategy",
    "sort_with_info",
    "sort_in_place",
    "sort_in_place_with_strategy",
    "biel_sort",
    "biel_sort_diagnostico",
    "biel_sort_with_strategy",
    "biel_sort_in_place",
    "biel_sort_in_place_diagnostico",
    "biel_sort_in_place_with_strategy",
    "__version__",
]
