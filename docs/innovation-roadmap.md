# Practical innovation roadmap

BielSort should add capabilities only when they solve a concrete Python
workflow and pass a reproducible correctness, time, and memory gate. A feature
is not innovative merely because it has a new name or wins one synthetic
benchmark.

The 2026-08-06 [market opportunity review](market-opportunities.md) compares
the current research with CPython, NumPy, pandas, Polars, Arrow,
more-itertools, and Sorted Containers. It recommends pausing new algorithm
variants and validating one narrower product hypothesis: a compact stable
reorder plan for aligned Python sequences. Functional demand is visible, but
large-scale performance demand remains unproven. That API and usability
protocol is now frozen in the
[compact reusable reorder-plan review](reorder-plan-api-review.md). The next
step is a private implementation and one unchanged canonical end-to-end run,
not public API or release work.

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

The exact-int64 stage-one core passed its fixed local gate in 18 of 24 target
cases, with no regression beyond the allowed bound. The next gates are a
one-call-compatible generic fallback, common callable shapes, isolated memory,
and cross-platform validation; the symbol remains private.

## Priority 3: bounded-memory streaming top-k

The unified private façade currently materializes a general iterable so it can
choose between partial selection and a full sort. That behavior is reasonable
for an adaptive batch API but is not suitable for a generator whose complete
contents should never reside in memory.

A separate private experiment will test a strict streaming contract: consume
once, retain only the selected records and keys, preserve stable ties, call an
explicit key once, specialize signed-int64 keys in native code, and decide a
native-memory limit from `k` before obtaining the iterator. Its fixed contract
and gates are in the
[streaming top-k research protocol](streaming-topk-research.md).

The concept is not exclusive to BielSort: Python's `heapq` is the mandatory
baseline. The potential differentiation is the measured combination of native
Python-object selection, stability, bounded retained state, and structured
diagnostics.

The first implementation passed its semantic and timing gates, reaching up to
`1.80x` `heapq`, and used only `0.00x–0.13x` the incremental RSS of the
materializing façade. It did not pass promotion because its `k=100,000`
incremental RSS remained `0.76x–0.80x` `heapq`, above the pre-registered
`0.70x` maximum. A second private layout may reduce per-selected-item native
state; the failed result and original threshold remain binding evidence.

That compact follow-up reduced the `k=100,000` ratios to `0.62x` for int64
keys and `0.67x` for strings, passing memory, while every generic timing case
also passed. Its overall decision is still failed because 7 of 12 signed-int64
cases reached `1.10x`, one short of the fixed count. Medium-`k` finalization is
the next bounded local optimization; no public API follows from the current
evidence.

That local optimization pass is complete. Stable medium-`k` Radix finishing
and a lower-movement exact heap each retained the semantic, memory, and
generic-key wins in separate canonical runs, but both again reached only 7 of
12 signed-int64 targets. A final bottom-up Floyd screening produced the same
count. Streaming remains a useful private research result—especially for
large `k` and bounded memory—but further work now requires a new hypothesis or
external workload evidence rather than another rerun of the fixed local gate.

## Priority 4: permutation toolkit

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

## Priority 5: sorted groups and rank boundaries

Telemetry and event workloads often need group starts, counts, ranks, or
deduplicated integer keys immediately after sorting. A future experiment can
derive group boundaries from the ordered native keys while they are already
in cache, avoiding a second Python pass. The useful output would be compact
boundaries plus counts, not an attempt to become a DataFrame library.

## Priority 6: wider integer domains

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
