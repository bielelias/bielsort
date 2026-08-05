# Compact stable `argsort` prototype — 2026-08-05

## Decision

**Keep the compact `argsort` implementation as a private research prototype
and continue the engineering work.** It passes both pre-registered research
gates on this machine, but it is not ready to become public API.

For disordered signed-integer lists, construction is materially faster than
`sorted(range(len(values)), key=values.__getitem__)` and uses a smaller
incremental peak. The experiment also exposes two important costs: a nearly
sorted input is slower than the Python baseline, and applying the compact
permutation to a Python list is usually slower than applying a `list[int]`.

This is local synthetic evidence. It does not show universal superiority over
Python or NumPy, establish external demand, or approve a version bump or
publication.

## Prototype contract

The private native function returns the original indices in stable sorted
order without mutating or retaining the source sequence. Its result is an
immutable Python sequence with a read-only buffer:

- 32-bit unsigned indices while the input length permits, otherwise 64-bit;
- stable signed-int64 LSD Radix for eligible disordered inputs;
- identity permutation for an already ordered input;
- compatible Timsort index fallback for small, nearly monotonic, generic, or
  arbitrary-size integer inputs;
- stable `reverse=True` behavior, covered by differential tests;
- no public `bielsort.argsort` or `Permutation` name.

At one million elements, the compact result owns a 4,000,000-byte index
payload. NumPy's `intp` result owns 8,000,000 bytes on this 64-bit machine. A
Python index list alone owns 8,000,056 shallow bytes, excluding its Python
integer objects.

## Construction time

Seven rotated samples ran locally on Linux x86-64 with CPython 3.11.2, GCC
12.2.0, and NumPy 2.4.6. Times are medians in seconds; gains above `1.00x`
favor BielSort over the Python index-sorting baseline.

`NumPy array` starts with an existing `int64` ndarray. `NumPy E2E` starts with
the same Python list as BielSort and includes conversion to an ndarray, but
returns NumPy indices rather than a Python list.

| n | Input | Biel strategy | Python indices | Biel compact | Gain | NumPy array | NumPy E2E |
|---:|---|---|---:|---:|---:|---:|---:|
| 100,000 | dense | Radix, 2 passes | 0.020717 | 0.003538 | 5.86x | 0.007949 | 0.010314 |
| 100,000 | random int32 | Radix, 3 passes | 0.025157 | 0.005186 | 4.85x | 0.008306 | 0.010995 |
| 100,000 | random int64 | Radix, 6 passes | 0.025211 | 0.007261 | 3.47x | 0.007797 | 0.010470 |
| 100,000 | nearly sorted | Timsort fallback | 0.003364 | 0.005073 | 0.66x | 0.000965 | 0.002725 |
| 100,000 | ascending | Identity | 0.003203 | 0.001432 | 2.24x | 0.000351 | 0.002433 |
| 1,000,000 | dense | Radix, 2 passes | 0.289052 | 0.035934 | 8.04x | 0.100658 | 0.119654 |
| 1,000,000 | random int32 | Radix, 3 passes | 0.340690 | 0.052381 | 6.50x | 0.099994 | 0.124475 |
| 1,000,000 | random int64 | Radix, 6 passes | 0.325366 | 0.072094 | 4.51x | 0.090345 | 0.110696 |
| 1,000,000 | nearly sorted | Timsort fallback | 0.047108 | 0.068793 | 0.68x | 0.011792 | 0.027278 |
| 1,000,000 | ascending | Identity | 0.028285 | 0.010789 | 2.62x | 0.001776 | 0.015881 |

The disordered cases pass the speed gate at both required sizes. NumPy remains
the natural choice when the data already lives in an ndarray, particularly
for ordered and nearly ordered inputs. The table compares distinct storage
models explicitly rather than presenting them as interchangeable APIs.

## Incremental peak RSS

Three samples per algorithm and case ran in isolated subprocesses at one
million elements. The values below are median increments above the process
after its input was created. They are operating-system high-water
measurements, not exact allocation traces.

| Input | Python indices | Biel compact | Biel/Python | NumPy array | NumPy E2E |
|---|---:|---:|---:|---:|---:|
| dense | 55.21 MiB | 30.59 MiB | 0.55x | 11.51 MiB | 19.18 MiB |
| random int32 | 57.02 MiB | 30.50 MiB | 0.53x | 11.63 MiB | 19.07 MiB |
| random int64 | 57.10 MiB | 30.54 MiB | 0.53x | 11.76 MiB | 19.21 MiB |
| nearly sorted | 53.68 MiB | 61.12 MiB | 1.14x | 11.63 MiB | 19.34 MiB |
| ascending | 45.90 MiB | 15.34 MiB | 0.33x | 7.76 MiB | 15.40 MiB |

The three disordered cases reduce the measured BielSort peak by 45%–47%, so
the alternative memory gate also passes. The nearly sorted fallback is a
clear negative result: it uses 14% more peak memory because the prototype has
already performed native eligibility work before constructing its compatible
Timsort result. NumPy uses less incremental memory in both of its scenarios.

## Applying the permutation

The permutation was precomputed outside the timer, then used in a Python list
comprehension. Seven rotated samples ran at one million elements.

| Input | Python `list[int]` | Biel compact | Compact/list |
|---|---:|---:|---:|
| dense | 0.091623 s | 0.106229 s | 1.16x |
| random int32 | 0.120239 s | 0.149556 s | 1.24x |
| random int64 | 0.107019 s | 0.137071 s | 1.28x |
| nearly sorted | 0.014525 s | 0.017776 s | 1.22x |
| ascending | 0.013094 s | 0.017243 s | 1.32x |

The compact iterator creates Python integers as indices are requested, while
the baseline list already owns them. This saves persistent storage but adds
iteration cost. A future native application method should be evaluated
against this measured cost before the result type is made public.

## Correctness and scope

- 10 dedicated prototype tests cover ascending and descending stability,
  duplicates, full signed-int64 boundaries, compatible fallbacks, immutability,
  the read-only buffer, source lifetime, and error propagation.
- The complete optimized suite currently contains 119 passing tests.
- The same 119 tests pass locally with AddressSanitizer and
  UndefinedBehaviorSanitizer enabled.
- The native extension compiles with `-Wall -Wextra -Werror` without warnings.
- All six runtime modules match their PEP 561 stubs, and the strict Python 3.9
  public typing contract still passes.
- A clean local wheel and source distribution build includes the new native
  source and header; the wheel installs outside the source tree and exercises
  the compact Radix result successfully.
- The prototype remains private and does not change version `0.2.0`, the
  canonical public exports, or the published package.

Supported cross-platform source and built-wheel validation remain release
gates because this prototype adds native code and a new Python object type.

## Raw evidence and reproduction

The primary seven-sample timing and application record is
[`2026-08-05-compact-argsort-time.json`](2026-08-05-compact-argsort-time.json).
The isolated three-sample memory record is
[`2026-08-05-compact-argsort-full.json`](2026-08-05-compact-argsort-full.json).
Both retain all samples and environment metadata.

```bash
python benchmarks/argsort_prototype.py \
  -n 100000 1000000 \
  -r 7 \
  --skip-memory \
  --json-output compact-argsort-time.json

python benchmarks/argsort_prototype.py \
  -n 100000 1000000 \
  -r 5 \
  --memory-repetitions 3 \
  --json-output compact-argsort-full.json
```
