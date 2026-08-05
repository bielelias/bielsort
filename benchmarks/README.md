# Benchmark policy

The benchmark imports `bielsort` and compares equivalent operations:

- `sorted(data)` against `bielsort.sort(data)`;
- `data.sort()` against `bielsort.sort_in_place(data)`.

Input copies for in-place algorithms are created before timing. Expected
results are also created outside the timed region.

Run:

```bash
python benchmarks/benchmark.py -n 10000 100000 1000000 -r 5
```

The included distributions exercise:

- dense signed ranges;
- random signed int32;
- random signed int64;
- arbitrary-size 1024-bit integers;
- nearly sorted lists;
- decreasing lists.

Performance claims must include machine, Python, compiler, distributions,
repetitions, and median timings. A speedup on one machine is not a universal
guarantee.

## Peak memory

The memory benchmark runs each algorithm in a separate child process so the
native C allocations contribute to the operating system's peak RSS:

```bash
python benchmarks/memory.py -n 1000000 -r 3
```

It currently supports Linux and macOS. Reported memory is the incremental peak
above the process state after generating the input. It is an operating-system
measurement, not an exact allocation trace.

## NumPy

Install the optional benchmark dependency and run:

```bash
python -m pip install -e ".[benchmark]"
python benchmarks/numpy_comparison.py -n 10000 100000 1000000 -r 5
```

`NumPy E2E` includes conversion from `list[int]` to `ndarray`, stable sorting,
and conversion back to `list[int]`. `NumPy array` measures stable sorting when
the input is already an `int64` array; it is intentionally shown as a
different API scenario.

## Workload validation

Run transparent synthetic proxies for event timestamps, signed record IDs,
and mostly ordered offsets:

```bash
python benchmarks/workload_validation.py \
  -n 10000 100000 1000000 \
  -r 7 \
  --json bielsort-workload-report.json
```

This command compares equivalent new-list operations and writes a shareable
report containing the environment, configuration, selected strategies,
whether a native fast path ran, medians, speedups, and winner for each case.
Algorithm order is interleaved deterministically. Input generation and
expected results stay outside the timed region.

These inputs are workload **proxies**, not claims about production behavior.
Potential users should replace a proxy with an anonymized deterministic
generator matching their data and report both positive and negative results.
See the [use-case guide](../docs/use-cases.md) for the adoption checklist.

## Private workload evaluator

To measure a user-owned list without writing its values to a report, copy the
provider example and replace `load_values()` with local application code:

```bash
cp benchmarks/workload_provider_example.py my_workload.py
python benchmarks/workload_evaluator.py \
  my_workload.py:load_values \
  --label "anonymous-description"
```

The evaluator compares `sorted()` with `bielsort.sort()` and `list.sort()`
with `bielsort.sort_in_place()`. It retains raw nanosecond timing samples but
never raw workload values or the provider path. There is no upload step. Both
the JSON and Markdown must be reviewed by the user before submission. Pass
`--minimal-metadata` to omit sampled distribution statistics.

See the [evaluator guide](../docs/evaluator.md) or the
[Portuguese guide](../docs/evaluator-pt.md) for the complete privacy and
measurement policy.

## Published-wheel runner matrix

Maintainers can manually run the
[`Hosted runner validation`](../.github/workflows/workload-validation.yml)
workflow. It installs an exact BielSort version from PyPI on Ubuntu, Windows,
Intel macOS, and Apple Silicon macOS, then uploads one JSON report per runner.
The final job consolidates environment metadata, strategy selection, timings,
and within-runner ratios into Markdown.

GitHub-hosted machines have variable load. Use the matrix to validate wheel
installation, correctness, portability, and broad consistency. Do not use its
absolute seconds as stable hardware benchmarks or its synthetic inputs as
evidence of real user demand. See the
[hosted validation policy](../docs/external-validation.md).

## Timsort fallback overhead

