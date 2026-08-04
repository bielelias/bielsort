# Candidate public `sort(key=...)` API — 2026-08-04

## Decision

**Accept adaptive signed-int64 keys for the new-list public API and reject the
same change for the in-place API in this candidate.** No new function or
parameter is required:

```python
bielsort.sort(records, key=extract_key, reverse=False)
```

The existing call now reaches stable native Counting or Radix when every key
result is an exact signed-int64 integer and the selector considers the input a
good fit. Small, generic, overflow, and nearly monotonic cases retain Timsort
behavior through exact-object replay. The key callable is evaluated exactly
once per record in input order.

`sort_in_place(..., key=...)` remains a direct `list.sort()` delegation. An
exploratory adaptive implementation materially accelerated integer-key cases,
but its compatibility-preserving private copy made generic string keys as much
as 17% slower in the sampled matrix. Shipping that regression silently was
rejected.

This is unreleased 0.2 research. The package metadata remains 0.1.0, and no
wheel, tag, merge, or PyPI publication is part of this checkpoint.

## Public contract

- The four canonical function names and signatures are unchanged.
- `sort(..., key=callable)` may use Counting, Radix, or Timsort.
- `sort(..., key=callable, reverse=True)` supports the same adaptive paths and
  preserves stable equal-key order.
- `sort(..., reverse=True)` without a key remains on Timsort.
- Both in-place functions continue to use `list.sort()` whenever `key` is not
  `None` or `reverse` is true.
- Diagnostic text exposes the chosen family but remains non-contractual.
- The adaptive implementation is internal and is not added to `__all__`.

## Median timing

Eleven rotated samples ran pinned to one CPU on Linux x86-64 with CPython
3.11. Both algorithms received the same live record list and `operator.attrgetter`
key. Ratios above 1.00x favor BielSort.

### Ascending

| Key distribution | 10,000 | 100,000 | 1,000,000 |
|---|---:|---:|---:|
| dense int64 | 3.36x | 4.10x | 5.09x |
| random int64 | 2.37x | 2.93x | 3.67x |
| string fallback | 1.03x | 0.99x | 1.00x |

### Reverse

| Key distribution | 10,000 | 100,000 | 1,000,000 |
|---|---:|---:|---:|
| dense int64 | 3.91x | 4.14x | 5.13x |
| random int64 | 2.42x | 2.68x | 3.53x |
| string fallback | 1.04x | 0.98x | 0.98x |

The candidate therefore retains material speedups for its intended integer
domain while keeping the measured generic fallback within 2% of `sorted()` in
all but one result, which favored BielSort by 4%. These measurements are local
evidence, not universal guarantees.

Raw reports:

- [`2026-08-04-keyed-public-api-ascending.json`](2026-08-04-keyed-public-api-ascending.json)
- [`2026-08-04-keyed-public-api-reverse.json`](2026-08-04-keyed-public-api-reverse.json)

## Correctness and compatibility coverage

The public integration tests require:

- one key call per record in encounter order;
- new-list behavior that leaves the source unchanged;
- stable equal-key object order through native Counting and reverse Counting;
- parity with `sorted()` for generic keys and truthy `reverse` values;
- no new public exports or function signatures;
- direct Timsort semantics for in-place key calls, including an empty list
  during key evaluation, mutation detection, identity preservation, and
  restoration after a key exception.

The private selector's existing differential, exact-identity, reference,
memory-guard, GC, exception, Counting, Radix, ordered-run, and reverse tests
continue to apply beneath the public wrapper. The complete local suite has 96
passing tests.

The English and Portuguese user documentation now distinguishes the published
0.1 behavior from this unreleased 0.2 candidate. It renders successfully with
MkDocs in strict mode.

A clean source distribution produced both a normal wheel and a freshly
compiled ASan/UBSan wheel. Each installed wheel passed the full 96-test suite
outside the source tree; the instrumented run reported no sanitizer failures.

## Remaining gates

Before `0.2.0rc1`, the candidate still needs the full CPython 3.9-3.14
Linux/Windows/macOS matrix. The bounded nearly ordered losses documented in the
selector v3 report also remain part of the release decision.
