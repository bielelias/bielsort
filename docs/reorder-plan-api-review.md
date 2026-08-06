# Review: compact reusable reorder plan

!!! warning "Pre-registered discovery protocol — 2026-08-06"

    This document freezes the first API and end-to-end evaluation before a
    public implementation or a new canonical benchmark is produced. BielSort
    does **not** currently export `argsort` or `Permutation`, and this review
    does not authorize a version, merge, release, or performance claim.

## Decision

The first candidate should be deliberately small:

```python
import bielsort

order = bielsort.argsort(timestamps)
ordered_timestamps = order.apply(timestamps)
ordered_events = order.apply(events)
```

The provisional public names are `argsort` and `Permutation`. `argsort` is
already familiar to users of indirect sorting, while the returned type makes
the BielSort-specific value explicit: it is an immutable, compact plan that
can be reused without materializing Python integer indices during each
application.

The candidate accepts a sequence of ordering values directly. It does not
accept `key=` in this stage. A caller that already has records and wants one
sorted result should continue to use `bielsort.sort(records, key=...)`.
Aligned data can pass its existing key column to `argsort()`. This boundary
matches the private implementation that has been measured and avoids
promising an untested second API shape.

## Product promise

> Compute one stable order from a large Python sequence and reuse it across
> equally sized Python sequences, with compact native indices and no required
> NumPy, DataFrame, or Arrow conversion.

The target user has all of these conditions:

- two or more aligned reusable Python sequences;
- a signed-integer sequence that defines the order;
- at least 100,000 records, or evidence that reordering is a real bottleneck;
- a need to preserve the exact Python objects in the aligned sequences;
- willingness to install a supported CPython wheel.

This is a focused Python-object workflow. Data already resident in NumPy,
Arrow, pandas, or Polars should normally remain in that system.

## Candidate contract

The proposed typed surface is:

```python
from typing import Iterator, Sequence, TypeVar, final

T = TypeVar("T")


def argsort(
    values: Sequence[object],
    *,
    reverse: bool = False,
) -> "Permutation": ...


@final
class Permutation:
    def __len__(self) -> int: ...
    def __getitem__(self, index: int, /) -> int: ...
    def __iter__(self) -> Iterator[int]: ...
    def apply(self, sequence: Sequence[T], /) -> list[T]: ...
```

### `argsort()` invariants

- It accepts a reusable sequence and rejects a one-shot iterator or generator.
- It returns the original zero-based indices in sorted order and never mutates
  the input.
- Equal values retain encounter order, including with `reverse=True`, matching
  Python's stable sorting rule.
- Empty and one-item inputs return the corresponding identity permutation.
- Eligible exact signed-int64 values may use native Radix selection. Small,
  nearly monotonic, non-exact-integer, arbitrary-size-integer, and other
  comparable values use a stable CPython fallback.
- Comparison and allocation failures propagate as their original exceptions;
  incomparable values fail instead of receiving an invented order.
- The result owns indices only. It does not retain the source sequence or its
  elements.

The generic fallback is part of the candidate because it keeps the function
predictable. The acceleration claim, if the gates pass, remains limited to
eligible signed-int64 sequences.

### `Permutation` invariants

- Instances are created by `argsort()`; direct construction is unsupported.
- `len()`, iteration, non-negative indexing, and negative indexing return
  ordinary Python integers. Slicing is not part of the first contract.
- The logical order is immutable. Equality and ordering between permutation
  objects have no value semantics; callers can compare `list(order)` when
  needed.
- `apply(sequence)` requires a reusable sequence with exactly the source
  length. A mismatch raises `ValueError`; a one-shot input raises `TypeError`.
- `apply()` always returns a new `list`, leaves its source unchanged, and
  preserves the exact identity of every source object.
- Applying the plan to another same-length sequence is intentional. The plan
  validates length, not whether the second sequence was the construction
  source.
- Pickling, a public constructor, mutation, slicing, inversion, composition,
  and semantic hashing are outside the first contract.

### Buffer contract

`memoryview(order)` must expose a read-only, one-dimensional, C-contiguous
unsigned-index buffer:

- four-byte indices and format `"I"` when the source length fits `uint32`;
- eight-byte indices and format `"Q"` only when required;
- shape `(len(order),)` and stride equal to the item size;
- payload size exactly `len(order) * itemsize`.

The owning permutation must remain alive while a view exists. NumPy may
consume this buffer optionally, but NumPy is not a runtime dependency and the
candidate does not promise a NumPy-specific wrapper.

## Explicit non-goals

The first proposal does not include:

- `key=`, `apply_many()`, `inverse()`, `compose()`, or serialization;
- partial, streaming, parallel, GPU, or external-memory ordering;
- float acceleration or new NaN and signed-zero semantics;
- a promise to beat NumPy for resident arrays;
- a general replacement for `sorted()`, `list.sort()`, or DataFrames;
- a new package version merely because the private prototype already exists.

