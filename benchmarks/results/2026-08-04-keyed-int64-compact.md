# Compact keyed-int64 Radix buffers — 2026-08-04

## Decision

**Keep the compact layout and proceed to structured strategy diagnostics.**

The compact layout reduced the Radix prototype's incremental peak RSS by about
20% on the wide-range cases while preserving its speed advantage over
`sorted(key=...)`. Stable Counting Sort also improved on the dense case. The
public BielSort API and published 0.1 package remain unchanged.

## Change

The initial Radix prototype allocated two arrays of 16-byte entries, each
containing a Python object pointer and a `uint64` key. Together with the result
list, the principal variable-size storage was approximately 40 bytes per
record.

The compact implementation now uses:

- the private result list as the current object-pointer input;
- one reusable object-pointer output buffer;
- two `uint64` key buffers.

After each stable Radix pass, the output pointers are copied into the private
result list and the key buffers are swapped. The principal variable-size
storage is approximately 32 bytes per record. The list is not visible to user
code during this work, and the pointer permutation does not change aggregate
reference ownership.

## Validation

- All 42 functional and stress tests passed.
- ASan and UBSan passed all 42 tests.
- `key` is still called exactly once per object.
- Input order is preserved for equal keys.
- Object identity and the original input list are preserved.
- Timing order alternates deterministically between the candidates.
- Peak RSS uses three isolated processes per algorithm and distribution.

Environment and workload generation match the
[initial keyed-int64 report](2026-08-04-keyed-int64-prototype.md).

## Median incremental peak RSS at one million records

| Distribution | `sorted(key=...)` | Initial prototype | Compact prototype | Compact vs initial |
|---|---:|---:|---:|---:|
| dense | 24.87 MiB | 26.68 MiB | 22.72 MiB | -14.8% |
| timestamp | 24.75 MiB | 38.15 MiB | 30.63 MiB | -19.7% |
| int32 | 26.74 MiB | 38.18 MiB | 30.60 MiB | -19.9% |
| int64 | 26.81 MiB | 38.22 MiB | 30.57 MiB | -20.0% |
| nearly sorted | 23.05 MiB | 26.69 MiB | 26.69 MiB | 0.0% |

The nearly-sorted proxy used Counting Sort, whose count table and output buffer
remain the peak phase. It therefore does not benefit from the compact Radix
layout. The dense Counting case measured lower, but its extraction and sorting
phases have similar theoretical peaks; that improvement needs cross-platform
replication before becoming a memory claim.

## Median time

Speedups above `1.00x` favor the compact prototype.

| Records | Distribution | `sorted(key=...)` | Compact prototype | Speedup |
|---:|---|---:|---:|---:|
| 10,000 | dense | 0.001371 s | 0.000315 s | 4.35x |
| 10,000 | timestamp | 0.001493 s | 0.000414 s | 3.61x |
| 10,000 | int32 | 0.001570 s | 0.000466 s | 3.37x |
| 10,000 | int64 | 0.001576 s | 0.000625 s | 2.52x |
| 10,000 | nearly sorted | 0.000195 s | 0.000233 s | 0.84x |
| 100,000 | dense | 0.021062 s | 0.004121 s | 5.11x |
| 100,000 | timestamp | 0.022069 s | 0.005133 s | 4.30x |
| 100,000 | int32 | 0.024068 s | 0.005628 s | 4.28x |
| 100,000 | int64 | 0.023758 s | 0.008042 s | 2.95x |
| 100,000 | nearly sorted | 0.003837 s | 0.004411 s | 0.87x |
| 1,000,000 | dense | 0.307525 s | 0.052663 s | 5.84x |
| 1,000,000 | timestamp | 0.338645 s | 0.060266 s | 5.62x |
| 1,000,000 | int32 | 0.375608 s | 0.060982 s | 6.16x |
| 1,000,000 | int64 | 0.353499 s | 0.090038 s | 3.93x |
| 1,000,000 | nearly sorted | 0.054294 s | 0.033330 s | 1.63x |

Separate before/after runs should not be treated as cycle-accurate A/B
measurements. The important result is that all four large disordered cases
remain well above the pre-registered `1.50x` continuation gate while the wide
Radix distributions reduce peak RSS consistently.

## Honest limitations

- Wide-range Radix still used 14%-24% more incremental peak RSS than
  `sorted(key=...)` on this machine.
- The prototype was measured only on local synthetic records and CPython 3.11.
- Small nearly-sorted records remain a known loss.
- This is evidence of engineering potential, not external demand or revenue.
- The historical initial buffer implementation is retained as a raw benchmark
  baseline, but the current source contains the compact follow-up.

## Next gate

> Follow-up: the
> [structured diagnostics report](2026-08-04-keyed-int64-diagnostics.md)
> completed this gate and defined the safe boundary for a native-memory guard.

The next research step is a structured diagnostic result containing:

- selected strategy and reason;
- element count and key domain;
- Radix pass count;
- conservative auxiliary-memory estimate;
- stability and key-call guarantees;
- explicit eligibility or failure reason.

Memory-budget behavior must be designed so that falling back never evaluates a
user key twice.

## Reproduction

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python benchmarks/keyed_int64_prototype.py \
  -n 10000 100000 1000000 \
  -r 5 \
  --memory-repetitions 3 \
  --json-output benchmarks/results/2026-08-04-keyed-int64-compact.json
```
