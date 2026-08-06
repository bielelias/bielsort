# Research: nearly ordered reorder-plan memory

!!! warning "Pre-registered continuation — 2026-08-06"

    This protocol was committed after the valid failed reorder-plan result and
    before changing the candidate implementation. It preserves the original
    result and every original gate. It does not authorize a public API,
    version, merge, tag, or publication.

## Prior result

The corrected
[reorder-plan canonical run](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical.md)
passed every frozen time gate and the intended disordered-memory targets. The
overall decision remained **failed** because the one-million-record nearly
ordered workflow used `1.1205x` the incremental peak RSS of direct Python,
above its unchanged `1.10x` maximum.

This continuation does not reinterpret or replace that result. It tests one
new implementation hypothesis against a separately frozen decision.

## Allocation diagnosis and hypothesis

The private constructor currently starts with `PySequence_List(sequence)`.
For an exact input `list`, that creates a second pointer array while retaining
references to the same objects. At one million elements, the snapshot's item
array alone is approximately 7.6 MiB. It remains alive while the nearly
monotonic route constructs and sorts a Python `list[int]`, and while those
indices are packed into the compact four-byte result.

The observed median difference between BielSort and direct Python was about
6.5 MiB, so the snapshot is a plausible primary cause. This is allocation
accounting, not yet causal benchmark proof.

The single implementation hypothesis is:

> Replace the eager snapshot with `PySequence_Fast`. Borrow exact built-in
> lists and tuples for the duration of the operation, while retaining snapshot
> behavior for other reusable sequences and subclasses. Teach the internal
> Timsort fallback to read either fast-sequence representation.

This should remove one `O(n)` pointer snapshot from common exact-list and
exact-tuple calls. It must not remove the compact result, change strategy
selection, alter stability, mutate the source, retain it after return, or add
a public symbol.

## Fixed implementation boundary

Allowed changes are limited to:

- acquiring the private argsort input with `PySequence_Fast` instead of
  `PySequence_List`;
- using `PySequence_Fast_GET_SIZE` and the existing sequence `__getitem__`
  contract inside the Timsort fallback;
- adding tests and a separate benchmark harness for this continuation;
- documentation and result artifacts required by this protocol.

Exact `list` and `tuple` inputs may be borrowed with an owned reference during
the call. Custom sequences and list/tuple subclasses must still be
materialized by `PySequence_Fast`, preserving snapshot isolation. Radix,
Counting, compact-buffer layout, permutation application, strategy thresholds,
and every public module remain unchanged.

If achieving the gate requires a different allocator, a custom Timsort,
in-place mutation, a public API change, or relaxed thresholds, this hypothesis
fails and a new protocol is required.

## Frozen semantic and engineering gates

All are required:

1. The complete existing test suite passes, including exact identity,
   stability, both sort directions, generic fallback, arbitrary-size integers,
   exception propagation, compact-buffer invariants, and source lifetime.
2. New differential coverage exercises exact lists and tuples on trivial,
   nearly monotonic, disordered int64, generic-object, and arbitrary-size-
   integer routes.
3. A comparison object that mutates its exact source list during fallback
   cannot crash or corrupt the returned compact permutation. Existing
   exception behavior remains compatible.
4. List/tuple subclasses and custom reusable sequences retain materialized
   snapshot behavior.
5. The candidate remains absent from `bielsort` and `bielsort_native` public
   exports, and no package version or stub changes.
6. Optimized and debug builds, `-Wall -Wextra -Werror`, the complete local
   suite, ASan/UBSan, strict typing/stub checks, and strict documentation pass
   before hosted portability is considered.

## Frozen performance protocol

The continuation reuses the exact four workloads, three sizes, seeds,
baselines, operation boundaries, seven rotated timing repetitions, three
isolated memory repetitions, and parent-sampled Linux RSS method from the
original protocol. Correctness validation remains outside memory sampling.

The implementation and dedicated harness must be committed before one
canonical continuation run. The harness must refuse canonical mode with a
dirty tree, changed sizes, changed workloads, fewer repetitions, missing
optional baselines, or pre-existing output artifacts.

### Original gates retained

Every original direct-Python, `sort_together()`, end-to-end NumPy, compact-
payload, disordered-memory, nearly ordered time-floor, and small-input gate
must pass unchanged. Passing only the focused memory check is insufficient.

### Additional focused gates

At one million records in `event-batch-nearly-ordered`:

- median candidate/direct-Python incremental peak RSS is at most `1.05x`,
  providing headroom below the original `1.10x` limit;
- at least two of the three same-seed candidate/direct-Python RSS ratios are
  at most `1.10x`;
- the compact result remains read-only with a four-byte item size and exactly
  `4,000,000` payload bytes;
- candidate/direct-Python time is at least `0.90x` at both 100,000 and one
  million records.

The result must report all NumPy-resident controls but does not need to beat
them. Ratios are calculated from unrounded bytes and seconds.

## Decision rule

A pass authorizes only local reconsideration of the candidate and the
previously deferred hosted portability/API review. It does not authorize a
public `argsort`, `Permutation`, release candidate, merge, tag, TestPyPI, or
PyPI operation.

A failure is preserved beside the original failed result. Thresholds cannot
be changed after execution, and an unchanged implementation cannot receive a
second decision run merely because of unfavorable measurements.