Repeated `order.apply(column)` calls are the intentionally visible workflow.
The private fused `apply_many()` experiment missed its own fixed performance
gate, so convenience alone is not sufficient to expand the public surface.

## Frozen usability workloads

The next benchmark must construct ordinary Python lists before the timed
region and return ordinary Python lists from the complete operation. Each
output is checked by exact object identity as well as value equality.

| Workload | Sequences | Ordering values | Direction | Purpose |
|---|---:|---|---|---|
| Event batch | 2 | disordered signed-int64 timestamps plus an event-object list | ascending | Smallest aligned shape and broad integer range |
| Event batch, nearly ordered | 2 | increasing timestamps with 0.2% deterministic swaps plus event objects | ascending | Required Timsort-friendly negative control |
| Ranking export | 3 | duplicate-heavy integer scores, user IDs, and metadata objects | descending | Stability and common ranking semantics |
| Simulation columns | 5 | disordered signed-int32 step/group values plus four heterogeneous Python columns | ascending | Reuse benefit as aligned-column count grows |

Every workload runs at 10,000, 100,000, and 1,000,000 records with fixed,
versioned seeds. Full signed-int64 boundaries, all-equal inputs, empty/single
inputs, tuples, strings, generic comparable objects, arbitrary-size integers,
incomparable values, length mismatches, and generators belong to the semantic
suite rather than the performance grid.

The documentation usability example must require no more than one import, one
constructor call, and one `apply()` call per aligned sequence. It must also
show the equivalent Python baseline and say when not to use BielSort.

## Frozen baselines

All timed implementations perform the same logical operation and produce
ordinary Python lists unless explicitly labeled as the resident-array
negative control.

### Direct Python

```python
order = sorted(range(len(keys)), key=keys.__getitem__, reverse=reverse)
outputs = [[column[index] for index in order] for column in columns]
```

Construction and every application are included. This is the primary
baseline because it has the same reusable-order semantics and no third-party
dependency.

### `more_itertools.sort_together()`

The benchmark calls `sort_together(columns, key_list=(0,),
reverse=reverse)` and normalizes its outputs to lists. Import and initial
input construction are excluded; sorting and output creation are included.
This baseline represents the established aligned-iterable convenience API,
even though it does not return a reusable compact plan.

### NumPy from Python lists, end to end

The timed region converts the integer key list to `int64`, constructs a stable
indirect order, converts each aligned Python column to the required array
representation, applies the order, and returns Python lists. The descending
ranking case must preserve tie encounter order rather than reverse an
ascending order blindly.

### NumPy-resident negative control

Arrays exist before timing, results remain arrays, and stable `argsort` plus
indexed application are timed. This result is reported but is not a BielSort
promotion gate: it documents the storage model BielSort is not designed to
beat.

Dependency versions, compiler flags, Python build, CPU, operating system, raw
samples, rotation order, and seeds must be stored in the result artifact.

## Pre-registered decision gates

Existing 2026-08-05 results informed these thresholds but cannot count toward
them. The new implementation and benchmark must be committed before one
canonical decision run. Timing uses seven rotated samples and their median;
incremental peak RSS uses three isolated child processes.

### 1. Semantics and usability — all required

- Every differential, stability, identity, exception, immutability, lifetime,
  reverse, fallback, and buffer test passes.
- The callable signatures, runtime introspection, and PEP 561 stubs match on
  every supported CPython version.
- The documented three-line core workflow runs from a clean built wheel with
  no optional dependency.
- Error messages identify a one-shot input or length mismatch without exposing
  a private implementation name.

Any failure stops promotion regardless of speed.

### 2. Complete-flow speed against direct Python

The target grid contains the three disordered workflows at 100,000 and one
million records, for six cases total:

- at least five of six reach `1.50x`;
- none falls below `0.85x`;
- both nearly ordered event cases at those sizes reach at least `0.85x`;
- no 10,000-record workflow falls below `0.80x`.

These gates measure construction plus all applications, not a native kernel
in isolation.

### 3. Complete-flow speed against `sort_together()`

- at least five of the same six disordered large cases reach `1.25x`;
- none of the large cases, including nearly ordered inputs, falls below
  `0.85x`.

If the established convenience API is just as fast end to end, the native
package has not demonstrated enough workflow value.

### 4. End-to-end NumPy boundary

- BielSort reaches at least `1.00x` in four of the six disordered large cases;
- no disordered large case falls below `0.80x`;
- every NumPy-resident result is reported prominently, without treating a
  loss as a defect.

This does not claim superiority over NumPy. It checks whether avoiding
conversion has practical value when the data begins and ends as Python
objects.

### 5. Incremental peak memory

At one million records:

- BielSort uses at most `0.70x` the direct-Python incremental peak RSS in at
  least two of the three disordered workflows;
- it also uses at most `0.70x` the `sort_together()` incremental peak in at
  least two of those workflows;
- no disordered or nearly ordered workflow exceeds `1.10x` either Python
  baseline;
- the compact result payload satisfies the exact four-/eight-byte formula.

