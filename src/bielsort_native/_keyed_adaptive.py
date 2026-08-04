"""Private adaptive generic-key selector for BielSort research.

User keys are evaluated exactly once.  The native path progressively extracts
exact signed-int64 values for Counting/Radix sorting.  On the first generic
key, the extracted integer values become a replay prefix and CPython Timsort
evaluates only the remaining keys.

The module remains an internal implementation detail.  The canonical public
wrapper may call it, but its direct names are not exported and carry no
compatibility commitment.
"""

import struct

from . import _bielsort
from ._keyed_int64_guard import (
    native_worst_case_variable_auxiliary_bytes,
)


_EXCEEDED_POLICIES = ("timsort", "raise")
_SMALL_INPUT_LIMIT = 2_048
_NATIVE_EXTRACTION_BYTES_PER_ITEM = 2 * struct.calcsize("P") + 8


def _validate_options(
    key,
    reverse,
    max_native_auxiliary_bytes,
    on_exceeded,
    return_info,
):
    if not callable(key):
        raise TypeError("key must be callable")
    if type(reverse) is not bool:
        raise TypeError("reverse must be a bool")
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
    if on_exceeded not in _EXCEEDED_POLICIES:
        raise ValueError(
            "on_exceeded must be either 'timsort' or 'raise'"
        )
    if type(return_info) is not bool:
        raise TypeError("return_info must be a bool")


def _guard_details(limit, worst_case, decision, on_exceeded):
    return {
        "max_native_auxiliary_bytes": limit,
        "native_worst_case_variable_auxiliary_bytes": worst_case,
        "decision": decision,
        "on_exceeded": on_exceeded,
        "pre_key": decision in (
            "timsort",
            "raise",
            "small-input-timsort",
        ),
    }


def _fallback_info(
    size,
    worst_case,
    limit,
    on_exceeded,
    reverse,
    *,
    fallback_mode,
):
    if fallback_mode == "progressive-generic":
        algorithm = "timsort-progressive-key-replay"
        strategy = (
            "prototype adaptive-key: Timsort with progressive-key replay"
        )
        cache_mode = "progressive-prefix"
        reason = "native extraction encountered a generic Python key"
        decision = "progressive-key-timsort"
        native_eligible = False
        memory_scope = (
            "native int64 estimate only; excludes the progressively cached "
            "prefix and Timsort allocations"
        )
    elif fallback_mode == "adaptive-sparse":
        algorithm = "timsort-sparse-run-replay"
        strategy = (
            "prototype adaptive-key: Timsort for sparse ordered runs"
        )
        cache_mode = "adaptive-prefix"
        reason = (
            "a sparse, nearly monotonic int64 prefix is small or would "
            "require many Radix passes, favoring Timsort"
        )
        decision = "adaptive-sparse-timsort"
        native_eligible = None
        memory_scope = (
            "native int64 estimate only; excludes the adaptive replay prefix "
            "and Timsort allocations"
        )
    else:
        algorithm = "timsort"
        strategy = "prototype adaptive-key: pre-key Timsort"
        cache_mode = None
        native_eligible = None
        if fallback_mode == "pre-key-small":
            reason = "input is below the native specialization threshold"
            decision = "small-input-timsort"
        else:
            reason = "native worst-case estimate exceeds the configured limit"
            decision = "timsort"
        memory_scope = (
            "native candidate estimate only; excludes Timsort allocations"
        )

    return {
        "strategy": strategy,
        "algorithm": algorithm,
        "reason": reason,
        "n": size,
        "key_domain": "generic-python",
        "key_min": None,
        "key_max": None,
        "key_span": None,
        "radix_passes": None,
        "normalized": False,
        "stable": True,
        "reverse": reverse,
        "key_calls": size,
        "estimated_variable_auxiliary_bytes": None,
        "worst_case_variable_auxiliary_bytes": worst_case,
        "memory_estimate_scope": memory_scope,
        "prototype": True,
        "native_eligible": native_eligible,
        "cached_key_fallback": cache_mode is not None,
        "cached_key_mode": cache_mode,
        "guard": _guard_details(
            limit,
            worst_case,
            decision,
            on_exceeded,
        ),
    }


