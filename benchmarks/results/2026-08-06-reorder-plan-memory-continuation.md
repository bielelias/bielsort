# Reorder-plan memory continuation — 2026-08-06

## Decision

**The frozen local time and memory gates pass.**

This result evaluates a private candidate. It does not add a public
`argsort` or `Permutation`, approve a release, or establish external
market demand. Hosted portability and final API review remain separate
promotion gates.

## Complete-flow timing

Medians include construction of one order and application to every
aligned column. Higher speedup values favor BielSort.

| n | Workload | Python | Biel | `sort_together` | NumPy E2E | Biel/Python | Biel/`sort_together` | Biel/NumPy E2E |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | event-batch | 0.002145 s | 0.000569 s | 0.002583 s | 0.001989 s | 3.77x | 4.54x | 3.49x |
| 10,000 | event-batch-nearly-ordered | 0.000495 s | 0.000373 s | 0.000749 s | 0.001378 s | 1.33x | 2.01x | 3.69x |
| 10,000 | ranking-export | 0.001582 s | 0.000277 s | 0.001827 s | 0.002053 s | 5.71x | 6.59x | 7.41x |
| 10,000 | simulation-columns | 0.003003 s | 0.000600 s | 0.003366 s | 0.002905 s | 5.01x | 5.61x | 4.85x |
| 100,000 | event-batch | 0.030666 s | 0.008424 s | 0.047988 s | 0.024728 s | 3.64x | 5.70x | 2.94x |
| 100,000 | event-batch-nearly-ordered | 0.007325 s | 0.005674 s | 0.015183 s | 0.013173 s | 1.29x | 2.68x | 2.32x |
| 100,000 | ranking-export | 0.027028 s | 0.004684 s | 0.042074 s | 0.026305 s | 5.77x | 8.98x | 5.62x |
| 100,000 | simulation-columns | 0.045554 s | 0.010053 s | 0.064208 s | 0.038321 s | 4.53x | 6.39x | 3.81x |
| 1,000,000 | event-batch | 0.543257 s | 0.097622 s | 0.719269 s | 0.307609 s | 5.56x | 7.37x | 3.15x |
| 1,000,000 | event-batch-nearly-ordered | 0.077844 s | 0.080511 s | 0.198946 s | 0.144010 s | 0.97x | 2.47x | 1.79x |
| 1,000,000 | ranking-export | 0.543248 s | 0.091971 s | 0.685339 s | 0.393438 s | 5.91x | 7.45x | 4.28x |
| 1,000,000 | simulation-columns | 0.909697 s | 0.133954 s | 1.036904 s | 0.633015 s | 6.79x | 7.74x | 4.73x |

The NumPy-resident control is retained in the raw JSON. It begins
and ends with arrays and is deliberately not a BielSort gate.

## Incremental peak RSS at one million records

| Workload | Python | Biel | `sort_together` | Biel/Python | Biel/`sort_together` |
|---|---:|---:|---:|---:|---:|
| event-batch | 55.19 MiB | 22.97 MiB | 145.05 MiB | 0.42x | 0.16x |
| event-batch-nearly-ordered | 53.59 MiB | 53.20 MiB | 144.94 MiB | 0.99x | 0.37x |
| ranking-export | 67.88 MiB | 26.35 MiB | 152.55 MiB | 0.39x | 0.17x |
| simulation-columns | 83.43 MiB | 41.72 MiB | 183.25 MiB | 0.50x | 0.23x |

## Frozen gate summary

- Direct Python time gate: **pass**.
- `sort_together()` time gate: **pass**.
- End-to-end NumPy boundary: **pass**.
- Peak-memory gate: **pass**.

Thresholds were not changed after execution. Existing older
argsort results did not count toward this decision.

## Focused continuation gates

The valid earlier failed result remains preserved and is not
replaced by this continuation.

- Focused continuation: **pass**.
- Nearly ordered median RSS ratio: `0.9928x` (maximum `1.05x`).
- Same-seed RSS ratios: `0.8799x, 0.9928x, 0.9958x`; all 3 passed, while at least 2 were required.
- Nearly ordered time ratios at 100,000 and 1,000,000: `100000: 1.29x`, `1000000: 0.97x` (minimum `0.90x`).
- Compact four-byte payload: **pass**.

## Interpretation

Avoiding the eager exact-list snapshot resolved the narrow negative control
that motivated this continuation. The nearly ordered median fell from the
earlier valid `1.1205x` result to `0.9928x` direct Python, and every paired
sample passed the original `1.10x` limit. The earlier failure is retained and
is not overwritten by this result.

The same implementation preserved the intended disordered differential. At
one million records, the three disordered complete flows were `5.56x–6.79x`
faster than direct Python and used `0.39x–0.50x` its incremental peak RSS.
These remain local synthetic results rather than external workload evidence.

All memory samples stopped at the worker's `operation-complete` checkpoint;
correctness-reference construction happened afterward and was excluded from
RSS sampling.

## Reproduction

```bash
python benchmarks/reorder_plan_memory_continuation.py --canonical \
  --json-output benchmarks/results/2026-08-06-reorder-plan-memory-continuation.json \
  --markdown-output benchmarks/results/2026-08-06-reorder-plan-memory-continuation.md
```

Raw samples and rotation order: [2026-08-06-reorder-plan-memory-continuation.json](2026-08-06-reorder-plan-memory-continuation.json).

## Environment

- Commit: `9cf280474a84bfd412c7d1f309cf810472e610d5`
- Python compiler: GCC 12.2.0
- Platform: Linux-6.7.0-keepos-x86_64-with-glibc2.36
- CPU: 13th Gen Intel(R) Core(TM) i5-1334U
- NumPy: 2.4.6
- more-itertools: 11.1.0
