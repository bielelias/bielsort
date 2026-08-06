"""Private candidate for the compact reusable reorder-plan contract.

The callable deliberately lives in a private module while the frozen
end-to-end gates are evaluated.  Keeping this thin façade separate from the C
prototype lets tests exercise the proposed keyword-only signature without
adding ``argsort`` or ``Permutation`` to either public package.
"""

from collections import abc as _abc

from . import _bielsort


Permutation = _bielsort._Permutation


def argsort(
    values: _abc.Sequence[object],
    *,
    reverse: bool = False,
) -> _bielsort._Permutation:
    """Return a private compact stable order for a reusable sequence."""
    return _bielsort._argsort_int64_prototype(values, reverse)


__all__ = ["Permutation", "argsort"]
