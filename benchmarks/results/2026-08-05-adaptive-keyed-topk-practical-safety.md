# Adaptive keyed top-k safety revalidation: 2026-08-05

## Decision

**The unchanged stage-three callable and isolated-memory gates passed again
after callback-safety hardening.** Nineteen of 24 common-callable cases reached
at least `1.10x` over `heapq`, versus the required 18, and none fell below the
fixed `0.90x` regression floor. Every semantic probe retained stable identity,
one key call per record in encounter order, and zero calls for `k == 0`.

The isolated-memory gate also passed. All eight cases had measurable traced
peaks, none exceeded the fixed `1.25x` adaptive/`heapq` ceiling, and all four
`k=100,000` cases met the required `0.80x` reduction target.

This revalidation does not expose `top_k`, change the package version, create
a tag, merge the draft PR, or publish a package.

## Why the gate was repeated

The private promotion review found that the native loop held a borrowed list
item while calling arbitrary Python code. A `key` that cleared the same input
list could invalidate that reference and crash the process. Commit `e0d6107`
keeps the current record alive across the callback and checks the reusable
input length around key and generic-comparison execution.

That safety work adds one temporary reference increment/decrement per
encountered record. The original practical evidence could therefore not be
assumed to describe the hardened code; this run repeats the exact canonical
shape and thresholds without replacing the
[original result](2026-08-05-adaptive-keyed-topk-practical.md).

## Provenance and method

- Pre-registered protocol: `1c793b9`
- Original selection baseline: `fdc9bb5`
- Hardened implementation measured: `e0d6107`
- Input size: 1,000,000 records
- Timing: 9 rotated paired blocks, 3 calls per algorithm per block
- Memory: 3 fresh child processes per algorithm and case, before timing

The raw JSON preserves all timing blocks, isolated workers, semantic probes,
configuration, environment, and machine-evaluated decisions:
[2026-08-05-adaptive-keyed-topk-practical-safety.json](2026-08-05-adaptive-keyed-topk-practical-safety.json).

## Common-callable timing

| Callable | Cases at least 1.10x | Hardened adaptive vs `heapq` |
|---|---:|---:|
| `itemgetter(0)` | 6/6 | 1.34x–1.52x |
| `lambda record: record[0]` | 4/6 | 1.09x–1.22x |
| `attrgetter("score")` | 6/6 | 1.34x–1.53x |
| `lambda record: record.score` | 3/6 | 1.09x–1.20x |

The five cases below the `1.10x` target remain recorded rather than rounded
into successes:

| Callable | k | Direction | Hardened adaptive vs `heapq` |
|---|---:|---|---:|
| `lambda record: record[0]` | 10 | smallest | 1.098x |
| `lambda record: record[0]` | 100 | largest | 1.092x |
| `lambda record: record.score` | 10 | smallest | 1.085x |
| `lambda record: record.score` | 10 | largest | 1.089x |
| `lambda record: record.score` | 100 | largest | 1.092x |

All remain above the `0.90x` regression floor, and the hardened adaptive core
won every measured case on this host. Relative median absolute deviation
across the 48 algorithm/case series had a middle value of 2.29%, a
90th-percentile value of 6.10%, and a maximum of 12.31%.

The result narrows the claim appropriately: C-level accessors retain the
largest gains. Python lambda execution is shared work and leaves a smaller
margin, even though the fixed aggregate gate still passes.

## Isolated peak memory

| Key domain | k | Direction | `heapq` traced | Hardened adaptive traced | Adaptive/`heapq` |
|---|---:|---|---:|---:|---:|
| dense int64 | 1,000 | smallest | 111.7 KiB | 31.5 KiB | 0.28x |
| dense int64 | 1,000 | largest | 111.7 KiB | 31.5 KiB | 0.28x |
| dense int64 | 100,000 | smallest | 10.68 MiB | 3.05 MiB | 0.29x |
| dense int64 | 100,000 | largest | 10.68 MiB | 3.05 MiB | 0.29x |
| arbitrary-size integer | 1,000 | smallest | 111.7 KiB | 47.1 KiB | 0.42x |
| arbitrary-size integer | 1,000 | largest | 111.7 KiB | 47.1 KiB | 0.42x |
| arbitrary-size integer | 100,000 | smallest | 10.68 MiB | 4.58 MiB | 0.43x |
| arbitrary-size integer | 100,000 | largest | 10.68 MiB | 4.58 MiB | 0.43x |

The transient safety reference does not change the structural `O(k)` design.
The hardened core again used approximately 71% less traced peak memory for
exact int64 keys and 57% less for arbitrary-size integers in the fixed cases.
Incremental process RSS remains diagnostic only because allocator high-water
behavior can reuse pages already committed by input construction.

## Interpretation

The callback-safety fix preserves the practical performance and memory case
for continued private API implementation. It does not resolve the remaining
public-design work: natural-order `key=None`, a benchmarked large-`k`
full-sort crossover, and structured `TopKInfo` diagnostics are still required.
Cross-platform source, sanitizer, and build-only wheel validation must also
pass on the hardened commit.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These synthetic measurements describe one machine and are not universal
guarantees.
