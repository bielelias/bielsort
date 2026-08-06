# Adaptive generic keyed top-k: 2026-08-05

## Decision

**The pre-registered stage-two gate did not pass.** The adaptive generic-key
implementation remains private research and is not approved for public API
review, a version bump, or a release.

Correctness, stability, identity, exact key-call behavior, exception
propagation, reference release, and the structural `O(k)` memory contract all
passed. Performance missed two unchanged requirements:

- exact int64: 19 of 24 cases reached `1.20x` over `heapq`, exceeding the
  required 18, but 3 cases were more than 15% slower than the frozen strict
  int64 core;
- generic keys: 1 of 24 cases was more than 15% slower than `heapq`.

The thresholds were not changed after measurement. The failed result and all
raw samples are retained.

## Method

The exact regression section uses one million tuple records, four int64
distributions, `k` values 10, 100, and 1,000, both directions, and seven
rotated samples. It compares the adaptive core with the frozen strict-int64
core and `heapq`.

The generic section uses 100,000 tuple records, the same `k` values and
directions, seven rotated samples, and arbitrary-size integers, strings,
integer tuples, and finite floats. It compares the adaptive core with `heapq`.

Record construction and stable reference sorting are outside timed regions.
Every result is checked by exact object identity. The raw JSON retains all
samples, configuration, environment, and gate output:
[2026-08-05-adaptive-keyed-topk.json](2026-08-05-adaptive-keyed-topk.json).

## Exact-int64 summary

| Distribution | Adaptive vs `heapq` | Adaptive vs strict core |
|---|---:|---:|
| dense | 1.31x–1.74x | 0.73x–1.01x |
| int32 | 1.15x–1.42x | 0.84x–1.18x |
| int64 | 1.08x–1.34x | 0.97x–1.01x |
| heavy duplicates | 1.52x–1.62x | 0.94x–0.95x |

The three strict-core regression failures were:

| Distribution | k | Direction | Adaptive vs strict |
|---|---:|---|---:|
| dense | 10 | largest | 0.85x |
| dense | 1,000 | smallest | 0.73x |
| int32 | 100 | largest | 0.84x |

## Generic-key summary

| Key domain | Adaptive vs `heapq` |
|---|---:|
| arbitrary-size integer | 0.73x–1.39x |
| string | 1.03x–1.07x |
| integer tuple | 1.05x–1.11x |
| finite float | 1.19x–1.32x |

The sole generic regression failure was arbitrary-size integers, smallest
`k=100`, at `0.73x`.

## Interpretation

The core establishes a useful semantic result: generic comparable keys can be
selected stably with one key call and only `O(k)` retained key objects, without
an `O(n)` key cache. Most measured cases also beat `heapq`.

However, the performance evidence is not yet robust enough for promotion. A
few raw sample sequences show simultaneous timing shifts across algorithms,
including the failed cases. That suggests host variability, but it does not
invalidate the pre-registered failure or authorize discarding samples.

Any follow-up must be a separately pre-registered profiling and confirmation
experiment. It should distinguish structural overhead from host variance,
then optimize only if a reproducible regression remains. The current result
must continue to be reported even if a later experiment passes.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These measurements describe one machine and are not universal guarantees.
