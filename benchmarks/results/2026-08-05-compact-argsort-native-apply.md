# Compact `argsort` native application — 2026-08-05

## Decision

**Keep the native application path as private research and continue the
engineering work.** All three pre-registered continuation gates pass on this
machine. The result does not create a public API, change version `0.2.0`, or
authorize a package publication.

The experiment addresses the main weakness found in the first compact
`argsort` pass. Applying the permutation in native code is `2.14x–4.86x`
faster than a Python list comprehension driven by precomputed `list[int]`
indices at one million elements. Building one order and reusing it across
three parallel Python lists is `4.93x–6.41x` faster for the three disordered
one-million-element cases.

These are local synthetic measurements, not universal performance promises or
evidence of external demand.

## Private contract

The private `_Permutation.apply(sequence)` method:

- returns a new Python list in permutation order;
- preserves the exact source objects and their stable relative order;
- leaves both the source and permutation unchanged;
- accepts reusable Python sequences, including lists, tuples, and strings;
- rejects one-shot generators;
- requires the source length to equal the permutation length.

The implementation reads the compact 32- or 64-bit native indices directly
and fills the result list in C. It therefore avoids materializing a Python
integer for each index. Neither `_Permutation` nor its constructor is exposed
by the public `bielsort` package.

## Applying a precomputed permutation

Seven rotated samples ran locally on Linux x86-64 with CPython 3.11.2 and GCC
12.2.0. Times are medians in seconds. The Python baseline uses a precomputed
`list[int]`; Biel native uses the same precomputed logical permutation.

| n | Input | Python `list[int]` | Compact iteration | Native apply | Native/Python gain |
|---:|---|---:|---:|---:|---:|
| 100,000 | dense | 0.003398 | 0.004634 | 0.000700 | 4.85x |
| 100,000 | random int32 | 0.003222 | 0.003894 | 0.000730 | 4.41x |
| 100,000 | random int64 | 0.005198 | 0.004870 | 0.000947 | 5.49x |
| 100,000 | nearly sorted | 0.001103 | 0.001456 | 0.000252 | 4.38x |
| 100,000 | ascending | 0.000997 | 0.001358 | 0.000272 | 3.66x |
| 1,000,000 | dense | 0.085392 | 0.108690 | 0.020567 | 4.15x |
| 1,000,000 | random int32 | 0.087861 | 0.112111 | 0.019855 | 4.43x |
| 1,000,000 | random int64 | 0.091156 | 0.104461 | 0.018756 | 4.86x |
| 1,000,000 | nearly sorted | 0.011843 | 0.014885 | 0.004840 | 2.45x |
| 1,000,000 | ascending | 0.010972 | 0.014217 | 0.005129 | 2.14x |

The first gate required at least `1.50x` in four of five one-million-element
cases. All five pass.

## Build once and apply to three lists

This complete flow constructs one stable order and applies it to three
parallel lists: the primary values, original positions, and a repeated
97-group payload. The Python baseline constructs a `list[int]` order and runs
three list comprehensions. BielSort constructs a compact order and calls the
private native method three times.

| n | Input | Python complete flow | Biel complete flow | Gain |
|---:|---|---:|---:|---:|
| 100,000 | dense | 0.026861 | 0.004377 | 6.14x |
| 100,000 | random int32 | 0.029621 | 0.005725 | 5.17x |
| 100,000 | random int64 | 0.032840 | 0.008495 | 3.87x |
| 100,000 | nearly sorted | 0.006197 | 0.005142 | 1.21x |
| 100,000 | ascending | 0.005054 | 0.001308 | 3.86x |
| 1,000,000 | dense | 0.494575 | 0.077179 | 6.41x |
| 1,000,000 | random int32 | 0.556220 | 0.087533 | 6.35x |
| 1,000,000 | random int64 | 0.551261 | 0.111891 | 4.93x |
| 1,000,000 | nearly sorted | 0.084894 | 0.081820 | 1.04x |
| 1,000,000 | ascending | 0.069042 | 0.026388 | 2.62x |

The second gate required `1.50x` in at least two disordered large cases; all
six measured disordered size/case combinations pass. The third gate prohibited
a regression greater than 10% for nearly sorted data. BielSort is slightly
faster in both measured sizes, so that gate also passes.

The nearly sorted result remains an important qualification. Compact
permutation construction alone is slower than Timsort (`0.55x` at 100,000 and
`0.68x` at one million in this run). Native reuse only offsets that cost when
the order is subsequently applied to several Python sequences.

## Incremental peak RSS for the three-list flow

Three samples per implementation ran in isolated subprocesses at one million
elements. Values are median increments above the process after input
construction, not exact allocation traces.

| Input | Python complete flow | Biel complete flow | Biel/Python | Approx. reduction |
|---|---:|---:|---:|---:|
| dense | 63.26 MiB | 30.57 MiB | 0.48x | 52% |
| random int32 | 69.13 MiB | 30.55 MiB | 0.44x | 56% |
| random int64 | 63.00 MiB | 30.58 MiB | 0.49x | 51% |
| nearly sorted | 64.15 MiB | 60.79 MiB | 0.95x | 5% |
| ascending | 63.09 MiB | 26.39 MiB | 0.42x | 58% |

## Interpretation and limits

The follow-up demonstrates a concrete niche: Python programs that hold large
signed-integer sequences and need to apply one stable order to multiple
parallel Python sequences. It does not replace NumPy sorting for data already
stored in ndarrays, and the first report's separate NumPy comparisons still
apply. Public API naming, buffer compatibility, unsupported-domain behavior,
and cross-platform wheel evidence remain future promotion decisions.

## Validation

- 13 dedicated compact-argsort tests cover the result and native-application
  contract.
- The complete optimized suite contains 122 passing tests.
- The same 122 tests pass with AddressSanitizer and
  UndefinedBehaviorSanitizer.
- The extension compiles with `-Wall -Wextra -Werror` without warnings.
- All six runtime modules match their PEP 561 stubs, strict Python 3.9 typing
  passes, and runtime introspection reports `apply(sequence, /)`.
- A local wheel and source distribution pass `twine check`; the wheel installs
  in a clean environment outside the source tree and exercises both the
  public sort and private native application successfully.
- No public export, version, tag, TestPyPI file, or PyPI file was created.

## Raw evidence and reproduction

The canonical seven-sample timing, construction, application, and reuse record
is
[`2026-08-05-compact-argsort-native-apply.json`](2026-08-05-compact-argsort-native-apply.json).
The isolated three-sample peak-memory record is
[`2026-08-05-compact-argsort-native-apply-memory.json`](2026-08-05-compact-argsort-native-apply-memory.json).
The memory-only JSON intentionally omits application timings, so its combined
application gate reads false; the canonical timing JSON contains and passes
the complete pre-registered gate.

```bash
python benchmarks/argsort_prototype.py \
  -n 100000 1000000 \
  -r 7 \
  --skip-memory \
  --json-output compact-argsort-native-apply.json

python benchmarks/argsort_prototype.py \
  -n 1000000 \
  -r 1 \
  --memory-repetitions 3 \
  --skip-application \
  --json-output compact-argsort-native-apply-memory.json
```
