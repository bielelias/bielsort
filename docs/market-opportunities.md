# Market opportunity review

!!! info "Decision snapshot — 2026-08-06"

    BielSort should stop adding sorting variants and validate one product
    hypothesis: a compact, stable, reusable reorder plan for aligned Python
    sequences. This is **not** a novel algorithm and is **not** yet proven
    market demand. It is the best-supported intersection of a recurring
    Python workflow and BielSort's existing measured strengths.

## Question and method

This review asks a narrower question than “what else can BielSort implement?”:

> Which workflow is insufficiently convenient or efficient for data that
> already lives in ordinary Python sequences, and which existing BielSort
> research is closest to solving it?

The review compares official product documentation, public user questions,
and BielSort's versioned benchmark records. It separates three kinds of
evidence:

1. **Capability evidence:** what established tools already provide.
2. **Problem evidence:** whether users repeatedly ask for the workflow.
3. **Performance-demand evidence:** whether the workflow is frequently a
   measured bottleneck at BielSort's target scale.

The first two are available. The third remains weak. Search results, one
question, stars, or download counts would not establish a market by
themselves.

## Existing solutions

| System | Data model | Existing relevant capability | Implication for BielSort |
|---|---|---|---|
| CPython | Python objects and iterables | `sorted()`/`list.sort()` provide stable complete ordering; `heapq.nsmallest()` and `nlargest()` retain a heap of selected records | The standard library is the mandatory semantic and streaming baseline; replacing it generally is not a credible goal |
| NumPy | homogeneous arrays | [`argsort`](https://numpy.org/doc/stable/reference/generated/numpy.argsort.html) returns reusable indices, supports stable ordering, and works with [`take_along_axis`](https://numpy.org/doc/stable/reference/generated/numpy.take_along_axis.html) | BielSort should not compete when data already lives in an `ndarray` |
| Polars | columnar DataFrames | [`arg_sort_by`](https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.arg_sort_by.html) can maintain equal-value order and its indices feed `gather` | Stable reusable ordering is already first-class inside a modern DataFrame engine |
| Apache Arrow | typed columnar arrays and tables | [`sort_indices`](https://arrow.apache.org/docs/python/generated/pyarrow.compute.sort_indices.html) is stable, [`take`](https://arrow.apache.org/docs/python/generated/pyarrow.compute.take.html) applies indices, and [`inverse_permutation`](https://arrow.apache.org/docs/python/generated/pyarrow.compute.inverse_permutation.html) already exists | `argsort`, application, and inversion are not exclusive concepts; BielSort's possible niche is Python-object storage |
| pandas | labeled tabular data | [`sort_values`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html) reorders complete frames; [`nsmallest`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.nsmallest.html) provides ordered partial selection; an [`Index`](https://pandas.pydata.org/docs/reference/api/pandas.Index.sort_values.html) can return an indexer | Users already in pandas should remain there instead of converting through BielSort |
| more-itertools | general Python iterables | [`sort_together`](https://more-itertools.readthedocs.io/en/latest/api.html#more_itertools.sort_together) sorts spreadsheet-like parallel inputs by one or more of them | The aligned-sequence workflow is established in Python, but the existing API does not aim to provide a compact reusable native plan |
| Sorted Containers | mutable Python collections | [`SortedList`](https://grantjenks.com/docs/sortedcontainers/sortedlist.html), `SortedDict`, and `SortedSet` maintain dynamic sorted state | Dynamic insertion/search is a mature, different niche; BielSort should not build a competing container |

## What the public evidence does and does not say

The aligned-sequence problem is recurring rather than invented for BielSort.
`more-itertools` describes `sort_together()` as spreadsheet-like column
sorting. Public questions from
[2012](https://stackoverflow.com/questions/9968297/python-argsort-indices-based-on-multiple-arrays)
and
[2021](https://stackoverflow.com/questions/70202457/sorting-multiple-lists-together-in-place)
ask for an argsort-like result or for several lists to retain their alignment.

That is evidence of a durable **functional** need. It is not evidence that
millions of Python objects are commonly sorted this way, that sorting is the
application bottleneck, or that users will accept a native wheel for it.
NumPy, Polars, Arrow, pandas, and the common recommendation to combine fields
into records already absorb much of the potential audience.

The realistic target user is therefore narrow:

- the data already exists in two or more aligned Python sequences;
- converting the complete workflow to a DataFrame or array is undesirable;
- one exact signed-int64 value or key defines a stable order;
- the same order must be applied to several sequences;
- the data is large and reordering is a measured cost;
- supported CPython wheels are acceptable.

## Opportunity scorecard

Scores range from 1 (weak) to 5 (strong). “Readiness” rewards existing tested
code and bounded implementation risk; it does not imply public API approval.

| Opportunity | Problem evidence | Differentiation | Technical proof | Readiness | Adoption ease | Strategic fit | Total / 30 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Compact stable reorder plan for aligned Python sequences | 3 | 3 | 5 | 4 | 3 | 5 | **23** |
| Direct stable keyed top-k for Python records | 4 | 2 | 4 | 4 | 4 | 3 | **21** |
| Signed-int64 to unsigned-int64 eligibility expansion | 3 | 1 | 3 | 4 | 5 | 4 | **20** |
| Bounded-memory stable streaming top-k | 4 | 2 | 2 | 3 | 4 | 3 | **18** |
| Fused sorted group boundaries and counts | 4 | 2 | 1 | 2 | 3 | 4 | **16** |
| NumPy/Arrow-specific integration layer | 3 | 1 | 3 | 3 | 2 | 2 | **14** |

### Why the reorder plan ranks first

The private compact permutation already demonstrates:

- `4.51x–8.04x` construction speedups over the fixed Python stable-index
  baseline on the disordered one-million-element samples;
- 45%–47% lower measured incremental peak RSS for those constructions;
- a four-byte index payload at one million elements when 32-bit indices are
  sufficient;
- `2.14x–4.86x` faster native application than the Python-index application
  baseline;
- `4.93x–6.41x` faster complete construction plus application to three
  aligned lists in the disordered one-million-element samples, with 51%–56%
  lower measured incremental peak RSS.

Those are local synthetic results, not market proof. They are nevertheless
substantially stronger technical evidence than the marginal streaming top-k
gate. The proposed value is the complete workflow, not `argsort` alone:

> Compute one stable order and reuse it across Python sequences without a
> giant `list[int]` or a mandatory conversion to a columnar container.

## Recommended 0.3 discovery candidate

The next work should be an API and usability review, not implementation. The
smallest candidate surface is:

- one constructor whose final name is still open (`argsort`,
  `stable_permutation`, or another reviewed name);
- one immutable `Permutation` result with `len`, indexing, iteration, and a
  read-only buffer;
- one `apply(sequence)` operation returning a new list and preserving exact
  object identity;
- stable `reverse=True` and one-call-compatible `key=` semantics;
- an explicit fallback or rejection contract for unsupported key domains.

Do **not** add `apply_many`, `inverse`, `compose`, grouping, serialization, or
streaming to the first proposal. `apply_many` missed its own performance gate,
and mature columnar systems already demonstrate how quickly a permutation API
can expand. A small surface is easier to explain, validate, and maintain.

## Pre-implementation validation gates

Before changing a public module, freeze a continuation protocol that includes:

1. Three understandable aligned-sequence workflows with 2, 3, and 5
   sequences, covering duplicate-heavy IDs, event timestamps plus payloads,
   and ranking scores plus metadata.
2. Complete correctness checks for stability, object identity, key call
   count/order, immutability, mismatched lengths, exceptions, and buffer
   format.
3. End-to-end comparisons against:
   - `sorted(range(n), key=...)` plus Python list comprehensions;
   - `more_itertools.sort_together()`;
   - NumPy conversion, stable `argsort`, and conversion/application back to
     Python lists;
   - NumPy with data already resident in arrays, retained as the negative
     control BielSort is not expected to win.
4. Time and isolated peak-memory measurements at 10,000, 100,000, and one
   million records, including nearly sorted and duplicate-heavy negatives.
5. A small-input rule that avoids paying native-dispatch cost when normal
   Python sorting is already sufficient.
6. CPython 3.9–3.14 source, sanitizer, typing, documentation, and build-only
   wheel gates before any public proposal.

The exact numerical performance thresholds must be committed before the new
benchmark is executed. Existing measurements may inform those thresholds but
must not count as the new decision run.

## Stop conditions

Do not promote the candidate if any of the following occurs:

- the complete workflow is not materially better than both the direct Python
  baseline and `sort_together()` on the intended large inputs;
- end-to-end NumPy conversion is consistently better for ordinary Python
  integer lists;
- the public contract needs multiple convenience methods to be understandable;
- generic fallbacks make key calls, stability, or exceptions surprising;
- native wheel installation is more effort than the measured pipeline gain;
- independent users consistently prefer records, NumPy, or DataFrames after
  seeing the same example.

## Market and monetization conclusion

This opportunity can make BielSort a clearer and more credible open-source
project. It does not currently support a claim of broad market adoption or
direct monetization. The likely near-term value is a focused tool, technical
portfolio evidence, and a basis for real workload reports. Commercial value
would require repeated external use in a costly pipeline, support demand, or
an adjacent service; no source reviewed here establishes that yet.