NumPy memory is reported separately and does not need to be beaten.

### 6. Engineering quality

- optimized and debug extension builds pass the full test suite;
- AddressSanitizer and UndefinedBehaviorSanitizer pass;
- native code compiles with `-Wall -Wextra -Werror` where supported;
- source builds pass on CPython 3.9–3.14 on Linux, Windows, and macOS;
- the build-only wheel matrix passes for every currently supported platform;
- strict typing, stub/runtime comparison, strict documentation, wheel-content
  inspection, and clean-wheel installation pass.

## Decision rule

Passing every gate authorizes only a public-API promotion review. That review
must inspect the final diff, compatibility surface, docs, and package cost
before deciding whether an `0.3.0rc1` is justified. It does not automatically
authorize a merge, tag, TestPyPI upload, PyPI upload, or stable release.

If a gate fails, the result remains versioned private research. Thresholds
must not be weakened after observing the canonical run. A materially new
hypothesis requires a separately committed protocol and retains the failed
result beside it.

## Private implementation checkpoint

The frozen contract is implemented only in the private
`bielsort_native._reorder_plan` module. Its thin `argsort()` façade delegates
to the existing compact C permutation and is explicitly absent from the
public `bielsort` and `bielsort_native` exports. Dedicated tests cover the
provisional signature, stable directions, fallbacks, identity, source
lifetime, both buffer widths, errors, and deferred behavior.

The versioned `benchmarks/reorder_plan_candidate.py` harness implements the
four workload shapes and all frozen baselines, time gates, isolated-memory
gates, raw samples, rotation order, and environment metadata. This checkpoint
records implementation readiness only.

The first canonical attempt completed its timing matrix but is invalid because
its `ru_maxrss` subtraction returned zero for every memory worker. The
[invalid-attempt record](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical-invalid-ru-maxrss.md)
preserves its JSON, diagnosis, and passing-but-incomplete time evidence.

Before another decision run, memory instrumentation is corrected without
changing a workload or threshold: each child constructs its inputs, emits a
ready checkpoint, and waits while the parent records current Linux RSS from
`/proc/<pid>/statm`; the parent then starts the operation and samples every
0.5 ms. Undefined zero-denominator ratios render as `n/a`. The correction and
invalid record must be committed before the one corrected canonical run.

That first correction exposed a second instrumentation boundary: parent
sampling continued while the child constructed its correctness reference
after the measured operation. The resulting
[validation-overlap record](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical-invalid-validation-rss.md)
retains a passing time matrix, but its memory values and combined decision are
invalid.

The final frozen correction adds an `operation-complete` checkpoint. The child
holds the measured result and waits; the parent takes its final sample, stops
memory measurement, then authorizes validation. A regression test requires
the output metadata to state that validation was excluded. Workloads,
algorithms, seeds, repetitions, and every threshold are still unchanged. This
correction and both invalid attempts must be committed before the corrected
decision run.

## Canonical result

The corrected canonical run started from clean commit `8886573` and retained
the exact pre-registered workloads, repetitions, baselines, and thresholds.
Every sample confirms that correctness validation happened after peak-RSS
sampling stopped. The complete result is preserved in the
[canonical report](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical.md).

All three time gates passed. In the six disordered large cases, BielSort met
the direct-Python target in all six, the `sort_together()` target in all six,
and the end-to-end NumPy target in all six. At one million records, complete
disordered workflows were `4.83x–5.88x` faster than direct Python. The required
nearly ordered control remained within its time floor at `0.93x`.

The compact payload requirement and the intended disordered-memory targets
also passed. BielSort used `0.44x–0.55x` the incremental peak RSS of direct
Python and `0.20x–0.23x` that of `sort_together()` across the three disordered
one-million-record workflows. However, the nearly ordered control used
`1.1205x` direct Python's incremental peak RSS, exceeding the frozen `1.10x`
maximum. The peak-memory gate, and therefore the overall local performance
gate, **failed**.

This is a valid negative result. It does not authorize public `argsort` or
`Permutation` exports, portability promotion, a version change, merge, tag,
or publication. The threshold will not be weakened. A follow-up may investigate
only a separately pre-registered, memory-focused hypothesis—such as avoiding
the duplicate snapshot/compact-buffer transition on the nearly monotonic
fallback—and must retain this failed canonical record.

That separate hypothesis is now frozen in the
[nearly ordered memory continuation](reorder-plan-memory-continuation.md). It
targets only the eager exact-list/tuple snapshot, retains all original gates,
and adds a stricter `1.05x` focused memory ceiling before implementation.

## Why this is a credible differential, not an exclusivity claim

NumPy, Arrow, Polars, pandas, and more-itertools already solve related forms
of indirect or aligned sorting. BielSort's candidate is not exclusive as an
idea or algorithm. Its narrower potential differential is the combination of
stable signed-integer ordering, compact reusable indices, native application
to arbitrary Python objects, and no required columnar conversion. The frozen
end-to-end gates determine whether that combination is useful enough to
justify a public API.
