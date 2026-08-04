# Adaptive generic-key selector — 2026-08-04

> Superseded by the
> [progressive selector v2](2026-08-04-keyed-adaptive-selector-v2.md).

## Decision

**Continue with the generic API direction, but keep it private.** The selector
now preserves `sorted(key=...)` semantics for general key domains, calls user
code exactly once per record, retains substantial int64 acceleration, and
avoids a material generic-fallback memory penalty.

It is not ready for a 0.2 release candidate. Medium nearly-sorted int64 inputs
remain a measured regression, and the cached-key replay must be validated on
every supported CPython version before becoming package behavior.

The public 0.1 API and version remain unchanged.

## Selected product direction

The eventual API does not need a separate int64-only public function. Existing
`bielsort.sort(records, key=...)` can remain generic while treating native
int64 acceleration as an implementation detail.

The private research selector currently follows this sequence:

1. Materialize a private output list.
2. Send fewer than 2,048 records directly to Timsort.
3. Evaluate the first 64 keys in input order.
4. If the prefix is not exact signed int64, give CPython Timsort a one-shot C
   callable that replays those 64 keys and evaluates every remaining key once.
5. If the prefix is int64, cache the remaining keys and attempt native stable
   Counting/Radix sorting.
6. If an incompatible key appears late, replay the complete cache through
   Timsort without evaluating the user callable again.

The selector supports any iterable when no memory limit is configured. A
pre-key `max_native_auxiliary_bytes` decision requires an exact built-in list
or tuple, making its size trustworthy before user code runs.

## Why replay is needed

Calling `sorted(items, key=user_key)` after an attempted native extraction
would evaluate `user_key` twice. Decorating Python indices preserved the
one-call contract but made generic sorting 33%-54% slower in the first
experiment.

The retained solution uses CPython's real Timsort with a private one-shot C
callable. That callable returns already evaluated prefix/cache keys and calls
the user function only for unevaluated positions. It therefore preserves:

- one user key call per input occurrence;
- input-order key evaluation;
- stable ordering for equal keys;
- normal Timsort key comparison behavior, including key objects that implement
  `<` but not equality;
- input and object identity preservation.

This relies on CPython listsort extracting keys in input order; the callable
does not independently reconstruct or validate occurrence order. BielSort is a
CPython extension, but this implementation dependency must be regression-tested
on CPython 3.9 through 3.14 rather than assumed universally.

## Median time

Seven rotated samples ran locally on Linux x86-64 with CPython 3.11. Speedups
above `1.00x` favor BielSort.

| Records | Key distribution | Selected path | `sorted(key=...)` | Adaptive BielSort | Speedup |
|---:|---|---|---:|---:|---:|
| 10,000 | random int64 | Radix | 0.001743 s | 0.000732 s | 2.38x |
| 10,000 | nearly sorted int64 | Radix | 0.000211 s | 0.000318 s | 0.66x |
| 10,000 | string | prefix replay + Timsort | 0.001735 s | 0.001816 s | 0.96x |
| 10,000 | huge integer | prefix replay + Timsort | 0.001610 s | 0.001652 s | 0.97x |
| 100,000 | random int64 | Radix | 0.024234 s | 0.009164 s | 2.64x |
| 100,000 | nearly sorted int64 | Radix | 0.004207 s | 0.005449 s | 0.77x |
| 100,000 | string | prefix replay + Timsort | 0.025662 s | 0.025233 s | 1.02x |
| 100,000 | huge integer | prefix replay + Timsort | 0.022556 s | 0.023053 s | 0.98x |
| 1,000,000 | random int64 | Radix | 0.364277 s | 0.104628 s | 3.48x |
| 1,000,000 | nearly sorted int64 | Counting | 0.056920 s | 0.049158 s | 1.16x |
| 1,000,000 | string | prefix replay + Timsort | 0.380673 s | 0.378963 s | 1.00x |
| 1,000,000 | huge integer | prefix replay + Timsort | 0.337817 s | 0.341308 s | 0.99x |

The generic results are effectively parity on this machine. The 10,000 and
100,000 nearly-sorted int64 results are real release blockers: adaptive
BielSort took about 51% and 30% longer, respectively. The one-million proxy
won locally, but that does not erase the medium-size regressions.

Raw timing samples and environment metadata are preserved in
[`2026-08-04-keyed-adaptive-benchmark.json`](2026-08-04-keyed-adaptive-benchmark.json).

## Median incremental peak RSS at one million records

Three isolated subprocesses ran per algorithm and distribution.

| Key distribution | `sorted(key=...)` | Adaptive BielSort | Ratio |
|---|---:|---:|---:|
| random int64 | 24.80 MiB | 30.64 MiB | 1.24x |
| nearly sorted int64 | 23.06 MiB | 26.73 MiB | 1.16x |
| string | 23.45 MiB | 23.42 MiB | 1.00x |
| huge integer | 24.86 MiB | 24.92 MiB | 1.00x |

Prefix replay removed the earlier full-cache penalty for homogeneous generic
keys. Native int64 speed still trades 16%-24% more incremental peak RSS than
Timsort on this machine; `max_native_auxiliary_bytes` makes that trade explicit.

Raw memory samples are preserved in
[`2026-08-04-keyed-adaptive-memory.json`](2026-08-04-keyed-adaptive-memory.json).

## Correctness coverage

- exact int64, string, huge integer, and `<`-only custom keys;
- empty, single-item, stable duplicate, generator, and randomized inputs;
- an incompatible key appearing after the 64-item prefix;
- key exceptions without input mutation;
- exact native-memory boundary, pre-key Timsort, and pre-key `MemoryError`;
- cached native ownership: eligible caches are consumed, ineligible caches are
  preserved for fallback;
- no public `bielsort` symbol was added.

The complete suite passed all 64 tests in both the regular build and the
ASan/UBSan instrumented build. A separate wheel build also passed with
`-Wall -Wextra -Werror`, with no compiler warnings.

## Remaining 0.2 gates

1. Move the selector from `benchmarks/` into a private installed module.
2. Improve medium nearly-sorted int64 selection without weakening the one-key-
   call contract or tuning to only one synthetic generator.
3. Add `reverse=True` with Python-compatible stable behavior.
4. Validate cached replay, exception paths, and wheels on CPython 3.9-3.14,
   Linux, Windows, and macOS.
5. Finalize public diagnostics, type hints, changelog, and documentation.
6. Publish `0.2.0rc1` to TestPyPI only after every gate above passes.

This is strong engineering evidence for the second option. It is not yet a
claim of universal speed, external demand, or release readiness.

## Reproduction

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m benchmarks.keyed_adaptive_benchmark \
  --repetitions 7 \
  --output benchmarks/results/2026-08-04-keyed-adaptive-benchmark.json
python -m benchmarks.keyed_adaptive_memory \
  --repetitions 3 \
  --output benchmarks/results/2026-08-04-keyed-adaptive-memory.json
```
