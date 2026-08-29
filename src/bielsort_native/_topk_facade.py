"""Private unified stable top-k research façade.

This module deliberately remains outside both public package exports. Its
heuristics and diagnostic type are experimental until the pre-registered
semantic, performance, sanitizer, and portability gates pass.
"""

import heapq
import operator
from dataclasses import dataclass
from typing import Optional

from . import _bielsort
from ._keyed_adaptive import sort_by_key_adaptive
from ._keyed_int64_guard import (
    native_worst_case_variable_auxiliary_bytes,
)


_FULL_SORT_DIVISOR = 8
_SMALL_INPUT_LIMIT = 2_048
_MEMORY_POLICIES = ("heapq", "raise")


@dataclass(frozen=True)
class _TopKInfo:
    """Immutable diagnostics for the private unified selector."""

    algorithm: str
    reason: str
    size: int
    requested_k: int
    selected: int
    largest: bool
    key_domain: str
    estimated_native_auxiliary_bytes: Optional[int]
    worst_case_native_auxiliary_bytes: int
    max_native_auxiliary_bytes: Optional[int]
    native_memory_limit_exceeded: bool

    @property
    def used_native(self):
        return self.algorithm.startswith("native-")

    def as_dict(self):
        """Return JSON-compatible fields for private benchmark reports."""
        return {
            "algorithm": self.algorithm,
            "reason": self.reason,
            "size": self.size,
            "requested_k": self.requested_k,
            "selected": self.selected,
            "largest": self.largest,
            "key_domain": self.key_domain,
            "estimated_native_auxiliary_bytes": (
                self.estimated_native_auxiliary_bytes
            ),
            "worst_case_native_auxiliary_bytes": (
                self.worst_case_native_auxiliary_bytes
            ),
            "max_native_auxiliary_bytes": (
                self.max_native_auxiliary_bytes
            ),
            "native_memory_limit_exceeded": (
                self.native_memory_limit_exceeded
            ),
            "used_native": self.used_native,
        }


def _validate_options(
    k,
    largest,
    max_native_auxiliary_bytes,
    on_memory_limit,
    return_info,
):
    if type(k) is bool:
        raise TypeError("k must be an integer index, not bool")
    try:
        requested_k = operator.index(k)
    except TypeError as error:
        raise TypeError("k must be an integer index") from error
    if requested_k < 0:
        raise ValueError("k must be non-negative")
    if type(largest) is not bool:
        raise TypeError("largest must be a bool")
    if (
        max_native_auxiliary_bytes is not None
        and type(max_native_auxiliary_bytes) is not int
    ):
        raise TypeError(
            "max_native_auxiliary_bytes must be an exact integer or None"
        )
    if (
        max_native_auxiliary_bytes is not None
        and max_native_auxiliary_bytes < 0
    ):
        raise ValueError("max_native_auxiliary_bytes must be non-negative")
    if on_memory_limit not in _MEMORY_POLICIES:
        raise ValueError(
            "on_memory_limit must be either 'heapq' or 'raise'"
        )
    if type(return_info) is not bool:
        raise TypeError("return_info must be a bool")
    return requested_k


def _finish(result, info, return_info):
    if return_info:
        return result, info
    return result


def _trivial_info(requested_k, largest, key, reason, limit):
    return _TopKInfo(
        algorithm="trivial",
        reason=reason,
        size=0,
        requested_k=requested_k,
        selected=0,
        largest=largest,
        key_domain="natural" if key is None else "python",
        estimated_native_auxiliary_bytes=None,
        worst_case_native_auxiliary_bytes=0,
        max_native_auxiliary_bytes=limit,
        native_memory_limit_exceeded=False,
    )


def _heapq_topk(values, selected, key, largest):
    selection = heapq.nlargest if largest else heapq.nsmallest
    return selection(selected, values, key=key)


def _full_timsort(values, selected, key, largest):
    result = sorted(values, key=key, reverse=largest)
    del result[selected:]
    return result


def _is_full_sort(selected, size):
    threshold = size // _FULL_SORT_DIVISOR
    if size % _FULL_SORT_DIVISOR:
        threshold += 1
    return selected >= threshold


def _natural_partial_memory(selected, size):
    index_bytes = 4 if size <= (1 << 32) - 1 else 8
    entry_bytes = 16
    return selected * (entry_bytes + index_bytes)


def _natural_full_algorithm(values, largest):
    """Mirror the private argsort selector for truthful untimed diagnostics."""
    size = len(values)
    if size < 2:
        return "trivial"
    if size < _SMALL_INPUT_LIMIT:
        return "timsort"
    iterator = iter(values)
    first = next(iterator)
    previous = -first if largest else first
    descents = 0
    ascents = 0
    for value in iterator:
        current = -value if largest else value
        if current < previous:
            descents += 1
        elif current > previous:
            ascents += 1
        previous = current
    if descents == 0:
        return "native-int64"
    if descents <= size // 128 or ascents <= size // 128:
        return "timsort"
    return "native-int64"


