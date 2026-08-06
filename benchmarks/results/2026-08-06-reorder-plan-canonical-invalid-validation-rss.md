# Invalid reorder-plan attempt: validation overlapped RSS — 2026-08-06

## Decision

**This attempt is invalid and cannot pass or fail the frozen protocol.** The
time matrix completed normally, but the parent kept sampling memory after the
measured operation while the worker built a million-item Python reference
order for correctness validation.

That validation allocation is outside every timed algorithm and must not be
included in complete-flow peak RSS. The raw JSON and time evidence are
preserved, but the reported memory ratios and combined `FAIL` are void. No
threshold, workload, or algorithm is changed in response.

## Frozen correction

The worker now emits an `operation-complete` checkpoint while its real result
is still alive, then waits. The parent records the final RSS and stops
sampling before signaling the worker to perform validation. The correction,
this invalid artifact, and a regression test must be committed before another
decision run.

## Complete-flow timing

Medians include construction of one order and application to every
aligned column. Higher speedup values favor BielSort.

| n | Workload | Python | Biel | `sort_together` | NumPy E2E | Biel/Python | Biel/`sort_together` | Biel/NumPy E2E |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | event-batch | 0.002236 s | 0.000700 s | 0.002481 s | 0.002009 s | 3.19x | 3.54x | 2.87x |
| 10,000 | event-batch-nearly-ordered | 0.000537 s | 0.000413 s | 0.000767 s | 0.001301 s | 1.30x | 1.86x | 3.15x |
| 10,000 | ranking-export | 0.001568 s | 0.000277 s | 0.001869 s | 0.001915 s | 5.65x | 6.74x | 6.90x |
| 10,000 | simulation-columns | 0.002995 s | 0.000618 s | 0.003345 s | 0.002929 s | 4.85x | 5.41x | 4.74x |
| 100,000 | event-batch | 0.031427 s | 0.009531 s | 0.042645 s | 0.023555 s | 3.30x | 4.47x | 2.47x |
| 100,000 | event-batch-nearly-ordered | 0.006876 s | 0.006248 s | 0.016105 s | 0.013341 s | 1.10x | 2.58x | 2.14x |
| 100,000 | ranking-export | 0.025853 s | 0.005103 s | 0.037338 s | 0.025870 s | 5.07x | 7.32x | 5.07x |
| 100,000 | simulation-columns | 0.047619 s | 0.009923 s | 0.060705 s | 0.037368 s | 4.80x | 6.12x | 3.77x |
| 1,000,000 | event-batch | 0.525070 s | 0.107760 s | 0.658960 s | 0.304287 s | 4.87x | 6.12x | 2.82x |
| 1,000,000 | event-batch-nearly-ordered | 0.084170 s | 0.082392 s | 0.182893 s | 0.140390 s | 1.02x | 2.22x | 1.70x |
| 1,000,000 | ranking-export | 0.487042 s | 0.085130 s | 0.606759 s | 0.352848 s | 5.72x | 7.13x | 4.14x |
| 1,000,000 | simulation-columns | 0.795555 s | 0.132864 s | 0.888105 s | 0.506198 s | 5.99x | 6.68x | 3.81x |

The NumPy-resident control is retained in the raw JSON. It begins
and ends with arrays and is deliberately not a BielSort gate.

## Contaminated RSS at one million records — do not use

| Workload | Python | Biel | `sort_together` | Biel/Python | Biel/`sort_together` |
|---|---:|---:|---:|---:|---:|
| event-batch | 107.39 MiB | 95.28 MiB | 145.06 MiB | 0.89x | 0.66x |
| event-batch-nearly-ordered | 107.57 MiB | 95.27 MiB | 145.09 MiB | 0.89x | 0.66x |
| ranking-export | 115.55 MiB | 102.96 MiB | 152.67 MiB | 0.89x | 0.67x |
| simulation-columns | 131.39 MiB | 118.05 MiB | 183.30 MiB | 0.90x | 0.64x |

## Frozen gate summary

- Direct Python time gate: **pass**.
- `sort_together()` time gate: **pass**.
- End-to-end NumPy boundary: **pass**.
- Peak-memory gate: **invalid; validation was sampled**.

The timing thresholds passed, but the complete decision remains unavailable.

## Reproduction

```bash
python benchmarks/reorder_plan_candidate.py --canonical \
  --json-output benchmarks/results/2026-08-06-reorder-plan-canonical-invalid-validation-rss.json \
  --markdown-output benchmarks/results/2026-08-06-reorder-plan-canonical-invalid-validation-rss.md
```

Raw samples and rotation order:
[2026-08-06-reorder-plan-canonical-invalid-validation-rss.json](2026-08-06-reorder-plan-canonical-invalid-validation-rss.json).

## Environment

- Commit: `35d6aee0e75b49ebb094f223874a1816be41b0a9`
- Python compiler: GCC 12.2.0
- Platform: Linux-6.7.0-keepos-x86_64-with-glibc2.36
- CPU: 13th Gen Intel(R) Core(TM) i5-1334U
- NumPy: 2.4.6
- more-itertools: 11.1.0
