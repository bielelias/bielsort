# Keyed-int64 native-memory guard — 2026-08-04

## Decision

**Keep the guard as a private research prototype.** Its decision happens
before any user key call, its fixed overhead is negligible for the target
large-list workload, and its narrow memory name is technically honest.

Do not expose it in `bielsort` yet. The `timsort` fallback's key-domain
semantics and the final public return/diagnostic shape must be settled first.
The published 0.1 API and version remain unchanged.

## Prototype contract

The research helper now lives in the installed private module
`bielsort_native._keyed_int64_guard`. It accepts exact built-in `list` and
`tuple` inputs only and remains outside the public API:

```python
from operator import attrgetter
from bielsort_native._keyed_int64_guard import sort_by_int64_key_guarded

ordered, info = sort_by_int64_key_guarded(
    records,
    attrgetter("timestamp"),
    max_native_auxiliary_bytes=64 * 1024 * 1024,
    on_exceeded="timsort",
    return_info=True,
)
```

The exact-container restriction is deliberate in this first guard. It makes
`len(values)` reliable for preflight and avoids an unaccounted iterable
materialization before sorting.

`max_native_auxiliary_bytes` covers result-list item pointers and BielSort's
variable native buffers. It does **not** promise a total process RSS limit.

## Pre-key decision

On the current 64-bit build, the compact-Radix worst case is `32 * n` bytes.
The implementation derives the multiplier from the process pointer width.

| Records | Native worst-case estimate |
|---:|---:|
| 10,000 | 312.50 KiB |
| 100,000 | 3.05 MiB |
| 1,000,000 | 30.52 MiB |

The guard compares this value with the configured limit before calling `key`:

- if it fits, the native keyed-int64 path runs;
- `on_exceeded="raise"` raises `MemoryError` with zero key calls;
- `on_exceeded="timsort"` delegates directly to `sorted(key=...)`, which
  calls the user key once per record and remains stable.

The fallback's own allocations are outside the native estimate.

## Unresolved semantic choice

> Resolved in follow-up: the
> [adaptive generic-key selector](2026-08-04-keyed-adaptive-selector.md)
> retains a generic public direction and replays evaluated keys through
> CPython Timsort without calling user code twice.

The native path deliberately accepts only exact signed-64-bit integer keys.
Direct Timsort delegation accepts every mutually orderable Python key type.
Consequently, the accepted key domain can currently depend on the memory
decision.

That is acceptable for measuring a private prototype, but not for a public
`sort_by_int64_key` contract. Before 0.2, choose one of these explicitly:

1. keep a strict int64-only API and offer only the pre-key `raise` policy;
2. define an adaptive generic-key API whose native specialization is an
   implementation detail;
3. build a cached-key fallback that validates once, at the cost of additional
   Python memory and complexity.

The second option is currently the most compatible with existing Python
sorting behavior, but it needs a post-extraction fallback design so unsupported
keys are never evaluated twice.

## Fixed overhead

An empty-input microbenchmark ran 200,000 calls per sample across 11 rotated
samples. It isolates the Python validation and arithmetic added before the same
private C entry point:

| Operation | Median per call | Added versus direct |
|---|---:|---:|
| Direct private C function | 71.5 ns | — |
| Guard without a limit | 268.1 ns | 196.6 ns |
| Guard with a fitting limit | 295.6 ns | 224.1 ns |

The guard therefore adds about `0.20–0.22 µs` of fixed work on this machine.
It is `O(1)` and does not scan the data.

## End-to-end timing interpretation

End-to-end medians for 10,000, 100,000, and 1,000,000 records varied between
`-10.30%` and `+11.40%` relative to the direct function, with signs changing by
size and distribution. Because every fitting guard eventually calls the same
C function, apparent negative overhead cannot be a real optimization. The
spread is local scheduler/cache noise and must not become a performance claim.

The fixed-call experiment is the useful result: around 0.22 microseconds is
immaterial beside target sorts measured in milliseconds. Raw samples and
environment metadata are preserved in
[`2026-08-04-keyed-int64-guard-overhead.json`](2026-08-04-keyed-int64-guard-overhead.json).

## Validation

- The exact-limit boundary selects the native path.
- Timsort fallback preserves ordering, stability, object identity, and one
  user key call per record.
- The `raise` policy executes zero user key calls and leaves input unchanged.
- Negative/non-integer limits, invalid policies, unsized iterables, and
  container subclasses are rejected.
- The helper remains absent from the public `bielsort` namespace.

## Release gate

This research branch may be published on GitHub after its final test and
sanitizer pass, clearly marked experimental. A PyPI `0.2.0rc1` should wait for:

1. the key-domain/API choice above;
2. public documentation, type hints, and changelog;
3. wheel tests across supported CPython and operating-system targets;
4. clean-environment installation from TestPyPI;
5. no regression in the existing 0.1 API.

A final `0.2.0` should be promoted from the candidate only after those checks
pass. No arbitrary waiting period is required; the decision is evidence-based.
