# Adaptive keyed top-k complete block protocol: 2026-08-05

## Decision

**The separately pre-registered complete block-timed gate passed.** All 48
canonical cases were present and identity-equivalent to stable full sorting.
Nineteen of 24 exact-int64 cases reached at least `1.20x` over `heapq`, versus
the required 18. No exact case fell below the fixed `0.87x` floor against the
frozen strict core, and no generic case fell below `0.87x` against `heapq`.

This is a new decision under a method committed before execution. It does not
erase the first failed stage-two result. Passing authorizes the planned
private callable-shape and isolated-memory experiments; it does not approve a
public `top_k`, version bump, tag, or release.

## Provenance and method

The complete protocol was fixed in commit `7fc9609`, the benchmark was
implemented and pushed in commit `669e754`, and the measured adaptive
selection code remained unchanged from commit `fdc9bb5`. The earlier failed
gate and its confirmation remain separately versioned.

The exact section uses one million tuple records and 24 combinations of four
int64 distributions, three `k` values, and two directions. It compares
`heapq`, the frozen strict-int64 core, and the adaptive core. The generic
section uses 100,000 records and 24 combinations of four key domains, the same
`k` values, and both directions. It compares `heapq` and the adaptive core.

Each algorithm receives one untimed warm-up. Every case then retains 11
rotated blocks of three complete calls. The decision statistic is the median
of comparator/adaptive ratios paired within each block. Record construction,
stable reference sorting, and garbage collection remain outside timing;
every result is checked by exact object identity.

The raw JSON contains all 11 block samples for every algorithm and case,
paired ratios, median absolute deviations, configuration, provenance,
environment, and the machine-evaluated gate:
[2026-08-05-adaptive-keyed-topk-block-canonical.json](2026-08-05-adaptive-keyed-topk-block-canonical.json).

## Exact-int64 summary

| Distribution | Adaptive vs `heapq` | Adaptive vs strict core |
|---|---:|---:|
| dense | 1.62x–1.82x | 0.94x–1.01x |
| int32 | 1.33x–1.50x | 0.96x–0.99x |
| int64 | 1.10x–1.20x | 0.98x–1.02x |
| heavy duplicates | 1.62x–1.71x | 0.94x–0.97x |

The five cases below the `1.20x` target were all full-range int64 inputs. They
are not gate failures because the pre-registered aggregate requirement was 18
of 24 cases and 19 passed it.

| Distribution | k | Direction | Adaptive vs `heapq` | Adaptive vs strict |
|---|---:|---|---:|---:|
| int64 | 10 | smallest | 1.113x | 1.001x |
| int64 | 10 | largest | 1.135x | 1.017x |
| int64 | 100 | smallest | 1.132x | 0.998x |
| int64 | 100 | largest | 1.099x | 0.999x |
| int64 | 1,000 | largest | 1.197x | 1.002x |

Across all exact cases, the adaptive core measured `1.10x–1.82x` over
`heapq` and `0.94x–1.02x` against the frozen strict core.

## Generic-key summary

| Key domain | Adaptive vs `heapq` |
|---|---:|
| arbitrary-size integer | 1.29x–1.36x |
| string | 1.05x–1.08x |
| integer tuple | 1.05x–1.09x |
| finite float | 1.21x–1.26x |

All 24 generic cases were faster than `heapq` in this run, with a complete
range of `1.05x–1.36x`. This is useful evidence for the compatible fallback,
not a universal performance guarantee.

## Interpretation

The block result resolves the next engineering decision without rewriting
history. The earlier isolated regressions were not reproduced under the
complete paired protocol: the worst exact comparison with the strict core was
`0.94x`, and the worst generic comparison with `heapq` was `1.05x`.

Timing spread was retained rather than filtered. Across 120 algorithm/case
series, relative median absolute deviation ranged from 0.39% to 8.94%, with a
middle value of 1.88% and a 90th-percentile value of 4.02%. This supports using
paired blocks while still treating the measurements as local synthetic
evidence.

The next evidence gates are common Python `lambda` and `attrgetter` callables
and isolated peak memory. The operation remains private until those results,
API clarity, portability, and actual user demand justify a promotion review.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These measurements describe one machine and are not universal guarantees.
