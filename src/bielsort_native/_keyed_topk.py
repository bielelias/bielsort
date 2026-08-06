"""Private adaptive stable keyed top-k research dispatcher.

The native core keeps only the current ``k`` key objects. Exact signed-int64
keys use normalized integer comparisons; other comparable keys switch the
same heap to Python ``<`` comparisons without evaluating a key twice.
"""

import heapq

from . import _bielsort


_EXCEEDED_POLICIES = ("heapq", "raise")


def _validate_options(
    k,
    largest,
    max_native_auxiliary_bytes,
    on_exceeded,
    return_strategy,
):
    if type(k) is not int:
        raise TypeError("k must be an exact integer")
    if k < 0:
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
    if on_exceeded not in _EXCEEDED_POLICIES:
        raise ValueError("on_exceeded must be either 'heapq' or 'raise'")
    if type(return_strategy) is not bool:
        raise TypeError("return_strategy must be a bool")


def _finish(result, strategy, return_strategy):
    if return_strategy:
        return result, strategy
    return result


def _heapq_topk(values, k, key, largest):
    function = heapq.nlargest if largest else heapq.nsmallest
    return function(k, values, key=key)


def topk_by_key_adaptive(
    values,
    k,
    key,
    *,
    largest=False,
    max_native_auxiliary_bytes=None,
    on_exceeded="heapq",
    return_strategy=False,
):
    """Return a private stable top-k result for comparable Python keys.

    A configured memory limit requires an exact list or tuple. The worst-case
    native-buffer decision then happens before ``key`` is called. This helper
    remains private and intentionally makes no compatibility commitment.
    """
    _validate_options(
        k,
        largest,
        max_native_auxiliary_bytes,
        on_exceeded,
        return_strategy,
    )
    if k == 0:
        return _finish(
            [],
            "empty selection without key evaluation",
            return_strategy,
        )
    if not callable(key):
        raise TypeError("key must be callable")

    if max_native_auxiliary_bytes is not None:
        if type(values) not in (list, tuple):
            raise TypeError(
                "max_native_auxiliary_bytes requires an exact list or tuple"
            )
        effective_k = min(k, len(values))
        worst_case = _bielsort._topk_by_key_worst_auxiliary_bytes(
            effective_k
        )
        if worst_case > max_native_auxiliary_bytes:
            if on_exceeded == "raise":
                raise MemoryError(
                    "BielSort top-k native auxiliary estimate "
                    f"({worst_case} bytes) exceeds the configured limit "
                    f"({max_native_auxiliary_bytes} bytes)"
                )
            result = _heapq_topk(values, k, key, largest)
            return _finish(
                result,
                "heapq: native auxiliary limit exceeded before key",
                return_strategy,
            )

    if return_strategy:
        return _bielsort._topk_by_key_prototype_with_strategy(
            values,
            k,
            key,
            largest,
        )
    return _bielsort._topk_by_key_prototype(
        values,
        k,
        key,
        largest,
    )
