# Limits and compatibility

BielSort remains correct outside its fast path because it delegates to
Timsort. The distinction is about expected performance and supported binary
platforms, not about producing a different sorted order.

!!! note "Stable release versus research source"

    This page describes stable `0.2.0`. The unreleased 0.3 research branch
    additionally evaluates native keyless `reverse=True` for eligible exact
    signed-int64 values. It has not passed the release matrix yet.

## Compatibility matrix

| Area | Current support |
|---|---|
| Python implementation | CPython only |
| Python versions | 3.9–3.14 |
| Fast-path values or key results | exact `int` in signed 64-bit range |
| Stable sorting | yes, every path |
| `key=` and `reverse=` | yes; 0.2 new-list signed-int64 key path |
| New-list API | any compatible iterable |
| In-place API | exact `list` |
| Runtime dependencies | none |
| License | MIT |

## Prebuilt wheels

The `0.2.0` release provides 36 wheels plus a source distribution.

| Operating system | Architectures |
|---|---|
| Linux | x86-64, manylinux and musllinux variants |
| Windows | x86, x86-64 |
| macOS | Intel x86-64, Apple Silicon arm64 |

Other platforms may build from source but are not part of the validated wheel
matrix. A source build needs a compatible C compiler and CPython development
headers.

## What uses the native fast path?

The accelerated Counting and Radix paths require all of the following:

- natural ascending exact integers, or an explicit new-list `key` returning
  exact signed-int64 integers in version 0.2;
- exact Python `int` objects, not subclasses;
- every value fitting between `-(2**63)` and `2**63 - 1`;
- enough elements and a distribution that makes native work worthwhile.

Even compatible integers may use Timsort when the input is small, already
ordered, or nearly monotonic.

## What falls back to Timsort?

- strings and floats;
- mixed or general Python objects;
- integer subclasses;
- arbitrary-size Python integers outside signed 64-bit range;
- generic, overflow, or unsuitable ordered-run key results;
- `reverse=True` without a key;
- every in-place call using `key=` or `reverse=True`;
- small, ordered, and nearly ordered inputs.

Fallback is part of BielSort's design. It preserves Python behavior in cases
where the native specializations do not offer a clear advantage.

## Memory

Counting and Radix Sort allocate native buffers proportional to input size.
Measured favorable workloads used more peak memory than `sorted()` and
`list.sort()`, even after the Counting Sort memory optimization.

If memory is more constrained than latency, benchmark peak RSS as well as
execution time before adopting BielSort.

The `sort_with_info()` API can apply a conservative limit to
BielSort's variable native auxiliary buffers before calling the user key. This
is not a total-process limit: it excludes input and key objects, allocator
overhead, fixed stack storage, and any memory later used by a Timsort fallback.
Supplying a limit requires an exact `list` or `tuple` so the preflight size is
known without hidden iterable materialization.

## CPython-specific implementation

The native extension uses the CPython C API and manipulates CPython list and
integer objects. PyPy and other Python implementations are not currently
supported.

## Threading and the GIL

The new-list native path can release the GIL during private buffer movement.
The in-place native path keeps the GIL because it mutates a list owned by the
caller. BielSort does not promise parallel sorting of one list.

## Pre-1.0 stability

The five canonical 0.2 function names and their documented signatures are
stable for that series. Performance heuristics and human-readable diagnostic
wording may evolve before 1.0. Keep correctness independent of the exact reason
or strategy text.

## Decision guide

=== "Consider BielSort"

    - the data is already a large `list[int]`;
    - values fit in signed 64-bit range;
    - the list is not usually nearly sorted;
    - end-to-end latency matters;
    - extra native memory is acceptable;
    - benchmarks on real data confirm an advantage.

=== "Prefer the built-in sort"

    - inputs are small or nearly ordered;
    - values are general Python objects;
    - key results are not exact signed-int64 integers;
    - code needs accelerated in-place `key=` or keyless `reverse=`;
    - portability beyond CPython is required;
    - minimizing auxiliary memory is more important;
    - there is no measured bottleneck to solve.

=== "Consider NumPy"

    - data is naturally an array rather than a Python list;
    - vectorized numerical processing continues after sorting;
    - conversion back to Python objects is unnecessary.

## Report a problem

- Use a [public issue](https://github.com/bielelias/bielsort/issues/new/choose)
  for correctness, installation, or reproducible performance problems.
- Use [private vulnerability reporting](https://github.com/bielelias/bielsort/security/advisories/new)
  for memory-safety or security issues.
