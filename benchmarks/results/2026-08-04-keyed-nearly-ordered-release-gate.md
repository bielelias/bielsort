# Keyed nearly ordered release gate — 2026-08-04

## Decision

**Document and accept the automatic selector's bounded trade-off for continued
0.2 research; do not add another machine-specific threshold.** The repeated
measurements confirm that keyed inputs which are already close to Timsort's
best case can lose at 10,000 records. The same selector retains material gains
when a similar prefix is followed by random int64 keys.

This is not a decision to publish `0.2.0rc1`. It closes one optimization
investigation so the candidate can focus on an explicit, inspectable memory
and strategy contract instead of claiming universal superiority.

## Why the trade-off exists

Before evaluating an arbitrary Python `key`, the records themselves do not
reveal whether the resulting key sequence is dense, random, or nearly ordered.
The adaptive selector therefore evaluates a 2,048-key prefix before it can
recognize sparse monotonic runs. Preserving Python's one-key-call-per-record
contract requires replaying that prefix when Timsort is selected.

Delegating every 10,000-record keyed input before evaluation would remove the
nearly ordered loss, but would also discard the measured 2.29x-2.41x gains for
the random-tail controls. Shorter prefix thresholds previously misclassified
those controls. A finer size/distribution threshold varied across runs and
would overfit the current machine.

## Recheck methodology

Eleven rotated samples ran on CPython 3.11/Linux with the process pinned to CPU
2. Generation, validation, and previous-result destruction were outside the
timed region. Ratios above 1.00x favor adaptive BielSort.

Reproduction commands:

```bash
taskset -c 2 python -m benchmarks.keyed_adaptive_benchmark \
  --sizes 10000,100000 \
  --cases nearly-sorted-int64,nearly-sorted-wide-int64,nearly-sorted-spaced-int64,ordered-prefix-random-int64,noisy-ordered-prefix-random-int64 \
  --repetitions 11
```

Run the same command with `--reverse` for descending order.

### Ascending

| Workload | 10,000 | 100,000 |
|---|---:|---:|
| nearly sorted dense int64 | 0.86x | 1.05x |
| nearly sorted wide int64 | 0.81x | 0.97x |
| nearly sorted spaced int64 | 0.85x | 0.93x |
| ordered prefix + random tail | 2.29x | 2.66x |
| noisy ordered prefix + random tail | 2.32x | 2.64x |

### Reverse

| Workload | 10,000 | 100,000 |
|---|---:|---:|
| nearly sorted dense int64 | 0.95x | 1.34x |
| nearly sorted wide int64 | 0.79x | 1.03x |
| nearly sorted spaced int64 | 0.79x | 0.86x |
| ordered prefix + random tail | 2.35x | 2.64x |
| noisy ordered prefix + random tail | 2.41x | 2.61x |

The exact ratios differ from the earlier selector-v3 checkpoint, reinforcing
the decision not to tune narrow thresholds from a single timing run. The
direction of the result is consistent: Timsort is difficult to beat on small
nearly ordered keys, while native Radix remains materially faster on random
int64 tails.

Raw samples:

- [`2026-08-04-keyed-nearly-ordered-recheck-ascending.json`](2026-08-04-keyed-nearly-ordered-recheck-ascending.json)
- [`2026-08-04-keyed-nearly-ordered-recheck-reverse.json`](2026-08-04-keyed-nearly-ordered-recheck-reverse.json)

## Product consequence

The automatic `sort(key=...)` path remains conservative but cannot guarantee a
win for every distribution. The unreleased `sort_with_info()` candidate makes
the selected algorithm, reason, key domain, and native-memory estimate visible
without exposing private selector names. Users should still benchmark real
workloads; diagnostics explain a measured result rather than predict runtime
without sorting.
