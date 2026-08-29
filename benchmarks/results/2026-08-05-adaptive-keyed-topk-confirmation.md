# Adaptive keyed top-k failure confirmation: 2026-08-05

## Decision

**The separately pre-registered confirmation is consistent with host timing
variability.** All four previously failed cases and both controls reached the
fixed minimum paired speedup of `0.87x`.

This result does not replace or retroactively pass the original stage-two
gate. The original failed result remains the promotion decision of record. A
new complete canonical protocol must be pre-registered before the adaptive
candidate can be reconsidered.

## Method

No selection code changed after the failed canonical run. The confirmation
uses the same deterministic data for four failed cases and two controls. Each
algorithm receives one untimed warm-up, then 15 rotated blocks of three calls.
The reported decision uses the median of comparator/adaptive speedup ratios
paired by block.

The raw JSON retains all 15 samples per algorithm, paired ratios,
configuration, environment, and decision:
[2026-08-05-adaptive-keyed-topk-confirmation.json](2026-08-05-adaptive-keyed-topk-confirmation.json).

## Results

| Case | Comparator | Comparator median | Adaptive | Median paired speedup |
|---|---|---:|---:|---:|
| dense, largest, k=10 | strict int64 | 0.01297 s | 0.01318 s | 1.00x |
| dense, smallest, k=1,000 | strict int64 | 0.01341 s | 0.01411 s | 0.95x |
| int32, largest, k=100 | strict int64 | 0.01979 s | 0.02050 s | 0.97x |
| heavy duplicates, smallest, k=100 control | strict int64 | 0.01274 s | 0.01342 s | 0.95x |
| huge integer, smallest, k=100 | `heapq` | 0.00326 s | 0.00244 s | 1.33x |
| string, smallest, k=100 control | `heapq` | 0.00309 s | 0.00288 s | 1.08x |

The three exact-int64 failures now show approximately 0%–5% adaptive overhead
instead of 15%–27%. The generic failure is `1.33x` faster than `heapq` under
block timing. The controls are consistent with their surrounding domains.

## Interpretation

These results support host variability as the main cause of the four isolated
canonical failures. They also bound the likely exact-int64 cost of retaining
up to `k` key references for a possible generic transition at roughly 3%–5%
on these cases.

The evidence is encouraging but deliberately non-promotional. The next valid
decision point is a newly pre-registered complete block-timed canonical run,
not selecting this confirmation instead of the original failure.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These measurements describe one machine and are not universal guarantees.