def _route_worst_case(size, selected, full_sort):
    if full_sort:
        return native_worst_case_variable_auxiliary_bytes(size)
    return _bielsort._topk_by_key_worst_auxiliary_bytes(selected)


def _memory_error(worst_case, limit):
    raise MemoryError(
        "BielSort top-k native auxiliary estimate "
        f"({worst_case} bytes) exceeds the configured limit "
        f"({limit} bytes)"
    )


def _info(
    *,
    algorithm,
    reason,
    size,
    requested_k,
    selected,
    largest,
    key_domain,
    estimated,
    worst_case,
    limit,
    exceeded=False,
):
    return _TopKInfo(
        algorithm=algorithm,
        reason=reason,
        size=size,
        requested_k=requested_k,
        selected=selected,
        largest=largest,
        key_domain=key_domain,
        estimated_native_auxiliary_bytes=estimated,
        worst_case_native_auxiliary_bytes=worst_case,
        max_native_auxiliary_bytes=limit,
        native_memory_limit_exceeded=exceeded,
    )


def _guard_fallback(
    values,
    requested_k,
    selected,
    key,
    largest,
    size,
    worst_case,
    limit,
    return_info,
):
    result = _heapq_topk(values, selected, key, largest)
    info = _info(
        algorithm="heapq",
        reason="native memory limit exceeded before key evaluation",
        size=size,
        requested_k=requested_k,
        selected=selected,
        largest=largest,
        key_domain="natural" if key is None else "python",
        estimated=None,
        worst_case=worst_case,
        limit=limit,
        exceeded=True,
    )
    return _finish(result, info, return_info)


def _natural_topk(
    values,
    requested_k,
    selected,
    largest,
    size,
    full_sort,
    small_input,
    max_native_auxiliary_bytes,
    on_memory_limit,
    return_info,
):
    if small_input:
        result = _heapq_topk(values, selected, None, largest)
        info = _info(
            algorithm="heapq",
            reason="input is below the native specialization threshold",
            size=size,
            requested_k=requested_k,
            selected=selected,
            largest=largest,
            key_domain="natural",
            estimated=None,
            worst_case=0,
            limit=max_native_auxiliary_bytes,
        )
        return _finish(result, info, return_info)

    exact_int64 = _bielsort._is_exact_int64_sequence_prototype(values)
    if not exact_int64:
        if full_sort:
            result = _full_timsort(values, selected, None, largest)
            algorithm = "timsort"
            reason = "large k favors CPython's stable full sort"
        else:
            result = _heapq_topk(values, selected, None, largest)
            algorithm = "heapq"
            reason = "natural values are outside the signed-int64 fast path"
        info = _info(
            algorithm=algorithm,
            reason=reason,
            size=size,
            requested_k=requested_k,
            selected=selected,
            largest=largest,
            key_domain="natural",
            estimated=None,
            worst_case=0,
            limit=max_native_auxiliary_bytes,
        )
        return _finish(result, info, return_info)

    worst_case = _route_worst_case(size, selected, full_sort)
    if (
        max_native_auxiliary_bytes is not None
        and worst_case > max_native_auxiliary_bytes
    ):
        if on_memory_limit == "raise":
            _memory_error(worst_case, max_native_auxiliary_bytes)
        return _guard_fallback(
            values,
            requested_k,
            selected,
            None,
            largest,
            size,
            worst_case,
            max_native_auxiliary_bytes,
            return_info,
        )

    order = _bielsort._topk_int64_prototype(values, selected, largest)
    result = order.apply(values)
    algorithm = (
        _natural_full_algorithm(values, largest)
        if full_sort and return_info
        else "native-int64"
    )
    estimated = (
        worst_case
        if full_sort and algorithm == "native-int64"
        else _natural_partial_memory(selected, size)
    )
    if algorithm in ("timsort", "trivial"):
        estimated = None
    info = _info(
        algorithm=algorithm,
        reason=(
            "large k uses CPython Timsort through the adaptive argsort route"
            if algorithm == "timsort"
            else (
                "the one-item selection is already complete"
                if algorithm == "trivial"
                else (
                    "large k uses the compact native full-argsort route"
                    if full_sort
                    else "exact signed-int64 values use compact native selection"
                )
            )
        ),
        size=size,
        requested_k=requested_k,
        selected=selected,
        largest=largest,
        key_domain="signed-int64",
        estimated=estimated,
        worst_case=worst_case,
        limit=max_native_auxiliary_bytes,
    )
    return _finish(result, info, return_info)


def _normalize_full_keyed_info(
    native_info,
    requested_k,
    selected,
    size,
    largest,
    worst_case,
    limit,
):
    native_algorithm = native_info["algorithm"]
    used_timsort = native_algorithm.startswith("timsort")
    algorithm = "timsort" if used_timsort else "native-int64"
    return _info(
        algorithm=algorithm,
        reason=(
            "large k uses cached-key CPython Timsort"
            if used_timsort
            else "large k uses adaptive native signed-int64 sorting"
        ),
        size=size,
        requested_k=requested_k,
        selected=selected,
        largest=largest,
        key_domain="python" if used_timsort else "signed-int64",
        estimated=(
            None
            if used_timsort
            else native_info["estimated_variable_auxiliary_bytes"]
        ),
        worst_case=worst_case,
        limit=limit,
    )


