# Practical innovation roadmap

BielSort should add capabilities only when they solve a concrete Python
workflow and pass a reproducible correctness, time, and memory gate. A feature
is not innovative merely because it has a new name or wins one synthetic
benchmark.

## Priority 1: stable compact top-k

Many programs need the best or worst few records rather than a full sort:
leaderboards, largest transactions, smallest latencies, recent event
candidates, anomaly triage, and ranking previews.

Python documents `heapq.nsmallest()` and `heapq.nlargest()` as partial-sort
tools for `k` small relative to the input. Pandas also provides ordered
`nsmallest()`/`nlargest()` with explicit tie behavior. Fast selection in NumPy,
Apache Arrow, and Polars does not generally promise stable output order:

- [Python partial sorting](https://docs.python.org/3/howto/sorting.html#partial-sorts)
- [pandas `DataFrame.nsmallest`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.nsmallest.html)
- [NumPy `argpartition`](https://numpy.org/doc/stable/reference/generated/numpy.argpartition.html)
- [Arrow `top_k_unstable`](https://arrow.apache.org/docs/python/generated/pyarrow.compute.top_k_unstable.html)
- [Polars `DataFrame.top_k`](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.top_k.html)

BielSort's candidate combines four properties for data already held in Python
sequences:

1. stable tie order;
2. `O(n log k)` native selection for eligible signed-int64 inputs;
3. compact 32- or 64-bit reusable indices;
4. native application of those indices to parallel Python sequences.

The private experiment and its fixed continuation gates are described in the
[stable top-k research proposal](topk-research.md).

## Priority 2: direct keyed top-k

The more direct Python workflow is selecting records by an integer field
without asking users to build and apply an index object themselves. A private
`top_k(records, k, key=...)` experiment should evaluate stable ties, exact
record identity, one key call per record, `O(n log k)` eligible selection, and
a compatible fallback. Its first-stage contract and fixed gates are
pre-registered in the
[direct keyed top-k research proposal](keyed-topk-research.md). Passing them
would still not approve a public API or release.

## Priority 3: permutation toolkit

If the compact permutation becomes public, the next direct operations should
be evaluated together:

- `apply_many()` to validate and reorder several parallel sequences in one
  call;
- `inverse()` to restore original order after downstream processing;
- `compose()` to combine two reorderings without materializing Python integer
  indices.

These operations make the result useful as a small data-alignment primitive,
not only as the output of one sorting function. They should remain private
until naming, errors, memory behavior, and measurable benefit are fixed.

The first `apply_many()` experiment passed correctness and regression checks
but missed its fixed complete-permutation performance gate. It remains a
private ergonomics experiment, not a promoted performance feature. `inverse()`
and `compose()` are deferred until users demonstrate a need for reusable
parallel-list permutations.

## Priority 4: sorted groups and rank boundaries

Telemetry and event workloads often need group starts, counts, ranks, or
deduplicated integer keys immediately after sorting. A future experiment can
derive group boundaries from the ordered native keys while they are already
in cache, avoiding a second Python pass. The useful output would be compact
boundaries plus counts, not an attempt to become a DataFrame library.

## Priority 5: wider integer domains

Unsigned 64-bit identifiers and timestamps are a practical extension of the
existing signed-int64 specialization. This work should come after top-k
because it broadens eligibility but does not create a new workflow by itself.

## Deliberately deferred

- Beating NumPy for arrays already stored in NumPy is not the target; NumPy's
  indirect sort and `take_along_axis()` already operate in its native storage
  model.
- Floating-point acceleration waits for an explicit, tested NaN and signed-zero
  ordering contract.
- Parallel and out-of-core sorting wait for real workloads that justify their
  complexity, platform cost, and failure modes.
- Bindings for other languages wait until the Python API demonstrates durable
  value.

This order keeps the project focused: one practical niche, one private
prototype, fixed gates, and honest negative results at a time.