The fallback profiler separates list-copy, slice-copy, equivalent new-list,
and in-place operations without changing the selector:

```bash
python benchmarks/fallback_overhead.py \
  -n 10000 100000 1000000 \
  -r 15 \
  --json fallback-overhead.json
```

It retains every nanosecond sample as well as medians and derived overheads.
Every result is validated and released before the next timer starts, preventing
one operation from inheriting another operation's list-destruction cost.
The manual `Fallback overhead profiling` workflow installs the public PyPI
wheel on matching Ubuntu runners with CPython 3.11 and 3.14. This research
exists to characterize [issue 18](https://github.com/bielelias/bielsort/issues/18),
not to justify tuning a heuristic to one synthetic distribution.

## Research: Python objects with signed-int64 keys

The keyed-int64 prototype is intentionally private to the native extension. It
does not change the supported `bielsort` API or the published 0.1 behavior.
It asks whether BielSort should accelerate stable sorting of arbitrary Python
objects whose `key` callable returns an exact signed-64-bit integer:

```bash
python benchmarks/keyed_int64_prototype.py \
  -n 10000 100000 1000000 \
  -r 5 \
  --memory-repetitions 3 \
  --json-output keyed-int64-prototype.json
```

Both candidates receive the same live list of objects, call the same key
callable, preserve the input, and return a new list. Results are checked for
ordering, stability, identity preservation, and length. Peak RSS uses an
isolated process per sample.

The decision gates were fixed before collecting full-size results:

1. Correctness, stability, exact identity preservation, and one key call per
   object are mandatory.
2. Continue product research if at least two large disordered cases reach a
   median speedup of `1.50x` or better while incremental peak RSS remains below
   `2.00x` the `sorted(key=...)` baseline.
3. Alternatively, continue if one credible large case reduces incremental peak
   RSS by at least 30% without slowing down by more than 10%.
4. Small and nearly sorted losses are allowed in this forced-native prototype,
   but a public API would need a conservative pre-key-extraction selector that
   sends those cases directly to Timsort.

Passing these gates is evidence for continued engineering, not evidence of
market demand. Failing them means the API direction should be discarded or
redesigned before publication.

## Research: compact stable argsort

The private compact-index prototype compares stable permutation construction,
Python and native application to a Python sequence, reuse across three
parallel lists, result storage, isolated peak RSS, and two explicit NumPy
scenarios:

```bash
python benchmarks/argsort_prototype.py \
  -n 100000 1000000 \
  -r 5 \
  --memory-repetitions 3 \
  --json-output compact-argsort.json
```

`NumPy array` starts with an existing `int64` ndarray. `NumPy E2E` includes
conversion from the same Python list received by BielSort. These are reported
separately because combining them would compare different input contracts.
The BielSort result is private, immutable, and exposed as a read-only 32- or
64-bit buffer; no public `argsort` API is implied by this benchmark.

The pre-registered gate and the first local result are recorded in the
[versioned research report](results/2026-08-05-compact-argsort.md). Raw timing,
application, memory, and environment samples are linked from that report.
The native-application continuation and its separate pre-registered gates are
recorded in the
[native application report](results/2026-08-05-compact-argsort-native-apply.md).
It measures both application in isolation and the complete build-once,
apply-three-lists operation. Both implementations receive reusable sequences;
one-shot generators are outside the prototype contract.

## Research: stable compact top-k

The private top-k prototype compares stable reusable index selection against
both full Python sorting and the standard library's partial `heapq` selection.
It also measures constructing one order and applying it to three parallel
Python sequences:

```bash
python benchmarks/topk_prototype.py \
  -n 100000 1000000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output stable-topk.json
```

The eligible path targets exact signed-int64 values and small `k`, uses a
native stable heap, and returns the existing private compact permutation.
Algorithm order is rotated, every index/result is checked against stable full
sorting, and all timing samples are retained. See the
[top-k proposal](../docs/topk-research.md) for the fixed gates and limitations.
The first canonical run passed all fixed gates; its medians, limitations, and
raw-sample link are in the
[versioned stable top-k report](results/2026-08-05-stable-topk.md).

The private continuation compares applying the same compact order through
repeated native `apply()` calls with one fused `apply_many()` call:

```bash
python benchmarks/permutation_apply_many.py \
  -n 100000 1000000 \
  -r 9 \
  --json-output apply-many.json
```

Both operations produce identical tuples of new Python lists; permutation
construction stays outside the timed region. Small results are batched and
normalized per call. The fixed gate is documented in the
[top-k research proposal](../docs/topk-research.md).

The canonical run did not pass the unchanged continuation gate: 12 of 15
target cases reached `1.05x`, but only 2 of 6 complete-permutation cases
reached the required `1.10x`. The method remains private. See the
[versioned fused-application report](results/2026-08-05-permutation-apply-many.md)
and its linked raw samples.

## Research: direct stable keyed top-k

The next experiment will compare a private direct record-returning path with
`heapq.nsmallest()`/`nlargest()` and stable full sorting. Its exact-int64
scope, key-call semantics, canonical 24 cases, and unchanged continuation
gates are fixed before implementation in the
[direct keyed top-k proposal](../docs/keyed-topk-research.md).

Run the benchmark with:

```bash
python benchmarks/keyed_topk_prototype.py \
  -n 100000 1000000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output keyed-topk.json
```

The record list is built outside the timed region, algorithm order rotates,
and all raw samples and environment metadata are retained. The fixed gate is
evaluated only when the complete one-million-record shape is present.

The first canonical run passed the unchanged gate: 18 of 24 target cases
reached `1.25x` over `heapq`, none regressed by more than 10%, and every result
matched stable full sorting by identity. See the
[versioned direct keyed top-k report](results/2026-08-05-keyed-topk.md) and its
linked raw samples.

The stage-two continuation was pre-registered in the same proposal. It
measures an adaptive `O(k)` heap over generic comparable keys, guard behavior,
exact-int64 regression against the frozen private core, and generic fallback
against `heapq`. Its thresholds were fixed before implementation.

The implemented benchmark command is:

```bash
python benchmarks/keyed_topk_fallback.py \
  --exact-size 1000000 \
  --generic-size 100000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output adaptive-keyed-topk.json
```

The gate is evaluated only with both complete canonical shapes. Exact cases
compare the adaptive and frozen strict cores with `heapq`; generic cases use
arbitrary-size integers, strings, integer tuples, and finite floats.

The first canonical run did not pass: three exact cases exceeded the strict-
core regression limit and one generic case exceeded the `heapq` regression
limit. Semantic and memory gates passed. See the
[versioned adaptive keyed top-k report](results/2026-08-05-adaptive-keyed-topk.md)
and its linked raw samples.

A separately pre-registered confirmation rechecks the four failures and two
controls with warm-ups, three calls per block, and 15 rotated blocks. It does
not alter the failed gate or authorize promotion; its purpose is to separate
repeatable overhead from host timing shifts.

## Research: adaptive generic keys

The follow-up selector keeps `key` generic, calls user code exactly once, and
uses progressive native int64 extraction only when eligible. Sparse ordered
runs can return conservatively to Timsort through a private vectorcall replay
object. Reproduce its timing and isolated peak-RSS reports with:

```bash
python -m benchmarks.keyed_adaptive_benchmark \
  --repetitions 7 \
  --output keyed-adaptive-time.json
python -m benchmarks.keyed_adaptive_benchmark \
  --repetitions 7 \
  --reverse \
  --output keyed-adaptive-reverse-time.json
python -m benchmarks.keyed_adaptive_memory \
  --repetitions 3 \
  --output keyed-adaptive-memory.json
```

This remains a private prototype. Its key replay deliberately targets CPython
and must pass the supported-version wheel matrix before it can back the public
`sort(key=...)` implementation. The selector is shipped only as the private
internal module `bielsort_native._keyed_adaptive`, so wheel-level tests can
exercise the real packaging boundary without adding it to either public
package's `__all__`.

Selector v3 adds `noisy-ordered-prefix-random-int64` to the timing matrix. It
prevents a short nearly ordered prefix from hiding a disordered tail and
records whether the conservative 2,048-key policy preserves the native Radix
path.

## Research: candidate public keyed API

The accepted candidate wires the private selector into the existing new-list
API without adding names or parameters. It deliberately leaves the in-place
key path on `list.sort()`:

```bash
python -m benchmarks.keyed_public_api_benchmark \
  --repetitions 11 \
  --cases dense-int64,int64,string \
  --output keyed-public-api.json
```

Pass `--reverse` for the descending matrix. The benchmark imports the
canonical `bielsort` package, so it measures the public wrapper rather than
calling the private selector directly.

The follow-up nearly ordered release gate deliberately retains negative
results. It compares the 2,048-key adaptive policy against random-tail controls
at 10,000 and 100,000 records, and explains why another narrow threshold was
rejected instead of tuned to one machine.

## Research: keyless stable reverse

The unreleased 0.3 candidate tests whether the natural integer path can support
stable descending order without reversing equal-value groups:

```bash
python -m benchmarks.keyless_reverse_benchmark \
  --sizes 10000,100000,1000000 \
  --cases dense-int64,random-int32,random-int64,nearly-descending,ascending \
  --repetitions 7 \
  --output keyless-reverse.json
```

The harness compares both equivalent operation shapes:
`sorted(reverse=True)` against `bielsort.sort(reverse=True)`, and
`list.sort(reverse=True)` against `bielsort.sort_in_place(reverse=True)`.
Copies for the in-place inputs and expected outputs are prepared outside the
timed region. Algorithm order is rotated, every result is checked, and raw
samples are retained.

## Versioned results

- [Keyless stable reverse prototype — 2026-08-05](results/2026-08-05-keyless-reverse.md)
- [Keyed nearly ordered release gate — 2026-08-04](results/2026-08-04-keyed-nearly-ordered-release-gate.md)
- [Candidate public `sort(key=...)` API — 2026-08-04](results/2026-08-04-keyed-public-api-candidate.md)
- [Adaptive generic-key selector v3 — 2026-08-04](results/2026-08-04-keyed-adaptive-selector-v3.md)
- [Exact key-identity replay — 2026-08-04](results/2026-08-04-key-identity-replay.md)
- [Stable reverse keyed selector — 2026-08-04](results/2026-08-04-keyed-adaptive-reverse.md)
- [Adaptive generic-key selector v2 — 2026-08-04](results/2026-08-04-keyed-adaptive-selector-v2.md)
- [Adaptive generic-key selector — 2026-08-04](results/2026-08-04-keyed-adaptive-selector.md)
- [Keyed-int64 native-memory guard — 2026-08-04](results/2026-08-04-keyed-int64-memory-guard.md)
- [Structured keyed-int64 diagnostics — 2026-08-04](results/2026-08-04-keyed-int64-diagnostics.md)
- [Compact keyed-int64 Radix buffers — 2026-08-04](results/2026-08-04-keyed-int64-compact.md)
- [Signed-int64 keyed-object prototype — 2026-08-04](results/2026-08-04-keyed-int64-prototype.md)
- [Corrected hosted validation and fallback investigation — 2026-07-31](results/2026-07-31-fallback-investigation.md)
- [Superseded GitHub-hosted snapshot — 2026-07-31](results/2026-07-31-github-hosted.md)
- [Linux x86-64 — 2026-07-30](results/2026-07-30-linux-x86_64.md)
- [Counting Sort memory optimization — 2026-07-30](results/2026-07-30-counting-memory.md)
