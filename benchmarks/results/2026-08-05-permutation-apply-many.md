# Private fused permutation application: 2026-08-05

## Decision

**The pre-registered continuation gate did not pass.** The private
`_Permutation.apply_many()` experiment remains research-only and is not a
performance claim, public API proposal, or release candidate.

The implementation passed correctness checks and no canonical case regressed
by more than 5%. It reached at least `1.05x` in 12 of 15 one-million-element
target cases, exceeding the required 9. However, only 2 of 6 complete-
permutation cases reached `1.10x`, below the required 3. The criterion was not
changed after observing the result.

## Method

The benchmark compares one fused `apply_many()` call with repeated native
`apply()` calls on the same already-constructed compact permutation. Both
paths validate their results against exact object identity and return new
Python lists. Permutation construction is outside the timed region.

The canonical run used:

- source sizes 100,000 and 1,000,000;
- compact top-k lengths 10, 100, and 1,000;
- random and identity complete permutations;
- 2, 3, and 5 aligned Python lists;
- nine rotated timing samples per case.

Small top-k operations were batched and normalized to one call because their
duration is below one microsecond. The raw JSON preserves all samples, batch
sizes, configuration, gate output, and environment metadata:
[2026-08-05-permutation-apply-many.json](2026-08-05-permutation-apply-many.json).

## One-million-element results

Higher speedup is better. Times are medians normalized to one application.

| Permutation | Lists | Repeated `apply()` | Fused `apply_many()` | Speedup |
|---|---:|---:|---:|---:|
| top-k 10 | 2 | 0.00000034 s | 0.00000016 s | 2.05x |
| top-k 10 | 3 | 0.00000039 s | 0.00000020 s | 2.00x |
| top-k 10 | 5 | 0.00000053 s | 0.00000027 s | 1.99x |
| top-k 100 | 2 | 0.00000099 s | 0.00000082 s | 1.20x |
| top-k 100 | 3 | 0.00000132 s | 0.00000118 s | 1.12x |
| top-k 100 | 5 | 0.00000196 s | 0.00000176 s | 1.12x |
| top-k 1,000 | 2 | 0.00000566 s | 0.00000518 s | 1.09x |
| top-k 1,000 | 3 | 0.00000766 s | 0.00000690 s | 1.11x |
| top-k 1,000 | 5 | 0.00001272 s | 0.00001110 s | 1.15x |
| full random | 2 | 0.03789650 s | 0.03876336 s | 0.98x |
| full random | 3 | 0.05278487 s | 0.04317598 s | 1.22x |
| full random | 5 | 0.07618636 s | 0.06010425 s | 1.27x |
| full identity | 2 | 0.01035898 s | 0.00962763 s | 1.08x |
| full identity | 3 | 0.01490276 s | 0.01516220 s | 0.98x |
| full identity | 5 | 0.01954799 s | 0.01916306 s | 1.02x |

## Interpretation

The fused call removes repeated Python method-call and validation overhead,
which explains the roughly `2x` ratio for top-k 10. That ratio should not be
overstated: the absolute saving is about two tenths of a microsecond per call
on this machine. For complete permutations, element traversal and list writes
dominate, and the results are mixed.

`apply_many()` can still be convenient for aligned data, but this experiment
does not establish it as a meaningful performance differentiator. It may stay
private while the top-k design is evaluated; promotion should require a
separate API decision based on real workflow value.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These measurements describe one machine and are not universal guarantees.
