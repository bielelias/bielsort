# Unified stable top-k façade — canonical result

## Decision

**The pre-registered local gate passed.** The private façade produced all 50
expected stable results by exact object identity, selected every expected
diagnostic route, passed every semantic probe, recorded no paired median below
the `0.85x` regression floor, and placed 47 of 50 cases at or above `0.95x`.
The protocol required at least 40.

This pass authorizes hosted portability and build-only wheel validation. It
does not add a public `top_k`, approve `TopKInfo`, prove external demand,
select a version, approve a merge, or authorize a package publication.

## Provenance

| Item | Value |
|---|---|
| Pre-registered protocol | `0cc6989` |
| Versioned benchmark harness | `72cde8f` |
| Implementation under test | `4f046a6` |
| Python | CPython 3.11.2 |
| Compiler | GCC 12.2.0 |
| Platform | Linux 6.7.0, x86-64, glibc 2.36 |
| CPU | 13th Gen Intel Core i5-1334U |
| Input size | 200,000 records per domain |
| Timing | 7 paired rotated blocks, 1 call per algorithm per block |
| Raw evidence | [JSON with every sample](2026-08-05-unified-topk-facade.json) |

The protocol and thresholds were committed before the benchmark harness and
private implementation. The canonical command was:

```bash
python -m benchmarks.topk_facade_crossover \
  --size 200000 \
  --denominators 64 16 8 4 2 \
  --blocks 7 \
  --calls-per-block 1 \
  --implementation-commit 4f046a6 \
  --json-output benchmarks/results/2026-08-05-unified-topk-facade.json
```

## Timing summary

Speedup is the median of seven paired `baseline / façade` block ratios, so a
value above `1.00x` favors the private façade. The fixed baseline is `heapq`
for `k=n/64` and `n/16`, then stable full sorting for `k=n/8`, `n/4`, and
`n/2`.

| Domain | Cases | Paired speedup range | Cases at least `0.95x` | Selected routes |
|---|---:|---:|---:|---|
| natural signed-int64 | 10 | `1.49x–3.73x` | 10 | native int64 |
| natural strings | 10 | `0.91x–1.06x` | 7 | `heapq` / Timsort |
| keyed signed-int64 | 10 | `2.35x–4.45x` | 10 | native int64 |
| keyed arbitrary-size integers | 10 | `0.98x–1.61x` | 10 | native generic / Timsort |
| keyed strings | 10 | `0.97x–1.50x` | 10 | native generic / Timsort |
| **total** | **50** | **`0.91x–4.45x`** | **47** | adaptive |

The three cases below `0.95x` were all natural-string fallbacks: largest
`n/64` at `0.946x`, and smallest/largest `n/8` at `0.912x` and `0.911x`.
They remain above the unchanged `0.85x` regression floor and are preserved as
negative results rather than hidden or used to retune the crossover.

## Correctness, semantics, and diagnostics

The canonical harness passed its seven grouped probes:

- exact one-call key behavior on partial and full-sort routes, in encounter
  order and in both directions;
- `k == 0`, negative `k`, and Boolean `k` checks before iterable consumption;
- natural ordering without a Python identity key and one-shot iteration once;
- iterator, key, and comparison exception propagation;
- `heapq` fallback or `MemoryError` before explicit key evaluation when the
  native-memory bound is exceeded;
- immutable normalized diagnostics and no public API leakage;
- safe `RuntimeError` when an explicit-key callback resizes the source list on
  the partial native path.

The optimized and ASan/UBSan local suites each passed all 174 tests. The native
extension also compiled with `-Wall -Wextra -Werror`; runtime/stub comparison,
strict Python 3.9 typing, and strict documentation passed.

## What this result does not establish

This is a deterministic synthetic experiment on one development machine. It
does not show how often users have these workloads, does not promise the same
ratios on other processors or Python versions, and does not claim that partial
selection replaces NumPy, dataframe engines, or database query planning.

The result validates a coherent private dispatcher: int64 specialization can
remain fast while generic paths stay close to the standard-library operation
chosen in advance. Hosted Linux/Windows/macOS source builds, hosted
sanitizers, and a fresh non-publishing wheel matrix on the exact candidate are
still required before a public API proposal.

