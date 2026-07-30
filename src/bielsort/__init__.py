"""Canonical public API for BielSort.

The implementation remains in ``bielsort_native`` so existing users keep a
compatible import path. New code should import this package.
"""

from bielsort_native import (
    __version__,
    biel_sort,
    biel_sort_diagnostico,
    biel_sort_in_place,
    biel_sort_in_place_diagnostico,
    biel_sort_in_place_with_strategy,
    biel_sort_with_strategy,
    sort,
)

__all__ = [
    "biel_sort",
    "biel_sort_diagnostico",
    "biel_sort_with_strategy",
    "biel_sort_in_place",
    "biel_sort_in_place_diagnostico",
    "biel_sort_in_place_with_strategy",
    "sort",
    "__version__",
]
