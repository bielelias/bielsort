# Research proposal: direct stable keyed top-k

!!! warning "Design only"

    BielSort does not expose `top_k`. This page fixes the private experiment's
    contract and decision gates before implementation or canonical timing.

## User problem

The compact top-k prototype accepts a sequence of integer keys and returns a
reusable permutation. That is useful for parallel lists, but it is indirect
for the more common Python shape: a list of records with an integer field.

Examples include selecting:

- the ten slowest request records by latency;
- the largest transactions by signed amount;
- the lowest-cost route candidates;
- a stable leaderboard whose equal scores retain arrival order.

The eventual public idea is deliberately small:

```python
def top_k(
    iterable,
    k,
    *,
    key=None,
    largest=False,
): ...
```

It would return the selected records directly as a new fully sorted list. A
public API is not approved by this proposal.

## Stage-one private contract

The first native experiment will be named
`_topk_by_int64_key_prototype(iterable, k, key, largest=False, /)`. It targets
only exact signed-int64 key results so that the eligible core can be measured
without pretending that generic fallback semantics are already solved.

Its required behavior is:

- reject negative `k` before consuming the iterable;
- return `[]` for `k == 0` without consuming the iterable or calling `key`;
- otherwise consume the iterable once and call `key` exactly once per record;
- clamp `k` to the number of records;
- return at most `k` original objects in fully sorted order;
- preserve encounter order for equal keys for both smallest and largest;
- preserve exact object identity and leave reusable inputs unchanged;
- propagate exceptions raised by iteration or `key`;
- reject non-exact-int or out-of-int64 key results in this private stage.

For list and tuple inputs with small `k`, the intended algorithm is a native
stable heap using `O(n log k)` time and `O(k)` native entries. A one-shot
iterable must first be materialized, so its record references require `O(n)`
memory. The output always requires `O(k)` Python references.

## Why this is more practical than another permutation operation

Users can express the operation in one call and receive their original
records. They do not need to extract a key list, understand a private index
object, or apply that object to payload lists. The specialization remains
narrow: it is for large Python-native record collections, small `k`, and
exact signed-int64 keys. NumPy, DataFrame, and database-native data should
normally stay in those systems.

## Pre-registered benchmark

The canonical performance run will use one million tuple records, an
`operator.itemgetter(0)` key, `k` values 10, 100, and 1,000, four disordered
signed-int64 distributions, and both smallest and largest directions. That
produces 24 target cases. Each case will retain at least seven rotated timing
samples and compare:

1. the private native direct result;
2. `heapq.nsmallest()` or `heapq.nlargest()` with the same key;
3. full stable `sorted(..., key=..., reverse=...)[:k]` as a reference and
   context, not as the primary gate.

Construction of the record list is outside the timed region. Correctness is
checked by object identity against stable full sorting. A separate call-count
key validates exact key evaluation semantics outside timed samples.

The stage-one prototype advances only if:

1. every result is identity-equivalent to stable full sorting, including ties;
2. all call-count, empty, boundary, exception, and input-preservation tests
   pass;
3. at least 18 of 24 one-million-record target cases reach `1.25x` over the
   equivalent `heapq` operation;
4. no target case is more than 10% slower than `heapq`;
5. code inspection and tests confirm an `O(k)` native selection heap with no
   `O(n)` key array for reusable list or tuple inputs.

The fixed gates evaluate an eligible private core only. Passing them would
authorize work on a compatible fallback, memory guard, diagnostics, and API
review. It would not approve a public symbol, version bump, or release. A
failed gate will be recorded without changing thresholds after measurement.

## Promotion questions after a passing core

Before a public proposal, BielSort would still need to answer:

- how generic and out-of-range keys fall back without a second key call;
- whether `key=None` should share the existing keyless top-k path;
- whether a conservative memory limit belongs in the API;
- how much advantage remains for common Python `lambda` and `attrgetter`
  callables;
- whether direct records or reusable indices represent actual user demand.

Until those questions have evidence, `_Permutation`, `apply_many()`, and the
new keyed operation remain implementation research.
