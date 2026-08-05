"""Adaptive stable sorting with native integer fast paths.

The native core accelerates compatible signed 64-bit integer workloads and
selects CPython's Timsort when it is more suitable.
"""

from dataclasses import dataclass
from typing import Optional

try:
    from ._bielsort import sort as _sort
    from ._bielsort import sort_in_place as _sort_in_place
    from ._bielsort import _sort_in_place_reverse
    from ._bielsort import _sort_in_place_reverse_with_strategy
    from ._bielsort import _sort_reverse
    from ._bielsort import _sort_reverse_with_strategy
    from ._bielsort import (
        sort_in_place_with_strategy as _sort_in_place_with_strategy,
    )
    from ._bielsort import sort_with_strategy as _sort_with_strategy
    from ._keyed_adaptive import (
        sort_by_key_adaptive as _sort_by_key_adaptive,
    )
except ImportError as erro:
    raise ImportError(
        "A extensão nativa do BielSort não está disponível para este "
        "interpretador. Instale o projeto com `python -m pip install .` "
        "ou, durante o desenvolvimento, `python -m pip install -e .`."
    ) from erro


@dataclass(frozen=True)
class SortInfo:
    """Structured diagnostics for one keyed sorting operation.

    Memory values cover BielSort's variable native buffers, not total process
    RSS or the memory owned by input objects and key results.
    """

    algorithm: str
    reason: str
    size: int
    reverse: bool
    key_domain: str
    key_min: Optional[int]
    key_max: Optional[int]
    key_span: Optional[int]
    radix_passes: Optional[int]
    estimated_native_auxiliary_bytes: Optional[int]
    worst_case_native_auxiliary_bytes: int
    max_native_auxiliary_bytes: Optional[int]
    native_memory_limit_exceeded: bool

    @property
    def used_native(self) -> bool:
        """Whether the operation committed to a native BielSort path."""
        return self.algorithm != "timsort"


def _keyed_strategy(info):
    algorithm = info["algorithm"]
    if algorithm == "counting":
        return "counting nativo estável por key"
    if algorithm == "radix":
        passes = info["radix_passes"]
        suffix = "passagem" if passes == 1 else "passagens"
        return f"radix nativo estável por key: {passes} {suffix}"
    if algorithm == "already-sorted":
        return "key int64: entrada já ordenada"
    if algorithm == "trivial":
        return "key int64: entrada trivial"
    if algorithm == "timsort-sparse-run-replay":
        return "timsort: runs quase monotônicas por key"
    return "timsort: fallback compatível por key"


def _public_keyed_algorithm(info):
    algorithm = info["algorithm"]
    if algorithm.startswith("timsort"):
        return "timsort"
    return algorithm


def _public_keyed_reason(info):
    algorithm = info["algorithm"]
    guard = info["guard"]
    if (
        guard["max_native_auxiliary_bytes"] is not None
        and guard["decision"] == "timsort"
    ):
        return "native memory limit exceeded; used Timsort"
    if algorithm == "counting":
        return "exact signed-int64 keys have a dense range"
    if algorithm == "radix":
        return "exact signed-int64 keys favor stable Radix sorting"
    if algorithm == "already-sorted":
        return "signed-int64 keys are already ordered"
    if algorithm == "trivial":
        return "the input has at most one record"
    if algorithm == "timsort-sparse-run-replay":
        return "sampled keys form sparse nearly monotonic runs"
    if algorithm == "timsort-progressive-key-replay":
        return "a key result is not an exact signed-int64 integer"
    return "the input is better handled by CPython Timsort"


def _public_sort_info(info):
    algorithm = _public_keyed_algorithm(info)
    guard = info["guard"]
    memory_limit = guard["max_native_auxiliary_bytes"]
    memory_limit_exceeded = (
        memory_limit is not None
        and guard["decision"] == "timsort"
    )
    return SortInfo(
        algorithm=algorithm,
        reason=_public_keyed_reason(info),
        size=info["n"],
        reverse=info["reverse"],
        key_domain=(
            "signed-int64" if algorithm != "timsort" else "python"
        ),
        key_min=info["key_min"],
        key_max=info["key_max"],
        key_span=info["key_span"],
        radix_passes=info["radix_passes"],
        estimated_native_auxiliary_bytes=(
            info["estimated_variable_auxiliary_bytes"]
        ),
        worst_case_native_auxiliary_bytes=(
            info["worst_case_variable_auxiliary_bytes"]
        ),
        max_native_auxiliary_bytes=memory_limit,
        native_memory_limit_exceeded=memory_limit_exceeded,
    )


def sort(iterable, *, key=None, reverse=False):
    """Return a new sorted list.

    Native integer paths apply to eligible natural-order and exact
    signed-int64 ``key`` workloads. Other cases retain Timsort semantics.
    """
    if key is not None:
        return _sort_by_key_adaptive(
            iterable,
            key,
            reverse=bool(reverse),
        )
    if reverse:
        return _sort_reverse(iterable)
    return _sort(iterable)


def sort_with_strategy(iterable, *, key=None, reverse=False):
    """Return ``(sorted_list, selected_strategy)`` for diagnostics."""
    if key is not None:
        result, info = _sort_by_key_adaptive(
            iterable,
            key,
            reverse=bool(reverse),
            return_info=True,
        )
        return result, _keyed_strategy(info)
    if reverse:
        return _sort_reverse_with_strategy(iterable)
    return _sort_with_strategy(iterable)


def sort_with_info(
    iterable,
    *,
    key,
    reverse=False,
    max_native_auxiliary_bytes=None,
    on_memory_limit="timsort",
):
    """Return ``(sorted_list, SortInfo)`` for an explicit keyed operation.

    When a native memory limit is provided, ``iterable`` must be an exact
    ``list`` or ``tuple``. The preflight decision is made before ``key`` is
    called. ``on_memory_limit`` accepts ``"timsort"`` or ``"raise"``.
    """
    if on_memory_limit not in ("timsort", "raise"):
        raise ValueError(
            "on_memory_limit must be either 'timsort' or 'raise'"
        )
    result, info = _sort_by_key_adaptive(
        iterable,
        key,
        reverse=bool(reverse),
        max_native_auxiliary_bytes=max_native_auxiliary_bytes,
        on_exceeded=on_memory_limit,
        return_info=True,
    )
    return result, _public_sort_info(info)


def sort_in_place(values, *, key=None, reverse=False):
    """Sort an exact list in place and return ``None``, like ``list.sort()``."""
    if key is not None:
        return values.sort(key=key, reverse=reverse)
    if reverse:
        return _sort_in_place_reverse(values)
    return _sort_in_place(values)


def sort_in_place_with_strategy(values, *, key=None, reverse=False):
    """Sort in place and return the selected strategy for diagnostics."""
    if key is not None:
        values.sort(key=key, reverse=reverse)
        return "timsort: key ou reverse"
    if reverse:
        return _sort_in_place_reverse_with_strategy(values)
    return _sort_in_place_with_strategy(values)


# Compatibility aliases retained for the 0.1 series.
biel_sort = sort
biel_sort_diagnostico = sort_with_strategy
biel_sort_with_strategy = sort_with_strategy
biel_sort_in_place = sort_in_place
biel_sort_in_place_diagnostico = sort_in_place_with_strategy
biel_sort_in_place_with_strategy = sort_in_place_with_strategy

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
]
__version__ = "0.2.0"
