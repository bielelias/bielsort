# Adaptive keyed selector v2 — 2026-08-04

## Decision

**Keep the direction and keep it private.** Progressive native extraction,
the lower keyed Counting threshold, sparse-run detection, and a vectorcall
replay object remove the original medium dense-int64 blocker and materially
improve sparse nearly-ordered inputs. Random int64 acceleration and generic-key
fallback parity remain intact.

This is still research, not a release candidate. Some 10,000-record adaptive
inputs and one 1,000,000-record spaced input remain slower than CPython
Timsort. The public API and version remain unchanged at 0.1.0.

## What changed from v1

The first selector built a complete Python key cache after a 64-record prefix,
then converted the cache to native int64 a second time. Dense nearly-sorted
inputs below 250,000 records also went through Radix Sort. Those two choices
caused the measured 0.66x and 0.77x results at 10,000 and 100,000 records.

Version 2 changes the private path in four ways:

1. C evaluates and converts keys in one progressive pass. Homogeneous int64
   workloads no longer build a full Python key list.
2. Dense keyed inputs can select stable Counting Sort from 8,192 records.
3. For at most 262,144 records, checkpoints at 64, 128, 256, 512, and 2,048
   keys detect sparse prefixes with few descents. Those candidates go to
   CPython Timsort; a prefix that is merely ordered before a random tail stays
   on the native Radix path.
4. Cached-key replay is now a private vectorcall object instead of a
   `PyCapsule`-backed `PyCFunction`, reducing per-key fallback overhead.

Inputs below 2,048 records still go directly to Timsort. A configured native
memory limit is still decided before any user key call.

## Semantics

The selector preserves:

- stable ordering;
- one user `key` call per input occurrence, in input order;
- the original input list and record identities;
- normal Timsort comparison behavior for generic key domains;
- exceptions from user keys without mutating the input.

When progressive extraction later encounters a generic key, preceding exact
int64 keys are reconstructed as equal Python integer values for replay. The
generic key object that caused the fallback is retained. Normal integer
ordering is unchanged, but an exotic cross-type comparator that inspects the
identity of another key object could observe a difference from `sorted()`.
That edge case must be resolved or explicitly excluded before this becomes a
public implementation.

The replay path remains CPython-specific and relies on listsort requesting
keys in input order. It must be validated on every supported CPython version.

## Median time

Nine rotated samples ran locally on Linux x86-64 with CPython 3.11. Speedups
above 1.00x favor BielSort.

| Records | Key distribution | Selected path | `sorted(key=...)` | Adaptive BielSort | Speedup |
|---:|---|---|---:|---:|---:|
| 10,000 | random int64 | Radix | 0.001727 s | 0.000682 s | 2.53x |
| 10,000 | nearly sorted dense int64 | Counting | 0.000196 s | 0.000222 s | 0.88x |
| 10,000 | nearly sorted wide int64 | sparse-run Timsort | 0.000254 s | 0.000305 s | 0.83x |
| 10,000 | nearly sorted spaced int64 | sparse-run Timsort | 0.000456 s | 0.000517 s | 0.88x |
| 10,000 | ordered prefix + random int64 tail | Radix | 0.001610 s | 0.000660 s | 2.44x |
| 10,000 | string | progressive Timsort | 0.001754 s | 0.001764 s | 0.99x |
| 10,000 | huge integer | progressive Timsort | 0.001666 s | 0.001699 s | 0.98x |
| 100,000 | random int64 | Radix | 0.024312 s | 0.008261 s | 2.94x |
| 100,000 | nearly sorted dense int64 | Counting | 0.003095 s | 0.002708 s | 1.14x |
| 100,000 | nearly sorted wide int64 | sparse-run Timsort | 0.005591 s | 0.005815 s | 0.96x |
| 100,000 | nearly sorted spaced int64 | sparse-run Timsort | 0.003014 s | 0.003263 s | 0.92x |
| 100,000 | ordered prefix + random int64 tail | Radix | 0.023128 s | 0.007911 s | 2.92x |
| 100,000 | string | progressive Timsort | 0.024702 s | 0.025805 s | 0.96x |
| 100,000 | huge integer | progressive Timsort | 0.021784 s | 0.021944 s | 0.99x |
| 1,000,000 | random int64 | Radix | 0.353093 s | 0.090166 s | 3.92x |
| 1,000,000 | nearly sorted dense int64 | Counting | 0.046740 s | 0.031482 s | 1.48x |
| 1,000,000 | nearly sorted wide int64 | Radix | 0.104719 s | 0.095105 s | 1.10x |
| 1,000,000 | nearly sorted spaced int64 | Radix | 0.044885 s | 0.052526 s | 0.85x |
| 1,000,000 | ordered prefix + random int64 tail | Radix | 0.335916 s | 0.083571 s | 4.02x |
| 1,000,000 | string | progressive Timsort | 0.371970 s | 0.373661 s | 1.00x |
| 1,000,000 | huge integer | progressive Timsort | 0.333780 s | 0.336538 s | 0.99x |

