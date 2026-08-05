# Research proposal: compact stable `argsort`

!!! warning "Design only"

    BielSort does not currently expose `argsort`. This page defines an
    experimental contract and measurement gates; it is not released API.

## Problem

Sorting objects produces one reordered collection. Some pipelines instead
need a reusable permutation so the same ordering can be applied to several
parallel sequences without changing the originals.

```python
order = bielsort.argsort(scores)

ordered_scores = [scores[index] for index in order]
ordered_names = [names[index] for index in order]
```

Potential applications include event batches, rankings, simulation results,
parallel Python columns, and telemetry records. The target niche is data that
already exists as Python sequences; an existing contiguous NumPy array should
continue to use NumPy's own sorting operations.

## Candidate contract

```python
from typing import Callable, Optional, Sequence, TypeVar

T = TypeVar("T")


def argsort(
    values: Sequence[T],
    *,
    key: Optional[Callable[[T], object]] = None,
    reverse: bool = False,
) -> "Permutation": ...
```

The proposed invariants are:

- return the original zero-based indices in sorted order;
- preserve encounter order for equal values or keys, including
  `reverse=True`;
- evaluate an explicit key exactly once per value, in input order;
- never mutate the input sequence;
- use native Counting or Radix only for eligible exact signed-int64 values or
  keys, with a Python-compatible fallback otherwise;
- return an immutable sequence that supports indexing, iteration, `len()`,
  and the buffer protocol.

The first prototype should accept a `Sequence`, not an arbitrary one-shot
iterable. Indices returned for a consumed generator would not refer to a
collection the caller can subsequently index.

## Compact result

A regular `list[int]` permutation owns Python integer objects and pointers.
The proposed `Permutation` object would store unsigned native indices:

- 32-bit indices when the input length permits;
- 64-bit indices only when required;
- an immutable Python sequence interface;
- a read-only buffer so optional consumers such as NumPy can interoperate
  without making NumPy a BielSort runtime dependency.

The exact buffer format and serialization behavior must be fixed before the
name becomes public. The first implementation should remain private as
`_argsort_int64_prototype`.

## Measurement gates

The prototype advances only if all semantic tests pass and at least one of
these performance outcomes is reproduced:

1. at least two disordered 100,000- or 1,000,000-element integer workloads
   reach `1.50x` over
   `sorted(range(len(values)), key=values.__getitem__)`; or
2. the complete operation reduces incremental peak memory by at least 30%
   without slowing down by more than 10%.

The benchmark must also compare against NumPy in two distinct scenarios:

- values already stored in a NumPy array;
- a Python sequence converted to NumPy and the indices converted or consumed
  by the caller.

Negative ordered cases, result-application cost, platform, compiler, raw
samples, and peak memory remain part of the report. Passing these gates would
justify further engineering, not prove external demand.

## Open questions

- Should the first public version support only natural integer values, or ship
  with stable signed-int64 `key=` support at once?
- Should `Permutation` expose a deliberate method for applying itself to a
  Python sequence, or remain a small index container?
- Is a stable generic fallback valuable enough to include, or should the
  prototype reject unsupported domains explicitly?
- Can 32-bit and 64-bit internal storage coexist without making the buffer
  contract surprising?

These questions will be answered by a private implementation and benchmark,
not by committing the public API in advance.
