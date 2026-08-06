# Private promotion review: stable `top_k`

!!! warning "No public API yet"

    This review promotes direct keyed top-k from algorithm research to an API
    implementation candidate. It does **not** add `bielsort.top_k`, change the
    package version, approve a merge, or approve a release.

## Decision

The private adaptive core has enough evidence to continue. It has passed the
fixed correctness, common-callable, and isolated-memory gates for large Python
record collections with small `k`. The proposed public contract is coherent,
but public exposure remains blocked by the implementation gates at the end of
this page.

| Area | Review decision |
|---|---|
| Canonical name | `top_k` |
| Result | new, fully ordered `list` of original records |
| Direction | `largest=False`; no `reverse` alias |
| Key | optional `key=None`, evaluated once per encountered record when present |
| Ties | stable encounter order for smallest and largest results |
| Diagnostics | separate `top_k_with_info()` and immutable `TopKInfo` |
| Memory guard | only on the structured diagnostic API |
| Generic fallback | Python `heapq` for small `k`; full stable sort when `k` is large |
| Status | conditional implementation candidate; still private |

## Proposed public shape

```python
def top_k(
    iterable,
    k,
    *,
    key=None,
    largest=False,
): ...


def top_k_with_info(
    iterable,
    k,
    *,
    key=None,
    largest=False,
    max_native_auxiliary_bytes=None,
    on_memory_limit="heapq",
): ...
```

`top_k` is the Python spelling users are most likely to discover and read.
`topk` is rejected as a second alias because two spellings would enlarge a
new API without adding capability. `nsmallest` and `nlargest` are rejected
because one function with `largest=` keeps the surface small. `reverse=` is
rejected because this operation selects a subset; `largest=` says which subset
is requested more directly.

There is no proposed `top_k_with_strategy()`. Human-readable strategy strings
are useful for private experiments but are a fragile programmatic contract.
One structured diagnostic API is sufficient.

## Compatibility contract

An eventual public implementation must satisfy all of these rules:

- accept any iterable and consume it at most once;
- accept a non-negative integer index for `k`, reject `bool`, and reject
  negative values with `ValueError`;
- return `[]` for `k == 0` without consuming the iterable or evaluating
  `key`;
- clamp `k` to the number of encountered records;
- return at most `k` original objects in fully sorted order;
- preserve encounter order for equal keys in both directions;
- evaluate an explicit `key` exactly once per encountered record;
- use natural ordering when `key is None` without an artificial Python
  identity-function call;
- compare generic keys with `<` and never compare records to break ties;
- propagate iteration, key, and comparison exceptions;
- leave reusable inputs unchanged during supported use;
- never crash if user code changes an input list's size during key evaluation
  or comparison; the reviewed private core raises `RuntimeError` instead.

Ordering equivalence applies to keys whose `<` relation is a consistent strict
weak ordering. Mutating the source collection from `key` or a comparison
method is unsupported; the runtime check is a safety boundary, not a promise
to define a useful result for a changing input.

## Structured diagnostics

`TopKInfo` should be a separate frozen dataclass rather than overloading
`SortInfo`: selection has a requested size, an effective selected size, and a
heap/full-sort decision that ordinary sorting does not have.

| Field | Intended meaning |
|---|---|
| `algorithm` | normalized `native-int64`, `native-generic`, `heapq`, `timsort`, or `trivial` |
| `reason` | human-readable explanation; wording is not for control flow |
| `size` | number of encountered records |
| `requested_k` | validated requested selection size |
| `selected` | `min(requested_k, size)` |
| `largest` | whether the largest records were requested |
| `key_domain` | normalized `natural`, `signed-int64`, or `python` |
| `estimated_native_auxiliary_bytes` | estimate for the selected native path, when used |
| `worst_case_native_auxiliary_bytes` | conservative native planning bound |
| `max_native_auxiliary_bytes` | requested limit or `None` |
| `native_memory_limit_exceeded` | whether the limit forced a fallback |
| `used_native` | derived property for a committed native path |

Normalized algorithm values become compatibility surface once published.
Private Portuguese strategy sentences must therefore not leak into
`TopKInfo.algorithm` or application control flow.

## Memory guard

