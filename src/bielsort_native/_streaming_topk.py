"""Private bounded-memory streaming top-k research candidate.

The implementation consumes an arbitrary iterable once and retains only the
current ``k`` records and their keys.  It is deliberately excluded from the
public package while its pre-registered performance and portability gates are
being evaluated.
"""

import heapq
import operator
from dataclasses import dataclass
from typing import Optional

from . import _bielsort


_MEMORY_POLICIES = ("heapq", "raise")


@dataclass(frozen=True)
class _StreamTopKInfo:
    """Immutable diagnostics for the private streaming candidate."""

    algorithm: str
    reason: str
    processed: int
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
        """Return JSON-compatible fields for the research reports."""
        return {
            "algorithm": self.algorithm,
            "reason": self.reason,
            "processed": self.processed,
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


def _info(
    *,
    algorithm,
    reason,
    processed,
    requested_k,
    selected,
    largest,
    key_domain,
    estimated,
    worst_case,
    limit,
    exceeded=False,
):
    return _StreamTopKInfo(
        algorithm=algorithm,
        reason=reason,
        processed=processed,
        requested_k=requested_k,
        selected=selected,
        largest=largest,
        key_domain=key_domain,
        estimated_native_auxiliary_bytes=estimated,
        worst_case_native_auxiliary_bytes=worst_case,
        max_native_auxiliary_bytes=limit,
        native_memory_limit_exceeded=exceeded,
    )


def _memory_error(worst_case, limit):
    raise MemoryError(
        "BielSort streaming top-k native auxiliary estimate "
        f"({worst_case} bytes) exceeds the configured limit "
        f"({limit} bytes)"
    )


def _counted(values, counter):
    for value in values:
        counter[0] += 1
        yield value


def _heapq_fallback(
    values,
    requested_k,
    key,
    largest,
    worst_case,
    limit,
    return_info,
):
    counter = [0]
    selection = heapq.nlargest if largest else heapq.nsmallest
    result = selection(
        requested_k,
        _counted(values, counter),
        key=key,
    )
    info = _info(
        algorithm="heapq",
        reason="native memory limit exceeded before stream consumption",
        processed=counter[0],
        requested_k=requested_k,
        selected=len(result),
        largest=largest,
        key_domain="natural" if key is None else "python",
        estimated=None,
        worst_case=worst_case,
        limit=limit,
        exceeded=True,
    )
    return _finish(result, info, return_info)


def stream_top_k(
    values,
    k,
    *,
    key=None,
    largest=False,
    max_native_auxiliary_bytes=None,
    on_memory_limit="heapq",
    return_info=False,
):
    """Return a private stable top-k result from a one-pass iterable.

    The native-memory decision depends only on ``k`` and therefore occurs
    before obtaining the input iterator or evaluating ``key``.  ``largest``
    changes the direction while retaining encounter order for equal keys.
    """
    requested_k = _validate_options(
        k,
        largest,
        max_native_auxiliary_bytes,
        on_memory_limit,
        return_info,
    )
    if requested_k == 0:
        info = _info(
            algorithm="trivial",
            reason="k is zero; the iterable and key were not evaluated",
            processed=0,
            requested_k=0,
            selected=0,
            largest=largest,
            key_domain="natural" if key is None else "python",
            estimated=None,
            worst_case=0,
            limit=max_native_auxiliary_bytes,
        )
        return _finish([], info, return_info)
    if key is not None and not callable(key):
        raise TypeError("key must be callable or None")

    worst_case = _bielsort._stream_topk_worst_auxiliary_bytes(
        requested_k
    )
    if (
        max_native_auxiliary_bytes is not None
        and worst_case > max_native_auxiliary_bytes
    ):
        if on_memory_limit == "raise":
            _memory_error(worst_case, max_native_auxiliary_bytes)
        return _heapq_fallback(
            values,
            requested_k,
            key,
            largest,
            worst_case,
            max_native_auxiliary_bytes,
            return_info,
        )

    if not return_info:
        return _bielsort._stream_topk_prototype(
            values,
            requested_k,
            key,
            largest,
        )

    result, processed, exact_int64 = (
        _bielsort._stream_topk_prototype_with_info(
            values,
            requested_k,
            key,
            largest,
        )
    )
    selected = len(result)
    if processed == 0:
        algorithm = "trivial"
        reason = "the stream was empty"
        key_domain = "natural" if key is None else "python"
        estimated = worst_case // 2
    elif exact_int64:
        algorithm = "native-stream-int64"
        reason = "exact signed-int64 keys used native comparisons"
        key_domain = "signed-int64"
        estimated = worst_case // 2
    else:
        algorithm = "native-stream-generic"
        reason = "comparable Python keys used the generic native heap"
        key_domain = "generic-python"
        estimated = worst_case
    info = _info(
        algorithm=algorithm,
        reason=reason,
        processed=processed,
        requested_k=requested_k,
        selected=selected,
        largest=largest,
        key_domain=key_domain,
        estimated=estimated,
        worst_case=worst_case,
        limit=max_native_auxiliary_bytes,
    )
    return result, info


__all__ = []
