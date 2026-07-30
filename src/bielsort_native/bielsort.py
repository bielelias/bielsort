"""Adaptive stable sorting with native integer fast paths.

The native core accelerates compatible signed 64-bit integer workloads and
selects CPython's Timsort when it is more suitable.
"""

try:
    from ._bielsort import sort as _sort
    from ._bielsort import sort_in_place as _sort_in_place
    from ._bielsort import (
        sort_in_place_with_strategy as _sort_in_place_with_strategy,
    )
    from ._bielsort import sort_with_strategy as _sort_with_strategy
except ImportError as erro:
    raise ImportError(
        "A extensão nativa do BielSort não está disponível para este "
        "interpretador. Instale o projeto com `python -m pip install .` "
        "ou, durante o desenvolvimento, `python -m pip install -e .`."
    ) from erro


def sort(iterable, *, key=None, reverse=False):
    """Return a new sorted list.

    Native integer paths apply to natural ascending order. General ``key`` and
    ``reverse`` operations delegate to ``sorted()`` to preserve its semantics.
    """
    if key is not None or reverse:
        return sorted(iterable, key=key, reverse=reverse)
    return _sort(iterable)


def sort_with_strategy(iterable, *, key=None, reverse=False):
    """Return ``(sorted_list, selected_strategy)`` for diagnostics."""
    if key is not None or reverse:
        return (
            sorted(iterable, key=key, reverse=reverse),
            "timsort: key ou reverse",
        )
    return _sort_with_strategy(iterable)


def sort_in_place(values, *, key=None, reverse=False):
    """Sort an exact list in place and return ``None``, like ``list.sort()``."""
    if key is not None or reverse:
        return values.sort(key=key, reverse=reverse)
    return _sort_in_place(values)


def sort_in_place_with_strategy(values, *, key=None, reverse=False):
    """Sort in place and return the selected strategy for diagnostics."""
    if key is not None or reverse:
        values.sort(key=key, reverse=reverse)
        return "timsort: key ou reverse"
    return _sort_in_place_with_strategy(values)


# Compatibility aliases retained for the 0.1 series.
biel_sort = sort
biel_sort_diagnostico = sort_with_strategy
biel_sort_with_strategy = sort_with_strategy
biel_sort_in_place = sort_in_place
biel_sort_in_place_diagnostico = sort_in_place_with_strategy
biel_sort_in_place_with_strategy = sort_in_place_with_strategy

__all__ = [
    "sort",
    "sort_with_strategy",
    "sort_in_place",
    "sort_in_place_with_strategy",
    "biel_sort",
    "biel_sort_diagnostico",
    "biel_sort_with_strategy",
    "biel_sort_in_place",
    "biel_sort_in_place_diagnostico",
    "biel_sort_in_place_with_strategy",
]
__version__ = "0.1.0rc1"
