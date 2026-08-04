# Stable reverse keyed selector — 2026-08-04

## Decision

**Keep native `reverse=True` in the private 0.2 research path.** It matches
`sorted(key=..., reverse=True)`, preserves duplicate encounter order, evaluates
the user key exactly once per item in input order, and retains the large
random-int64 advantage without penalizing generic-key fallback materially.

This remains private research. The public BielSort 0.1 API and version are
unchanged, and no release claim follows from these local measurements.

## Implementation

The native core maps signed-int64 keys to their monotonic unsigned domain as
before. For reverse ordering it complements that transformed key and then runs
the same stable Counting or LSD Radix implementation. Ascending order of the
complemented domain is descending order of the original signed domain.

This approach is important for stability. Reversing an already sorted output
would also reverse each equal-key group. The key transformation leaves equal
keys equal, so their original encounter order is preserved naturally.

Generic and sparse-run fallbacks pass `reverse=True` to CPython Timsort through
the existing one-shot cached-key replay object. If progressive extraction
encounters a non-int64 key, complemented native prefix values are converted
back to their original Python integer values before replay.

## Median time

Five rotated samples ran locally on Linux x86-64 with CPython 3.11. Speedups
above 1.00x favor BielSort.

| Records | Key distribution | Selected path | `sorted(reverse=True)` | Adaptive BielSort | Speedup |
|---:|---|---|---:|---:|---:|
| 10,000 | random int64 | Radix | 0.001818 s | 0.000690 s | 2.64x |
| 10,000 | nearly sorted dense int64 | Counting | 0.000232 s | 0.000236 s | 0.98x |
| 10,000 | string | progressive Timsort | 0.001715 s | 0.001767 s | 0.97x |
| 10,000 | huge integer | progressive Timsort | 0.001568 s | 0.001616 s | 0.97x |
| 100,000 | random int64 | Radix | 0.024647 s | 0.008315 s | 2.96x |
| 100,000 | nearly sorted dense int64 | Counting | 0.004543 s | 0.003241 s | 1.40x |
| 100,000 | string | progressive Timsort | 0.026083 s | 0.025960 s | 1.00x |
| 100,000 | huge integer | progressive Timsort | 0.022460 s | 0.022149 s | 1.01x |
| 1,000,000 | random int64 | Radix | 0.368443 s | 0.094271 s | 3.91x |
| 1,000,000 | nearly sorted dense int64 | Counting | 0.063063 s | 0.034564 s | 1.82x |
| 1,000,000 | string | progressive Timsort | 0.387689 s | 0.386637 s | 1.00x |
| 1,000,000 | huge integer | progressive Timsort | 0.342368 s | 0.341869 s | 1.00x |

The 10,000-record losses are 2%-3%, inside ordinary local timing noise but
still reported rather than rounded into a performance claim. Raw samples and
environment metadata are in
[`2026-08-04-keyed-adaptive-reverse.json`](2026-08-04-keyed-adaptive-reverse.json).

An ascending regression run in the same session retained the established
shape: random-int64 speedups were 2.52x, 2.87x, and 3.98x at 10,000, 100,000,
and 1,000,000 records; generic fallbacks remained between 0.96x and 1.01x.

## Validation

- 83 tests pass in the optimized build.
- The same 83 tests pass under ASan and UBSan.
- The C extension compiles with `-Wall -Wextra -Werror`.
- Reverse-specific tests cover Counting, Radix, full signed-int64 extremes,
  stable duplicates, sparse-run replay, late huge-int fallback, memory-limit
  fallback, generators, option validation, and randomized differential checks
  across integer, string, and arbitrary-size integer key domains.
- The original input and record identities remain unchanged.
- Structured diagnostics now report the requested `reverse` direction.

## Reproduction

```bash
python -m unittest discover -s tests -v
python -m benchmarks.keyed_adaptive_benchmark \
  --sizes 10000,100000,1000000 \
  --cases int64,nearly-sorted-int64,string,huge-int \
  --repetitions 5 \
  --reverse \
  --output benchmarks/results/2026-08-04-keyed-adaptive-reverse.json
```

The next gates remain the known nearly-sorted/spaced selector losses, the
exotic reconstructed-key identity decision, and public API/type/documentation
design. This work was not merged into `main` or published.
