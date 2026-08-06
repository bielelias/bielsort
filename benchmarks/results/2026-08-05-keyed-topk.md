# Direct stable keyed top-k: 2026-08-05

## Decision

**The pre-registered stage-one gate passed.** This authorizes continued
private engineering of a compatible fallback and API review. It does not add
a public `top_k` function, approve a version bump, or justify a release.

For the 24 canonical one-million-record cases:

- every result matched stable full sorting by exact object identity;
- the key-call contract passed;
- 18 of 24 cases reached at least `1.25x` over `heapq`, exactly meeting the
  fixed threshold;
- no case was more than 10% slower than `heapq`;
- the eligible selection uses a native `O(k)` heap and no `O(n)` key array for
  reusable list or tuple inputs.

The thresholds were committed before implementation and were not changed
after observing the measurements.

## Method

The benchmark uses reusable lists of distinct one-element tuple records. The
tuple's first field is an exact signed-int64 key and is read with
`operator.itemgetter(0)`. Record construction is outside the timed region.

It compares:

1. private native direct keyed top-k;
2. `heapq.nsmallest()` or `heapq.nlargest()`;
3. full stable `sorted(..., key=..., reverse=...)[:k]` for context.

The canonical shape contains four disordered distributions, `k` values 10,
100, and 1,000, both directions, and seven rotated samples per algorithm. All
results are checked by identity against stable full sorting. The raw JSON
retains every sample, configuration value, gate result, and environment:
[2026-08-05-keyed-topk.json](2026-08-05-keyed-topk.json).

## One-million-record results

Higher speedup is better. Times are medians.

| Distribution | k | Direction | `heapq` | Biel direct | vs `heapq` |
|---|---:|---|---:|---:|---:|
| dense | 10 | smallest | 0.02207 s | 0.01286 s | 1.72x |
| dense | 10 | largest | 0.02159 s | 0.01262 s | 1.71x |
| dense | 100 | smallest | 0.02258 s | 0.01270 s | 1.78x |
| dense | 100 | largest | 0.02216 s | 0.01267 s | 1.75x |
| dense | 1,000 | smallest | 0.02555 s | 0.01335 s | 1.91x |
| dense | 1,000 | largest | 0.02487 s | 0.01362 s | 1.83x |
| int32 | 10 | smallest | 0.02784 s | 0.01978 s | 1.41x |
| int32 | 10 | largest | 0.02687 s | 0.01992 s | 1.35x |
| int32 | 100 | smallest | 0.02817 s | 0.02003 s | 1.41x |
| int32 | 100 | largest | 0.02730 s | 0.01975 s | 1.38x |
| int32 | 1,000 | smallest | 0.03160 s | 0.02066 s | 1.53x |
| int32 | 1,000 | largest | 0.03080 s | 0.02064 s | 1.49x |
| int64 | 10 | smallest | 0.03095 s | 0.02765 s | 1.12x |
| int64 | 10 | largest | 0.02989 s | 0.02745 s | 1.09x |
| int64 | 100 | smallest | 0.03097 s | 0.02743 s | 1.13x |
| int64 | 100 | largest | 0.03049 s | 0.02771 s | 1.10x |
| int64 | 1,000 | smallest | 0.03437 s | 0.02833 s | 1.21x |
| int64 | 1,000 | largest | 0.03315 s | 0.02816 s | 1.18x |
| heavy duplicates | 10 | smallest | 0.02190 s | 0.01269 s | 1.72x |
| heavy duplicates | 10 | largest | 0.02188 s | 0.01292 s | 1.69x |
| heavy duplicates | 100 | smallest | 0.02238 s | 0.01274 s | 1.76x |
| heavy duplicates | 100 | largest | 0.02198 s | 0.01275 s | 1.72x |
| heavy duplicates | 1,000 | smallest | 0.02403 s | 0.01330 s | 1.81x |
| heavy duplicates | 1,000 | largest | 0.02354 s | 0.01336 s | 1.76x |

The native path was `10.19x–21.53x` faster than fully sorting the same records,
but full sorting is not the primary comparator for small `k`.

## Interpretation and limits

The result supports a practical niche: selecting a small, stable, fully
ordered set of Python records by an integer field without constructing Python
heap decoration tuples or a separate key list. It is more direct than the
reusable-permutation prototype.

The six full-range int64 cases did not reach `1.25x`; their range was
`1.09x–1.21x`. They still remained within the fixed no-regression bound. This
shows that Python integer magnitude and key-extraction cost materially affect
the advantage.

The experiment has important limits:

- one local Linux machine and CPython build;
- one-element tuple records and `operator.itemgetter(0)`;
- exact signed-int64 keys only;
- no compatible generic-key fallback or public memory guard yet;
- no evidence that native-array, DataFrame, or database workloads should move
  into Python lists.

Common `lambda` and `attrgetter` keys, isolated memory behavior, compatible
fallback, and cross-platform builds remain separate gates.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These measurements describe one machine and are not universal guarantees.
