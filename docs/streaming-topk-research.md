# Research protocol: stable bounded-memory streaming top-k

!!! warning "Private experiment"

    This protocol does **not** add a public `stream_top_k`, export a stateful
    object, change the package version, approve a merge, or approve a release.
    It fixes the streaming contract, comparison matrix, memory gates, and
    failure policy before implementation or canonical measurement.

## Practical gap

The current private unified top-k façade accepts an arbitrary iterable, but it
first converts non-list and non-tuple inputs to a list so it can know `n` and
choose between partial selection and a full sort. The current private keyed C
core also uses `PySequence_Fast`, which materializes a general iterator.
Consequently, neither path is truly bounded-memory for a generator even though
the selection heap itself retains only `k` keys.

Python's [`heapq.nsmallest()` and `heapq.nlargest()`](https://docs.python.org/3/library/heapq.html)
already provide a strong streaming baseline. NumPy
[`argpartition`](https://numpy.org/doc/stable/reference/generated/numpy.argpartition.html),
Apache Arrow
[`top_k_unstable`](https://arrow.apache.org/docs/python/generated/pyarrow.compute.top_k_unstable.html),
and Polars
[`Expr.top_k`](https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.top_k.html)
target array or columnar storage and do not promise stable selected order.
pandas provides explicit ordered top-k behavior after data has entered its
tabular model.

The hypothesis is narrower: BielSort may offer useful differentiation for
records that arrive as Python iterables by combining stable encounter-order
ties, one key call per record, exact signed-int64 specialization, native
retained state proportional to `k`, and an auditable memory decision made
before consuming the stream.

This is not a claim that streaming top-k is a new algorithm or exclusive idea.
Only the measured combination and its Python-object contract may become a
BielSort differentiator.

## Fixed private contract

The private candidate will be named `stream_top_k` inside an internal module:

```python
stream_top_k(
    iterable,
    k,
    *,
    key=None,
    largest=False,
    max_native_auxiliary_bytes=None,
    on_memory_limit="heapq",
    return_info=False,
)
```

Before implementation, its required behavior is fixed:

- consume the input at most once and never copy all encountered records into
  an internal list or tuple;
- retain `O(k)` selected records and keys, excluding the iterator's own state
  and the returned list;
- accept an integer index for `k`, reject `bool`, and reject negative values
  before obtaining an iterator;
- for `k == 0`, return an empty result without obtaining an iterator,
  validating `key`, or invoking user code;
- accept natural ordering with `key=None` without inserting or calling a
  Python identity function;
- call an explicit key exactly once for each encountered record and in
  encounter order;
- return original records in complete selected order and preserve encounter
  order for equal keys for both smallest and largest selection;
- compare generic keys with `<` without comparing records as tie-breakers;
- propagate iterator, key, comparison, and allocation errors;
- release rejected records and keys during consumption rather than retaining
  them until the stream ends;
- return only the selected list unless `return_info=True`.

The streaming contract follows iterator behavior. It does not promise to
detect mutation of an external container being traversed by that iterator;
unlike sorting an owned list, the candidate has no source sequence to inspect
or replay.

## Fixed memory and fallback contract

The private native entry owns the retained record and key references plus a
monotonic encounter index. A conservative worst-case native-buffer estimate
is derived only from `k`, so a configured limit does not require a sized input.

When `max_native_auxiliary_bytes` is provided:

- validation and the native-buffer decision occur before obtaining the input
  iterator or evaluating `key`;
- `on_memory_limit="raise"` raises `MemoryError` at that checkpoint;
- `on_memory_limit="heapq"` uses the matching standard-library streaming
  selector without materializing the iterable;
- the limit covers BielSort's variable native buffers, not Python objects,
  iterator-owned storage, the result list, or total process RSS.

Diagnostics remain immutable and private. They record the normalized
algorithm, reason, number of records processed, requested and selected counts,
direction, key domain, native buffer estimate and bound, configured limit, and
whether the limit forced fallback. Proposed algorithm values are
`native-stream-int64`, `native-stream-generic`, `heapq`, and `trivial`.

## Pre-registered timing matrix

The canonical timing run uses deterministic one-shot generators and includes
generator construction and complete consumption in both timings. It uses one
million records, nine rotated paired blocks, and one call per implementation
per block.

Four domains are fixed:

1. naturally ordered dense signed-int64 values;
2. records with a dense signed-int64 `itemgetter(0)` key;
3. records with an arbitrary-size integer `itemgetter(0)` key;
4. records with a repeated string `itemgetter(0)` key.

Each domain measures smallest and largest selection at `k = 100`, `10,000`,
and `100,000`, for 24 cases. The sole timing baseline is the corresponding
`heapq.nsmallest()` or `heapq.nlargest()` call over an equivalent fresh
generator. Validation, expected-result construction, diagnostics, garbage
collection, and destruction of the previous result remain outside the timed
region.

Every raw duration, paired speedup, median, median absolute deviation,
environment field, configuration value, processed count, and observed route
must be retained in versioned JSON and Markdown. Results are compared by
record fields and stable encounter positions because separate generator calls
create distinct record objects.

## Pre-registered isolated-memory matrix

Fresh child processes measure incremental peak RSS for the candidate,
`heapq`, and the existing materializing private façade. The matrix uses one
million generated records, smallest selection, explicit signed-int64 and
string keys, and `k = 100`, `10,000`, and `100,000`.

The report retains every child-process sample and the size of the returned
selection. A lifetime probe must also show that non-selected weak-referenceable
records can be released before the iterator is exhausted.

## Mandatory semantic probes

The harness and unit suite must verify:

- exact stable equivalence to `sorted(...)[0:k]` by object identity when the
  same source objects are used;
- one-shot iteration and no hidden full materialization;
- zero consumption for `k == 0`;
- validation before iteration for invalid `k`, direction, key, limits, and
  policies;
- zero artificial key calls for natural ordering and exactly one explicit key
  call per encountered record;
- inputs shorter than `k`, empty streams, duplicate-heavy data, late switches
  from signed-int64 to generic keys, and both directions;
- keys supporting only `<`, without equality or record comparison;
- iterator, key, and comparison exception propagation with retained objects
  released afterward;
- pre-consumption native-memory fallback and `MemoryError` behavior;
- immutable normalized diagnostics and correct processed counts;
- absence of `stream_top_k`, `top_k`, and diagnostic types from public
  runtime exports and public stubs.

## Fixed decision gates

The experiment passes only if all conditions below hold without changing this
protocol after implementation:

1. every timing, memory, lifetime, correctness, route, and semantic probe
   passes;
2. no median paired candidate/`heapq` speedup is below `0.85x`;
3. at least 8 of the 12 signed-int64 cases reach `1.10x` or better, and at
   least 9 of the 12 generic-key cases reach `0.95x` or better;
4. at `k = 100,000`, candidate incremental peak RSS is at most `0.70x` the
   matching `heapq` peak in both fixed key domains;
5. at `k = 100` and `10,000`, candidate incremental peak RSS is at most
   `0.35x` the existing materializing façade peak in both fixed key domains;
6. the complete optimized and sanitized suite, warning-clean native build,
   strict typing, strict documentation, supported hosted CI, and a
   non-publishing wheel matrix pass;
7. every new symbol remains private throughout the experiment.

A failed gate remains part of the record and must not be weakened after the
canonical run. Passing authorizes only a separate API and usability review;
it does not prove external demand, justify universal claims, select a release
version, or authorize TestPyPI or PyPI publication.