def _explicit_key_topk(
    values,
    requested_k,
    selected,
    key,
    largest,
    size,
    full_sort,
    small_input,
    max_native_auxiliary_bytes,
    on_memory_limit,
    return_info,
):
    if small_input:
        result = _heapq_topk(values, selected, key, largest)
        info = _info(
            algorithm="heapq",
            reason="input is below the native specialization threshold",
            size=size,
            requested_k=requested_k,
            selected=selected,
            largest=largest,
            key_domain="python",
            estimated=None,
            worst_case=0,
            limit=max_native_auxiliary_bytes,
        )
        return _finish(result, info, return_info)

    worst_case = _route_worst_case(size, selected, full_sort)
    if (
        max_native_auxiliary_bytes is not None
        and worst_case > max_native_auxiliary_bytes
    ):
        if on_memory_limit == "raise":
            _memory_error(worst_case, max_native_auxiliary_bytes)
        return _guard_fallback(
            values,
            requested_k,
            selected,
            key,
            largest,
            size,
            worst_case,
            max_native_auxiliary_bytes,
            return_info,
        )

    if full_sort:
        if return_info:
            result, native_info = sort_by_key_adaptive(
                values,
                key,
                reverse=largest,
                return_info=True,
            )
            del result[selected:]
            info = _normalize_full_keyed_info(
                native_info,
                requested_k,
                selected,
                size,
                largest,
                worst_case,
                max_native_auxiliary_bytes,
            )
            return result, info
        result = sort_by_key_adaptive(values, key, reverse=largest)
        del result[selected:]
        return result

    if return_info:
        result, native_info = (
            _bielsort._topk_by_key_prototype_with_info(
                values,
                selected,
                key,
                largest,
            )
        )
        info = _info(
            algorithm=native_info["algorithm"],
            reason=native_info["reason"],
            size=size,
            requested_k=requested_k,
            selected=selected,
            largest=largest,
            key_domain=native_info["key_domain"],
            estimated=native_info["estimated_native_auxiliary_bytes"],
            worst_case=worst_case,
            limit=max_native_auxiliary_bytes,
        )
        return result, info
    return _bielsort._topk_by_key_prototype(
        values,
        selected,
        key,
        largest,
    )


def top_k_adaptive(
    values,
    k,
    *,
    key=None,
    largest=False,
    max_native_auxiliary_bytes=None,
    on_memory_limit="heapq",
    return_info=False,
):
    """Return a private adaptive stable top-k result.

    This research façade accepts any iterable when no native-memory limit is
    configured. A limit requires an exact built-in list or tuple so the route
    and conservative bound are known before evaluating an explicit key.
    """
    requested_k = _validate_options(
        k,
        largest,
        max_native_auxiliary_bytes,
        on_memory_limit,
        return_info,
    )
    if requested_k == 0:
        return _finish(
            [],
            _trivial_info(
                requested_k,
                largest,
                key,
                "k is zero; the iterable and key were not evaluated",
                max_native_auxiliary_bytes,
            ),
            return_info,
        )
    if key is not None and not callable(key):
        raise TypeError("key must be callable or None")
    if (
        max_native_auxiliary_bytes is not None
        and type(values) not in (list, tuple)
    ):
        raise TypeError(
            "max_native_auxiliary_bytes requires an exact list or tuple"
        )

    reusable_values = (
        values if type(values) in (list, tuple) else list(values)
    )
    size = len(reusable_values)
    selected = min(requested_k, size)
    if selected == 0:
        return _finish(
            [],
            _TopKInfo(
                algorithm="trivial",
                reason="the input is empty",
                size=size,
                requested_k=requested_k,
                selected=0,
                largest=largest,
                key_domain="natural" if key is None else "python",
                estimated_native_auxiliary_bytes=None,
                worst_case_native_auxiliary_bytes=0,
                max_native_auxiliary_bytes=max_native_auxiliary_bytes,
                native_memory_limit_exceeded=False,
            ),
            return_info,
        )

    full_sort = _is_full_sort(selected, size)
    small_input = size < _SMALL_INPUT_LIMIT and not full_sort
    if key is None:
        return _natural_topk(
            reusable_values,
            requested_k,
            selected,
            largest,
            size,
            full_sort,
            small_input,
            max_native_auxiliary_bytes,
            on_memory_limit,
            return_info,
        )
    return _explicit_key_topk(
        reusable_values,
        requested_k,
        selected,
        key,
        largest,
        size,
        full_sort,
        small_input,
        max_native_auxiliary_bytes,
        on_memory_limit,
        return_info,
    )


__all__ = []
