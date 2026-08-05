# Research: stable compact top-k

!!! warning "Private prototype"

    BielSort does not expose `topk` or `top_k`. The native symbol described
    here is research-only and may change or be removed.

## Problem

Sorting every item is unnecessary when a program needs only the smallest or
largest `k` records. The useful result may also need to reorder several
parallel Python sequences while preserving the original order of equal keys.

Examples include:

- top scores with aligned names and metadata;
- lowest latency events with timestamps and request identifiers;
- largest transactions with account and audit fields;
- a stable preview of ranked records before a full export.

## Candidate contract

```python
def topk_indices(
    values: Sequence[int],
    k: int,
    *,
    largest: bool = False,
) -> Permutation: ...
```

The private implementation currently uses
`_topk_int64_prototype(sequence, k, largest=False, /)`. Its invariants are:

- return at most `k` original indices in fully sorted order;
- preserve encounter order for equal values in both directions;
- leave the input unchanged;
- clamp `k` to the sequence length and reject negative `k`;
- return a compact immutable permutation that can reorder any parallel
  sequence with the same original length;
- use a native stable heap for eligible exact signed-int64 inputs when `k` is
  at most one eighth of `n`;
- use the existing compatible full-argsort path for larger `k`, generic values,
  or integers outside signed int64.

For a list or tuple on the eligible path, selection takes `O(n log k)` time
and `O(k)` variable native memory. A custom sequence may first be materialized
by CPython's sequence-fast conversion.

## Why stability matters

Python's full sort guarantees that equal keys retain their input order. The
top-k candidate preserves that contract, including at the cutoff boundary.
By contrast, NumPy documents `argpartition()` as unstable with undefined
partition order, Arrow names its operation `top_k_unstable`, and Polars does
not guarantee a particular output order for `top_k()`.

This does not make BielSort a replacement for those columnar systems. It
defines a narrower option for large data that already exists as Python
sequences and needs stable, reusable indices.

## Continuation gates

The canonical local run uses one million elements, `k` values 10, 100, and
1,000, four disordered integer distributions, both smallest and largest
directions, and seven rotated samples. That produces 24 target cases.

The private prototype advances only if:

1. every result matches stable full sorting exactly;
2. at least 18 of 24 construction cases reach `1.25x` over the equivalent
   `heapq.nsmallest()` or `heapq.nlargest()` index baseline;
3. at least 18 of 24 build-once/apply-three-sequences cases reach `1.25x` over
   the equivalent `heapq` flow;
4. no target construction or reuse case is more than 10% slower than `heapq`;
5. the compact index payload is no more than half the shallow size of the
   Python index list, before Python integer objects are counted.

The benchmark also reports full sorting, raw samples, strategies, result
storage, platform, Python, and compiler. Passing these gates authorizes more
private engineering only; it does not establish external demand or approve a
public API, version bump, or release.

## Reproduction

```bash
python benchmarks/topk_prototype.py \
  -n 100000 1000000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output stable-topk.json
```

## First canonical result

The 2026-08-05 local run passed every continuation gate. Across the 24
one-million-element target cases, construction was `1.56x–3.36x` faster than
the equivalent `heapq` baseline and `15.41x–36.99x` faster than stable full
index sorting. The complete build-once/apply-three-sequences flow was
`1.55x–3.45x` faster than the equivalent `heapq` flow.

See the
[versioned report](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-stable-topk.md)
and its linked raw samples. This result permits further private validation;
it does not yet approve a public function or a release.

## Parallel application continuation

The next private question is whether the compact result should apply itself to
several aligned sequences in one call:

```python
ordered_scores, ordered_names, ordered_metadata = order.apply_many(
    scores,
    names,
    metadata,
)
```

The candidate validates every reusable sequence and its original length before
reading selected items, returns one new list per input sequence, preserves
exact object identity, and mutates nothing. It uses `O(m)` temporary native
pointers for `m` sequences; the returned Python lists have the same payload as
calling `apply()` `m` times.

The canonical application-only gate uses one million source elements, top-k
lengths 10, 100, and 1,000, full random and identity permutations, 2, 3, and 5
parallel lists, and nine rotated samples. The method advances only if:

1. every fused result is identity-equivalent to repeated native `apply()`;
2. at least 9 of 15 target cases reach `1.05x` over repeated calls;
3. at least 3 of the 6 full-permutation cases reach `1.10x`;
4. no target case is more than 5% slower.

Small top-k calls are batched to stabilize sub-microsecond measurements. The
reported samples are normalized to one call and retain the batch size. Passing
the gate would support a permutation-toolkit proposal, not a public API or
release.

```bash
python benchmarks/permutation_apply_many.py \
  -n 100000 1000000 \
  -r 9 \
  --json-output apply-many.json
```

## Parallel application result

The 2026-08-05 canonical run did **not** pass the fixed continuation gate.
Correctness passed, no case was more than 5% slower, and 12 of 15 target cases
reached `1.05x`. Only 2 of 6 complete-permutation cases reached `1.10x`, below
the required 3.

Small top-k results approached `2x`, but the absolute saving for top-k 10 was
only about two tenths of a microsecond per call. Complete permutations were
mixed. The method therefore remains private as an ergonomics experiment and
is not promoted as a performance differentiator. See the
[versioned report](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-permutation-apply-many.md)
and its linked raw samples.

## Next practical question: keyed records

The reusable-index prototype proves the selection core, but most Python users
hold records rather than separate integer-key and payload lists. The next
private proposal will evaluate a direct stable operation shaped like:

```python
top_k(records, k, *, key=lambda record: record.score, largest=False)
```

The experiment must preserve exact record identity and stable ties, call
`key` exactly once per encountered record, leave the input unchanged, and
return a fully sorted result. It will remain private until its semantics,
compatible fallback, memory guard, and pre-registered performance gates are
reviewed independently.
