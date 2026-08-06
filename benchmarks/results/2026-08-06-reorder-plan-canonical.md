# Reusable reorder-plan canonical result — 2026-08-06

## Decision

**The frozen local time and memory gates do not pass.**

This result evaluates a private candidate. It does not add a public
`argsort` or `Permutation`, approve a release, or establish external
market demand. Hosted portability and final API review remain separate
promotion gates.

## Complete-flow timing

Medians include construction of one order and application to every
aligned column. Higher speedup values favor BielSort.

| n | Workload | Python | Biel | `sort_together` | NumPy E2E | Biel/Python | Biel/`sort_together` | Biel/NumPy E2E |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | event-batch | 0.002159 s | 0.000629 s | 0.002446 s | 0.001954 s | 3.43x | 3.89x | 3.11x |
| 10,000 | event-batch-nearly-ordered | 0.000530 s | 0.000425 s | 0.000774 s | 0.001342 s | 1.25x | 1.82x | 3.16x |
| 10,000 | ranking-export | 0.001584 s | 0.000287 s | 0.001778 s | 0.001991 s | 5.52x | 6.20x | 6.94x |
| 10,000 | simulation-columns | 0.003003 s | 0.000685 s | 0.003331 s | 0.002824 s | 4.39x | 4.86x | 4.12x |
| 100,000 | event-batch | 0.031270 s | 0.009120 s | 0.043471 s | 0.023019 s | 3.43x | 4.77x | 2.52x |
| 100,000 | event-batch-nearly-ordered | 0.006513 s | 0.005996 s | 0.016570 s | 0.013083 s | 1.09x | 2.76x | 2.18x |
| 100,000 | ranking-export | 0.026357 s | 0.004483 s | 0.036565 s | 0.023794 s | 5.88x | 8.16x | 5.31x |
| 100,000 | simulation-columns | 0.043400 s | 0.009238 s | 0.060860 s | 0.040305 s | 4.70x | 6.59x | 4.36x |
| 1,000,000 | event-batch | 0.520142 s | 0.107738 s | 0.670779 s | 0.294787 s | 4.83x | 6.23x | 2.74x |
| 1,000,000 | event-batch-nearly-ordered | 0.077999 s | 0.084030 s | 0.179369 s | 0.133952 s | 0.93x | 2.13x | 1.59x |
| 1,000,000 | ranking-export | 0.486627 s | 0.082800 s | 0.589847 s | 0.355154 s | 5.88x | 7.12x | 4.29x |
| 1,000,000 | simulation-columns | 0.775376 s | 0.133474 s | 0.873997 s | 0.501843 s | 5.81x | 6.55x | 3.76x |

The NumPy-resident control is retained in the raw JSON. It begins
and ends with arrays and is deliberately not a BielSort gate.

## Incremental peak RSS at one million records

| Workload | Python | Biel | `sort_together` | Biel/Python | Biel/`sort_together` |
|---|---:|---:|---:|---:|---:|
| event-batch | 55.19 MiB | 30.50 MiB | 144.98 MiB | 0.55x | 0.21x |
| event-batch-nearly-ordered | 54.28 MiB | 60.82 MiB | 144.97 MiB | 1.12x | 0.42x |
| ranking-export | 69.20 MiB | 30.58 MiB | 152.82 MiB | 0.44x | 0.20x |
| simulation-columns | 85.24 MiB | 41.64 MiB | 183.30 MiB | 0.49x | 0.23x |

## Frozen gate summary

- Direct Python time gate: **pass**.
- `sort_together()` time gate: **pass**.
- End-to-end NumPy boundary: **pass**.
- Peak-memory gate: **fail**.

Thresholds were not changed after execution. Existing older
argsort results did not count toward this decision.

## Interpretation

The candidate demonstrated a strong differential in its intended disordered
Python-list workflows: at one million records it was `4.83x–5.88x` faster
than direct Python and used only `0.44x–0.55x` its incremental peak RSS. It
also stayed inside the frozen nearly ordered time floor at `0.93x`.

The decision is still **fail**, not a rounded pass. The nearly ordered memory
control used `1.1205x` direct Python's incremental peak RSS, exceeding the
`1.10x` ceiling. A likely investigation target is the simultaneous lifetime
of the input snapshot, Python fallback indices, and packed compact result,
but that is a hypothesis rather than a conclusion from this benchmark. Any
implementation change requires a separate pre-registered continuation and
must retain this result.

All memory samples stopped at the worker's `operation-complete` checkpoint;
correctness-reference construction happened afterward and was excluded from
RSS sampling.

## Reproduction

```bash
python benchmarks/reorder_plan_candidate.py --canonical \
  --json-output benchmarks/results/2026-08-06-reorder-plan-canonical.json \
  --markdown-output benchmarks/results/2026-08-06-reorder-plan-canonical.md
```

Raw samples and rotation order: [2026-08-06-reorder-plan-canonical.json](2026-08-06-reorder-plan-canonical.json).

## Environment

- Commit: `8886573bb12ae74d62195355a1d9506752adfaec`
- Python compiler: GCC 12.2.0
- Platform: Linux-6.7.0-keepos-x86_64-with-glibc2.36
- CPU: 13th Gen Intel(R) Core(TM) i5-1334U
- NumPy: 2.4.6
- more-itertools: 11.1.0
