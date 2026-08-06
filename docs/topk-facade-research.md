# Research protocol: unified stable top-k façade

!!! warning "Private experiment"

    This protocol does **not** add `bielsort.top_k`, export `TopKInfo`, change
    the package version, approve a merge, or approve a release. It fixes the
    façade contract, crossover rule, benchmark cases, and decision gates
    before implementation and canonical timing.

## Question being tested

The existing private prototypes prove two useful pieces independently:

- compact stable top-k selection for natural exact signed-int64 values;
- direct stable top-k selection for records with an explicit key.

The next question is whether one private façade can select a safe path for
natural ordering and explicit keys, keep diagnostics consistent, and avoid
forcing an `O(n log n)` full sort when `k` is small or an `O(n log k)` heap
when `k` is large.

The private candidate will be named `top_k_adaptive` inside an internal
module. It will not be re-exported by either public package.

## Fixed private contract

```python
top_k_adaptive(
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

Before implementation, the required behavior is fixed as follows:

- accept any iterable and consume it at most once;
- accept an integer index for `k`, reject `bool`, and reject negative values;
- return an empty list for `k == 0` without consuming the iterable or
  evaluating `key`;
- clamp the selected count to the number of encountered records;
- return original objects in complete sorted order, retaining encounter order
  for equal keys in both directions;
- use natural ordering when `key is None`, without inserting a Python identity
  callback;
- evaluate an explicit key exactly once per encountered record;
- compare generic keys with `<` and never compare records to break ties;
- propagate iterator, key, and comparison exceptions;
- retain the existing callback-resize safety boundary for reusable lists;
- return only the result unless `return_info=True`, in which case it returns
  `(result, info)`.

The private immutable diagnostic record has the reviewed fields from the
[top-k API review](topk-api-review.md): normalized algorithm and key-domain
names, decision reason, input and selected sizes, direction, native-memory
estimates, requested limit, and whether that limit forced a fallback. Its
`used_native` property is derived from the normalized algorithm. Thresholds
and prose reasons are not compatibility promises.

When `max_native_auxiliary_bytes` is supplied, the input must be an exact
built-in `list` or `tuple`. A conservative route-specific decision occurs
before iteration or key evaluation. The `heapq` policy falls back at that
checkpoint; the `raise` policy raises `MemoryError` there.

## Fixed strategy

The crossover is intentionally simple and integer-only:

```text
k == 0                                  -> trivial result
selected * 8 >= n                       -> adaptive full stable sort
n < 2,048                               -> heapq selection
otherwise                               -> partial selection
```

`selected` means `min(k, n)`. The full-sort rule takes precedence over the
small-input rule. The factor eight and the 2,048-record floor are private
heuristics and may change after a new pre-registered experiment.

The route table is fixed before implementation:

| Input/key shape | Partial route | Full-sort route |
|---|---|---|
| natural exact signed-int64 | compact native stable top-k | compact native full argsort |
| other natural ordering | `heapq` | CPython stable Timsort |
| explicit exact signed-int64 key | native direct top-k | existing adaptive native sort |
| other explicit key | native generic top-k | cached-key Timsort replay |

The explicit-key full route reuses the existing private adaptive sorter. This
is important because an exact-int64 key may still benefit from Counting or
Radix sorting when `k` is large; blindly routing every large selection to
Python `sorted()` would discard that advantage.

## Exploratory crossover input

One unversioned local exploration, performed before this protocol existed,
compared heap selection with full sorting at ratios from `1/1,024` to `1/1`.
It suggested a generic-key crossover around `k = n / 8` to `n / 4`, while
exact-int64 native paths remained competitive at substantially larger `k`.

Those observations only selected the fixed `selected * 8 >= n` experiment.
They are not canonical evidence, do not count toward the gate, and must not be
reported as a product performance result.

## Pre-registered canonical matrix

The canonical run uses exactly 200,000 records, seven paired rotated blocks,
and one call per algorithm per block. It covers five deterministic domains:

1. natural dense signed-int64 values;
2. natural strings;
3. records with a dense signed-int64 `itemgetter(0)` key;
4. records with an arbitrary-size-integer `itemgetter(0)` key;
5. records with a string `itemgetter(0)` key.

For every domain it measures smallest and largest selection at
`k = n / 64`, `n / 16`, `n / 8`, `n / 4`, and `n / 2`: 50 timing cases in
total. Input generation, expected output, validation, diagnostics, garbage
collection, and destruction of the previous result remain outside the timed
region.

The comparator follows the same pre-registered crossover rather than choosing
the faster baseline after measurement:

- `heapq.nsmallest()` or `heapq.nlargest()` for `n / 64` and `n / 16`;
- stable `sorted()` followed by a slice for `n / 8`, `n / 4`, and `n / 2`.

Results must match a complete stable sort by exact object identity. The report
retains every raw duration, paired baseline/candidate ratio, median, median
absolute deviation, environment field, configuration value, and observed
diagnostic category.

## Mandatory semantic and safety probes

The canonical harness and unit suite must verify:

- exact one-call key behavior on both sides of the crossover;
- no consumption or key validation for `k == 0`;
- rejection of negative and Boolean `k` before consumption;
- no artificial key invocation for natural ordering;
- one-shot iterables consumed once;
- stable duplicate handling for smallest and largest selection;
- iterator, key, and comparison exception propagation;
- conservative memory fallback and `MemoryError` before key evaluation;
- immutable structured diagnostics with normalized algorithm values;
- source-list resize protection for explicit-key native callbacks;
- absence of `top_k`, `top_k_with_info`, and `TopKInfo` from the public API,
  runtime exports, and public stubs.

## Fixed decision gates

The private façade advances to a public-API proposal only if all of these
conditions pass without changing this protocol:

1. all 50 canonical results, routing assertions, and mandatory semantic probes
   pass;
2. no canonical median paired baseline/candidate ratio is below `0.85x`;
3. at least 40 of the 50 ratios reach `0.95x` or better;
4. the complete local suite, warning-clean native build, ASan/UBSan, supported
   source-build CI, strict documentation, and non-publishing wheel matrix pass;
5. the façade and diagnostic names remain private throughout this experiment.

Passing only authorizes a separate public API proposal. It is not evidence of
external demand, a universal speed claim, a version decision, or permission to
publish. A failed gate remains in the project record; thresholds must not be
relaxed after canonical execution.

## First canonical result

The single canonical execution on implementation commit `4f046a6` passed the
unchanged local gate. All 50 results and route assertions matched, every
semantic probe passed, no median paired ratio fell below `0.85x`, and 47 cases
reached `0.95x` or better against the comparator fixed for their `k/n` ratio.

Signed-int64 cases measured `1.49x–3.73x` for natural values and
`2.35x–4.45x` for explicit keys. Generic keyed paths measured
`0.97x–1.61x`. Natural-string fallbacks included the three below-parity cases,
with a minimum of `0.91x`; these negative results are retained and the
crossover was not retuned.

See the
[versioned result and limitations](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-unified-topk-facade.md)
and its linked raw JSON. The local pass authorizes hosted source, sanitizer,
and non-publishing wheel checks only. Public names and a release remain
unapproved.
