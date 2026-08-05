# Research: compact stable `argsort`

!!! warning "Private prototype"

    BielSort does not expose `argsort`. A native prototype now tests the
    contract and measurement gates below, but it is not released API.

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
name becomes public. The current implementation remains private as
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

## First prototype result

The 2026-08-05 local experiment passes both alternative research gates:

- the three disordered integer cases reach `3.47x–5.86x` at 100,000 elements
  and `4.51x–8.04x` at one million against Python's stable index baseline;
- at one million, those cases reduce median incremental peak RSS by 45%–47%;
- a one-million-index BielSort result uses a 4,000,000-byte payload, compared
  with NumPy's 8,000,000-byte `intp` payload and a Python list's 8,000,056
  shallow bytes before its integer objects are counted.

The negative results are equally important. Nearly sorted construction is
about 32% slower at one million and uses 14% more incremental peak memory.
Applying the compact indices to a Python list is 16%–32% slower in the tested
one-million-element cases. NumPy also retains a major advantage when values
already live in an ndarray, especially for ordered inputs.

## Native application follow-up

The next private experiment adds `Permutation.apply(sequence)` to avoid
materializing one Python integer per index while applying the compact buffer.
It must return a new list, preserve exact object identity, leave the source
unchanged, reject one-shot iterables, and require the sequence length to match
the permutation.

Before the full-size run, the continuation gates are fixed as follows:

1. Native application must reach at least `1.50x` over a Python list
   comprehension driven by `list[int]` in at least four of the five
   one-million-element cases.
2. Constructing one order and applying it to three parallel lists must reach
   `1.50x` in at least two disordered 100,000- or one-million-element cases.
3. That complete three-list operation must not be more than 10% slower on a
   nearly sorted input at either large size.

Passing this follow-up would show that compact storage and fast reuse can
coexist. It would still not make the type public or approve a release.

## Native application result

The 2026-08-05 continuation passes all three pre-registered gates on the local
Linux machine:

- at one million elements, native application is `2.14x–4.86x` faster than a
  list comprehension driven by a precomputed Python `list[int]`;
- building one order and applying it to three parallel lists is
  `4.93x–6.41x` faster in the three disordered one-million-element cases;
- the same complete operation is `1.21x` and `1.04x` faster for nearly sorted
  inputs at 100,000 and one million elements, respectively;
- incremental peak RSS for the three disordered one-million-element complete
  flows is 51%–56% lower than the Python baseline.

The native method avoids creating Python integer indices during application
and preserves exact object identity. It remains private, and the nearly sorted
construction stage by itself remains slower than Timsort. See the
[native application research record](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-08-05-compact-argsort-native-apply.md)
for tables, raw evidence, limitations, and reproduction commands.

See the
[full research record](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-08-05-compact-argsort.md)
for the separate Python/NumPy scenarios, reproduction commands, raw samples,
and environment. This pass authorizes continued private engineering only; it
does not add an API, change the package version, or establish market demand.

## Open questions

- Should the first public version support only natural integer values, or ship
  with stable signed-int64 `key=` support at once?
- Should a future public `Permutation` expose the validated native application
  method, and what name best communicates that it returns a new list?
- Is a stable generic fallback valuable enough to include, or should the
  prototype reject unsupported domains explicitly?
- Can 32-bit and 64-bit internal storage coexist without making the buffer
  contract surprising?

These questions will be answered by further private implementation and
benchmark work, not by committing the public API in advance.
