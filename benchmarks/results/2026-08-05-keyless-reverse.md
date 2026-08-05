# Keyless stable reverse prototype — 2026-08-05

## Decision

**Keep the keyless `reverse=True` native path as an unreleased 0.3
candidate.** It reuses the existing stable Counting and Radix core for exact
signed-int64 values and falls back to CPython Timsort for small, generic, or
nearly monotonic inputs.

The experiment passes its initial gate: disordered integer inputs improve
materially in both the new-list and in-place APIs, while the selector retains
Timsort for its strongest ordered cases. This is local synthetic evidence, not
a universal performance claim and not approval to publish a new release.

## Implementation

Signed integer order is first mapped to the monotonic unsigned domain used by
the existing native core. For descending order, the transformed key is
complemented before stable Counting or LSD Radix sorting. Equal values remain
equal after this transformation, so their original encounter order is not
reversed.

Both public operation shapes are covered:

- `bielsort.sort(values, reverse=True)` returns a new list and may release the
  GIL after it owns its private copy;
- `bielsort.sort_in_place(values, reverse=True)` mutates an exact list and
  keeps the GIL.

Incompatible values and conservative ordered samples call `list.sort` with
`reverse=True` inside the native wrapper. This preserves CPython's stable
descending semantics rather than sorting ascending and reversing equal-value
groups.

## Median time

Seven rotated samples ran locally on Linux x86-64 with CPython 3.11. Times are
seconds; speedups above `1.00x` favor BielSort.

| n | Input | Strategy | `sorted(reverse=True)` | Biel new | Gain | `.sort(reverse=True)` | Biel in-place | Gain |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 10,000 | dense int64 | Radix, 2 passes | 0.001152 | 0.000271 | 4.25x | 0.001111 | 0.000247 | 4.50x |
| 10,000 | random int32 | Radix, 3 passes | 0.001398 | 0.000368 | 3.80x | 0.001377 | 0.000353 | 3.90x |
| 10,000 | random int64 | Radix, 6 passes | 0.001444 | 0.000534 | 2.71x | 0.001442 | 0.000502 | 2.87x |
| 10,000 | nearly descending | Timsort | 0.000072 | 0.000074 | 0.98x | 0.000058 | 0.000062 | 0.93x |
| 10,000 | ascending | Timsort | 0.000049 | 0.000053 | 0.91x | 0.000038 | 0.000042 | 0.91x |
| 100,000 | dense int64 | Radix, 2 passes | 0.014407 | 0.003191 | 4.51x | 0.014375 | 0.002881 | 4.99x |
| 100,000 | random int32 | Radix, 3 passes | 0.018292 | 0.004561 | 4.01x | 0.020866 | 0.004201 | 4.97x |
| 100,000 | random int64 | Radix, 6 passes | 0.020001 | 0.006941 | 2.88x | 0.019957 | 0.006353 | 3.14x |
| 100,000 | nearly descending | Timsort | 0.000970 | 0.000880 | 1.10x | 0.000716 | 0.000741 | 0.97x |
| 100,000 | ascending | Timsort | 0.000565 | 0.000566 | 1.00x | 0.000453 | 0.000443 | 1.02x |
| 1,000,000 | dense int64 | Counting | 0.212232 | 0.034399 | 6.17x | 0.206665 | 0.027889 | 7.41x |
| 1,000,000 | random int32 | Radix, 3 passes | 0.257677 | 0.047973 | 5.37x | 0.250293 | 0.042976 | 5.82x |
| 1,000,000 | random int64 | Radix, 6 passes | 0.278431 | 0.072328 | 3.85x | 0.267501 | 0.065136 | 4.11x |
| 1,000,000 | nearly descending | Timsort | 0.017855 | 0.018149 | 0.98x | 0.014350 | 0.014131 | 1.02x |
| 1,000,000 | ascending | Timsort | 0.011333 | 0.011814 | 0.96x | 0.006808 | 0.006034 | 1.13x |

The disordered cases range from `2.71x` to `6.17x` for the new-list API and
from `2.87x` to `7.41x` in place. The worst recorded ordered case is `0.91x`
at 10,000 elements, where the absolute selector cost is only a few
microseconds but is visible against Timsort's exceptionally short run time.
This bounded loss must remain visible in future release documentation.

Raw samples and environment metadata are in
[`2026-08-05-keyless-reverse.json`](2026-08-05-keyless-reverse.json).

## Validation

- 109 tests pass in the optimized build.
- The same 109 tests pass under AddressSanitizer and
  UndefinedBehaviorSanitizer.
- The native extension compiles with `-Wall -Wextra -Werror` without warnings.
- `mypy.stubtest` passes for all six runtime modules and strict Python 3.9
  contract checking passes.
- Dedicated tests cover stable duplicate identities, full signed-int64 Radix,
  dense Counting, both operation shapes, generators, and stable generic
  fallback.
- Draft PR [#30](https://github.com/bielelias/bielsort/pull/30) passes
  source-build CI on Linux with CPython 3.9–3.14, Windows with CPython
  3.11/3.14, and macOS with CPython 3.11/3.14, plus the hosted sanitizer,
  public-stub, and strict-documentation jobs.

Native-core release consideration still requires building and installing the
supported wheel matrix. No tag, TestPyPI upload, or production publication was
created by this experiment.

## Reproduction

```bash
python -m benchmarks.keyless_reverse_benchmark \
  --sizes 10000,100000,1000000 \
  --cases dense-int64,random-int32,random-int64,nearly-descending,ascending \
  --repetitions 7 \
  --output benchmarks/results/2026-08-05-keyless-reverse.json
```
