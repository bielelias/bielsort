# Adaptive generic-key selector v3 — 2026-08-04

## Decision

**Accept v3 as a private research checkpoint, but keep the pull request in
Draft.** The selector now waits for a 2,048-key prefix before classifying
nearly monotonic signed-int64 runs. It considers both run directions, keeps
small sparse runs with Timsort, and delegates larger sparse runs only when the
sample predicts at least five Radix passes.

This policy avoids a serious false positive discovered during the experiment:
a mostly ordered 512-key prefix with one early swap followed by random int64
data. Short 64-512-key checkpoints sent that input to Timsort and erased the
native speedup. Both the clean and noisy ordered-prefix cases now remain on
Radix at 10,000, 100,000, and 1,000,000 records.

The published BielSort API and version remain unchanged at 0.1.0.

## Selector policy

The private fused C extractor evaluates keys in input order and retains their
exact Python objects. At item 2,048 it considers Timsort replay only when:

1. the exact keys seen so far fit signed int64;
2. the prefix is sparse rather than Counting-eligible;
3. one direction change count is at most 1/32 of the sample;
4. and either the input has at most 32,768 records or the sample predicts at
   least five 11-bit Radix passes.

Otherwise extraction continues and the existing already-sorted, Counting, or
Radix path makes the final decision. Generic keys and int64 overflow continue
to use exact-object progressive replay. `reverse=True` applies the same policy
after direction normalization and preserves stable equal-key order.

## Median timing

Eleven rotated samples ran pinned to one CPU on the local Linux x86-64 machine
with CPython 3.11. Generation, correctness validation, and destruction of the
previous result stayed outside the timed region. Ratios above 1.00x favor
BielSort.

### Ascending

| Workload | 10,000 | 100,000 | 1,000,000 |
|---|---:|---:|---:|
| random int64 | 2.64x | 2.90x | 3.52x |
| nearly sorted dense int64 | 1.03x | 1.48x | 1.35x |
| nearly sorted wide int64 | 0.85x | 1.34x | 1.03x |
| nearly sorted spaced int64 | 0.81x | 0.97x | 0.95x |
| ordered prefix + random tail | 2.78x | 2.62x | 3.50x |
| noisy ordered prefix + random tail | 2.53x | 2.88x | 3.55x |

### Reverse

| Workload | 10,000 | 100,000 | 1,000,000 |
|---|---:|---:|---:|
| random int64 | 2.45x | 2.65x | 3.61x |
| nearly sorted dense int64 | 1.02x | 1.23x | 1.43x |
| nearly sorted wide int64 | 0.82x | 1.16x | 0.99x |
| nearly sorted spaced int64 | 0.84x | 0.83x | 0.98x |
| ordered prefix + random tail | 2.38x | 2.80x | 3.62x |
| noisy ordered prefix + random tail | 2.42x | 2.68x | 3.42x |

The previously reported one-million spaced-int64 result improved from 0.85x
to 0.95x ascending; the new reverse measurement was 0.98x. These are local
measurements rather than a universal guarantee. Earlier exploratory runs
varied enough to justify retaining every raw sample and avoiding finer-grained
heuristics.

## Peak memory

Three isolated one-million-record RSS samples measured:

| Workload | `sorted(key=...)` | Adaptive BielSort | Ratio |
|---|---:|---:|---:|
| random int64 | 24.85 MiB | 30.46 MiB | 1.23x |
| nearly sorted wide int64 | 25.76 MiB | 21.98 MiB | 0.85x |
| nearly sorted spaced int64 | 22.97 MiB | 30.60 MiB | 1.33x |
| noisy ordered prefix + random tail | 23.89 MiB | 30.45 MiB | 1.27x |

The wide case falls back after the sample and therefore uses less measured
incremental RSS. The spaced and random-tail cases remain native. These are
operating-system peak-RSS observations, not exact allocation bounds.

## Validation

- 90 tests pass in the optimized local build.
- A clean sdist produced a normal wheel whose 90 tests passed outside the
  repository using only the installed package.
- The same clean sdist produced an ASan/UBSan wheel whose 90 tests passed with
  both sanitizers enabled.
- The C extension compiles with `-Wall -Wextra -Werror`.
- New tests cover both monotonic directions, `reverse=True`, the 2,048-key
  decision boundary, regularly spaced native retention, and clean/noisy
  ordered prefixes with random tails.

Raw samples:

- [`2026-08-04-keyed-adaptive-selector-v3-ascending.json`](2026-08-04-keyed-adaptive-selector-v3-ascending.json)
- [`2026-08-04-keyed-adaptive-selector-v3-reverse.json`](2026-08-04-keyed-adaptive-selector-v3-reverse.json)
- [`2026-08-04-keyed-adaptive-selector-v3-memory.json`](2026-08-04-keyed-adaptive-selector-v3-memory.json)

## Remaining limitations

The v3 selector does not make BielSort universally faster. Wide and spaced
nearly ordered inputs at 10,000 records remain roughly 15%-19% slower, and the
100,000-record reverse spaced case measured 17% slower. Pre-key selection
cannot observe an arbitrary Python `key` distribution, while post-key Timsort
replay has a measurable per-item cost. Finer synthetic thresholds fluctuated
across runs and were rejected to avoid overfitting one machine.

Before a public 0.2 candidate, the project still needs an explicit acceptance
decision for those bounded losses, a public API and typing contract, final
diagnostics and user documentation, and a fresh supported-platform wheel
matrix. Nothing in this checkpoint was merged or published.