The original dense nearly-sorted results improved from 0.66x/0.77x/1.16x to
0.88x/1.14x/1.48x. This removes the material 100,000-record regression and
improves 10,000 records substantially, but 10,000-record adaptive overhead is
still measurable. The wide and spaced cases prevent claiming that the selector
was tuned only to a dense synthetic range.

Raw samples and environment metadata are in
[`2026-08-04-keyed-adaptive-v2.json`](2026-08-04-keyed-adaptive-v2.json).

## Median incremental peak RSS at one million records

Three isolated subprocesses ran per algorithm and distribution. The workload
generators avoid large temporary lists before the RSS baseline is captured.

| Key distribution | `sorted(key=...)` | Adaptive BielSort | Ratio |
|---|---:|---:|---:|
| random int64 | 24.88 MiB | 30.56 MiB | 1.23x |
| nearly sorted dense int64 | 23.04 MiB | 26.63 MiB | 1.16x |
| nearly sorted wide int64 | 25.68 MiB | 30.54 MiB | 1.19x |
| nearly sorted spaced int64 | 23.02 MiB | 30.71 MiB | 1.33x |
| ordered prefix + random int64 tail | 23.82 MiB | 30.52 MiB | 1.28x |
| string | 23.43 MiB | 22.93 MiB | 0.98x |
| huge integer | 24.86 MiB | 22.91 MiB | 0.92x |

Native int64 speed still trades additional peak memory for key and object
buffers. Generic fallbacks remain at or below the measured Timsort peak on this
machine. These are local allocator and RSS observations, not universal bounds.

Raw samples are in
[`2026-08-04-keyed-adaptive-memory-v2.json`](2026-08-04-keyed-adaptive-memory-v2.json).

## Validation

- 74 tests passed in the normal optimized build.
- The same 74 tests passed under ASan and UBSan.
- The Draft PR matrix passed on CPython 3.9-3.14 for Linux and on CPython
  3.11/3.14 for Windows and macOS.
- The C extension compiled with `-Wall -Wextra -Werror` without warnings.
- Differential tests cover native sizes, stable duplicates, int64 extremes,
  strings, huge integers, generators, late generic keys, key exceptions, the
  8,192 Counting boundary, sparse ordered runs, and an ordered prefix followed
  by a random tail.
- Raw timing and memory reports are valid JSON.

## Remaining 0.2 gates

1. Decide whether a 12%-17% loss at 10,000 nearly-sorted records is acceptable
   or requires another conservative selector improvement.
2. Improve or deliberately delegate the one-million spaced-int64 case, which
   measured 0.85x locally.
3. Resolve the reconstructed-int key-identity edge case.
4. Implement stable `reverse=True`; the accepted selector now lives in the
   private installed module `bielsort_native._keyed_adaptive`.
5. Repeat the supported-platform matrix after each semantic or native change,
   especially around vectorcall replay and exception paths.
6. Finalize public diagnostics, types, changelog, and docs before any
   `0.2.0rc1` TestPyPI candidate.

Nothing in this experiment was merged into `main` or published.

## Reproduction

```bash
python -m unittest discover -s tests -v
python -m benchmarks.keyed_adaptive_benchmark \
  --repetitions 9 \
  --output benchmarks/results/2026-08-04-keyed-adaptive-v2.json
python -m benchmarks.keyed_adaptive_memory \
  --repetitions 3 \
  --output benchmarks/results/2026-08-04-keyed-adaptive-memory-v2.json
```