def _decorate_native_info(info, limit, worst_case, on_exceeded):
    info["strategy"] = info["strategy"].replace(
        "protótipo keyed-int64",
        "prototype adaptive-key",
    )
    info["key_domain"] = "generic-python; specialized signed-int64"
    info["native_eligible"] = True
    info["cached_key_fallback"] = False
    info["cached_key_mode"] = None
    extraction_estimate = (
        info["n"] * _NATIVE_EXTRACTION_BYTES_PER_ITEM
    )
    selected_estimate = info["estimated_variable_auxiliary_bytes"]
    if selected_estimate is not None:
        info["estimated_variable_auxiliary_bytes"] = max(
            selected_estimate,
            extraction_estimate,
        )
    info["worst_case_variable_auxiliary_bytes"] = worst_case
    info["memory_estimate_scope"] = (
        "result-list items and native variable buffers; excludes key-object "
        "payloads, allocator overhead, and fixed stack"
    )
    info["guard"] = _guard_details(
        limit,
        worst_case,
        "native",
        on_exceeded,
    )
    return info


def _raise_limit_error(worst_case, limit):
    raise MemoryError(
        "BielSort native auxiliary estimate "
        f"({worst_case} bytes) exceeds the configured limit "
        f"({limit} bytes)"
    )


def _sort_with_prefix_replay(items, cached_keys, key, reverse):
    replay = _bielsort._make_prefix_cached_key_replay_prototype(
        items,
        cached_keys,
        key,
    )
    items.sort(key=replay, reverse=reverse)
    return items


def sort_by_key_adaptive(
    values,
    key,
    *,
    reverse=False,
    max_native_auxiliary_bytes=None,
    on_exceeded="timsort",
    return_info=False,
):
    """Return a stable new list using a cached generic-key selector.

    Without a memory limit, any iterable is accepted.  A configured native
    limit requires an exact built-in list or tuple so the selector can make a
    trustworthy decision before evaluating ``key``.  ``reverse=True`` keeps
    the original encounter order of records whose keys compare equal.
    """
    _validate_options(
        key,
        reverse,
        max_native_auxiliary_bytes,
        on_exceeded,
        return_info,
    )

    if max_native_auxiliary_bytes is not None:
        if type(values) not in (list, tuple):
            raise TypeError(
                "max_native_auxiliary_bytes requires an exact list or tuple"
            )
        size = len(values)
        worst_case = native_worst_case_variable_auxiliary_bytes(size)
        if worst_case > max_native_auxiliary_bytes:
            if on_exceeded == "raise":
                _raise_limit_error(
                    worst_case,
                    max_native_auxiliary_bytes,
                )
            result = sorted(values, key=key, reverse=reverse)
            if not return_info:
                return result
            return result, _fallback_info(
                size,
                worst_case,
                max_native_auxiliary_bytes,
                on_exceeded,
                reverse,
                fallback_mode="pre-key-limit",
            )

    items = list(values)
    size = len(items)
    worst_case = native_worst_case_variable_auxiliary_bytes(size)
    if size < _SMALL_INPUT_LIMIT:
        items.sort(key=key, reverse=reverse)
        if not return_info:
            return items
        return items, _fallback_info(
            size,
            worst_case,
            max_native_auxiliary_bytes,
            on_exceeded,
            reverse,
            fallback_mode="pre-key-small",
        )

    cached_keys = []

    if return_info:
        native_attempt = (
            _bielsort._try_sort_by_prefix_cached_int64_keys_prototype_with_info(
                items,
                cached_keys,
                key,
                reverse,
            )
        )
    else:
        native_attempt = (
            _bielsort._try_sort_by_prefix_cached_int64_keys_prototype(
                items,
                cached_keys,
                key,
                reverse,
            )
        )

    if native_attempt is False:
        result = _sort_with_prefix_replay(
            items,
            cached_keys,
            key,
            reverse,
        )
        if not return_info:
            return result
        return result, _fallback_info(
            size,
            worst_case,
            max_native_auxiliary_bytes,
            on_exceeded,
            reverse,
            fallback_mode="adaptive-sparse",
        )

    if native_attempt is not None:
        if not return_info:
            return native_attempt
        result, info = native_attempt
        return result, _decorate_native_info(
            info,
            max_native_auxiliary_bytes,
            worst_case,
            on_exceeded,
        )

    # The fused native extraction retains the exact key objects only until it
    # commits to the native path. On fallback, Timsort replays that evaluated
    # prefix and calls the user key exactly once for every remaining item.
    result = _sort_with_prefix_replay(
        items,
        cached_keys,
        key,
        reverse,
    )
    if not return_info:
        return result
    return result, _fallback_info(
        size,
        worst_case,
        max_native_auxiliary_bytes,
        on_exceeded,
        reverse,
        fallback_mode="progressive-generic",
    )
