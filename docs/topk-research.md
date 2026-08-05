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