The simple `top_k()` API remains simple. The optional guard belongs to
`top_k_with_info()`, matching the existing separation between `sort()` and
`sort_with_info()`.

When `max_native_auxiliary_bytes` is provided:

1. the input must be an exact built-in `list` or `tuple`;
2. the conservative decision occurs before iteration and before `key`;
3. `on_memory_limit="heapq"` delegates without a repeated key call;
4. `on_memory_limit="raise"` raises `MemoryError` at the same checkpoint.

The estimate covers variable native selection and final-merge buffers. It
does not claim to measure input objects, returned-list references, Python key
payloads, allocator overhead, or total process RSS.

## Strategy and fallbacks

The current native heap is intended for large Python-native collections where
`k` is small relative to `n`. A public selector must not force that path for
every input:

```text
k == 0                     -> trivial empty result
small k + explicit key     -> adaptive native stable heap
small k + natural int64    -> compact native int64 selection and application
small k + other natural    -> heapq fallback
large k                    -> full stable sort, then slice
native memory limit hit    -> heapq policy or MemoryError
```

The exact crossover between a heap and a full sort is deliberately not frozen
here. It must be benchmarked across supported platforms and should remain an
internal heuristic. Correct results and diagnostic categories are API;
thresholds are not.

One-shot iterables may be materialized once when a length is required for the
strategy decision. `k == 0` remains the exception and must not consume them.

## Evidence supporting continuation

The versioned practical gate used one million named-tuple records, four common
`itemgetter`/`attrgetter`/`lambda` callables, three `k` values, and both
directions. Twenty-two of 24 cases reached at least `1.10x` over `heapq`, none
fell below `0.90x`, and every key-call probe passed. In isolated measurements,
the adaptive core used `0.28x–0.43x` the traced peak memory of `heapq` across
the fixed exact-int64 and arbitrary-size-integer cases.

These are synthetic results from one development host, not universal speed
guarantees. See the
[complete practical report](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-practical.md)
and the earlier pass/failure history in the
[research proposal](keyed-topk-research.md).

The callback-safety change was then measured with the exact same canonical
shape. Its [separate revalidation report](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-practical-safety.md)
also passed: 19 of 24 callable cases reached `1.10x`, none fell below `0.90x`,
and traced peak memory remained at `0.28x–0.43x` of `heapq`.

## Safety finding from this review

The review tested adversarial user callbacks in addition to the benchmarked
normal path. The previous native loop held a borrowed list item while calling
arbitrary Python code. A `key` that cleared the same input list could therefore
cause an out-of-bounds access and process crash.

The private candidate now owns the current item across the callback, checks
the source length after key evaluation and before later unchecked access, and
also checks after generic comparisons. Dedicated regression tests require a
safe `RuntimeError` for size changes caused by either `key` or `__lt__`.
Sanitizer and cross-platform validation are mandatory for this native change.

## Remaining promotion gates

Public exposure remains blocked until the unchecked items below pass:

- [x] implement one private façade supporting both `key=None` and explicit
  keys;
- [x] benchmark and select a safe large-`k` full-sort crossover;
- [x] replace private strategy strings with structured internal diagnostics
  and construct the proposed `TopKInfo` without exporting it;
- [x] preserve the passing callback-safety performance and isolated-memory
  revalidation as the reviewed implementation baseline;
- [ ] re-pass the supported source-build CI, hosted ASan/UBSan, strict docs,
  and a non-publishing wheel matrix on the unified-façade commit;
- [ ] add the complete public runtime, type-stub, documentation, and
  compatibility tests only in a later, explicitly approved API branch.

The hardened source and performance record passed
[source-build CI](https://github.com/bielelias/bielsort/actions/runs/31060360543),
[ASan/UBSan](https://github.com/bielelias/bielsort/actions/runs/31060360542),
[strict hosted documentation](https://github.com/bielelias/bielsort/actions/runs/31060360581),
and the
[non-publishing wheel matrix](https://github.com/bielelias/bielsort/actions/runs/31060438846).
The wheel run built and tested commit `f7565bd` on Linux, Windows, macOS Intel,
and macOS Apple Silicon; all publication jobs were skipped.

Passing the build-only matrix validates portability of the private candidate.
It does not by itself authorize `top_k`, version `0.3.0`, a tag, TestPyPI, or
PyPI.
