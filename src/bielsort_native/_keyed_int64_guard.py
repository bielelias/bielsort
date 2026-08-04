"""Private memory guard for the experimental keyed-int64 implementation.

This module is installed so internal selectors and wheel-level tests do not
depend on the repository-only ``benchmarks`` package.  Its leading underscore
is intentional: no compatibility commitment is made before BielSort 0.2.
"""

import struct

from . import _bielsort


_POINTER_BYTES = struct.calcsize("P")
_RADIX_BYTES_PER_ITEM = 2 * _POINTER_BYTES + 2 * 8
_EXCEEDED_POLICIES = ("timsort", "raise")


def native_worst_case_variable_auxiliary_bytes(size):
    """Return the compact-Radix planning estimate for ``size`` records."""
    if type(size) is not int:
        raise TypeError("size must be an exact integer")
    if size < 0:
        raise ValueError("size must be non-negative")
    return size * _RADIX_BYTES_PER_ITEM


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


def _read_size(values):
    if type(values) not in (list, tuple):
        raise TypeError(
            "the guarded prototype requires an exact list or tuple"
        )
    return len(values)


def _guard_details(limit, worst_case, decision, on_exceeded):
    return {
        "max_native_auxiliary_bytes": limit,
        "native_worst_case_variable_auxiliary_bytes": worst_case,
        "decision": decision,
        "on_exceeded": on_exceeded,
        "sized_input": True,
    }


def _timsort_info(size, worst_case, limit, on_exceeded, reverse):
    return {
        "strategy": "timsort: native auxiliary limit exceeded",
        "algorithm": "timsort",
        "reason": (
            "the compact-Radix worst-case estimate exceeds "
            "max_native_auxiliary_bytes"
        ),
        "n": size,
        "key_domain": "delegated-to-timsort; not inspected by guard",
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
        "memory_estimate_scope": (
            "native BielSort candidate only; excludes Timsort allocations"
        ),
        "prototype": True,
        "guard": _guard_details(
            limit,
            worst_case,
            "timsort",
            on_exceeded,
        ),
    }


def sort_by_int64_key_guarded(
    values,
    key,
    *,
    reverse=False,
    max_native_auxiliary_bytes=None,
    on_exceeded="timsort",
    return_info=False,
):
    """Sort an exact list or tuple through the experimental guarded path.

    The limit covers BielSort's result-list pointers and variable native
    buffers, not total process RSS.  Restricting this first prototype to exact
    built-in containers makes ``len(values)`` a trustworthy preflight value
    and avoids hidden iterable-materialization allocations.  The decision is
    made before the callable ``key`` is evaluated.

    ``reverse=True`` uses the same stable descending semantics as
    ``sorted(..., reverse=True)`` on both native and Timsort paths.

    This is a research contract.  In particular, the ``timsort`` policy
    delegates key-domain validation to Python when the limit is exceeded,
    while the native path requires exact signed 64-bit integer keys.
    """
    _validate_options(
        key,
        reverse,
        max_native_auxiliary_bytes,
        on_exceeded,
        return_info,
    )
    size = _read_size(values)
    worst_case = native_worst_case_variable_auxiliary_bytes(size)
    exceeded = (
        max_native_auxiliary_bytes is not None
        and worst_case > max_native_auxiliary_bytes
    )

    if exceeded:
        if on_exceeded == "raise":
            raise MemoryError(
                "BielSort native auxiliary estimate "
                f"({worst_case} bytes) exceeds the configured limit "
                f"({max_native_auxiliary_bytes} bytes)"
            )
        result = sorted(values, key=key, reverse=reverse)
        if not return_info:
            return result
        return result, _timsort_info(
            size,
            worst_case,
            max_native_auxiliary_bytes,
            on_exceeded,
            reverse,
        )

    if not return_info:
        return _bielsort._sort_by_int64_key_prototype(
            values,
            key,
            reverse,
        )

    result, info = _bielsort._sort_by_int64_key_prototype_with_info(
        values,
        key,
        reverse,
    )
    info["guard"] = _guard_details(
        max_native_auxiliary_bytes,
        worst_case,
        "native",
        on_exceeded,
    )
    return result, info
