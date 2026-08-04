# Signed-int64 keyed-object prototype — 2026-08-04

> Follow-up: the
> [compact Radix-buffer report](2026-08-04-keyed-int64-compact.md) reduced
> wide-range peak RSS by about 20% while preserving the speed signal. The
> current research source contains that compact implementation.

## Decision

**Continue the research, but do not publish this as a 0.2 API yet.**

The prototype passed the pre-registered speed gate on all four large,
disordered cases. Its incremental peak RSS stayed below the allowed `2.00x`
baseline, but it used more memory than `sorted(key=...)` in every measured
case. The result supports native keyed-object sorting as a performance
direction; it does not yet support a lower-memory claim or prove market demand.

## Contract validated

The research-only native entry point:

- returns a new list and leaves the input unchanged;
- accepts arbitrary Python objects;
- requires an exact signed-64-bit integer key;
- calls `key` exactly once per object, in input order;
- preserves object identity;
- preserves the encounter order of equal keys;
- raises instead of silently evaluating an unsupported key twice.

The public `bielsort` API and version remain unchanged.

## Environment

- CPU: 13th Gen Intel Core i5-1334U, 12 logical CPUs
- RAM: 7.4 GiB
- OS: Linux x86-64, kernel 6.7.0-keepos
- Python: CPython 3.11.2
- Compiler: GCC 12.2.0 with `-O3`
- Repetitions: five for time, three isolated processes for peak RSS
- Input size for memory: 1,000,000 records
- Native sanitizers: all 42 tests passed with ASan and UBSan
- Timing order: deterministically alternated between both algorithms

The machine had other applications running. Ratios within the same local run
are more useful than absolute seconds, and these numbers are not universal
performance guarantees.

## Median time

Speedups above `1.00x` favor the prototype.

| Records | Distribution | `sorted(key=...)` | Keyed prototype | Speedup |
|---:|---|---:|---:|---:|
| 10,000 | dense | 0.001335 s | 0.000329 s | 4.06x |
| 10,000 | timestamp | 0.001480 s | 0.000403 s | 3.67x |
| 10,000 | int32 | 0.001554 s | 0.000435 s | 3.58x |
| 10,000 | int64 | 0.001571 s | 0.000622 s | 2.53x |
| 10,000 | nearly sorted | 0.000205 s | 0.000245 s | 0.84x |
| 100,000 | dense | 0.021789 s | 0.004113 s | 5.30x |
| 100,000 | timestamp | 0.021843 s | 0.005293 s | 4.13x |
| 100,000 | int32 | 0.022997 s | 0.006108 s | 3.77x |
| 100,000 | int64 | 0.023568 s | 0.007321 s | 3.22x |
| 100,000 | nearly sorted | 0.004788 s | 0.003419 s | 1.40x |
| 1,000,000 | dense | 0.307051 s | 0.047685 s | 6.44x |
| 1,000,000 | timestamp | 0.330274 s | 0.063107 s | 5.23x |
| 1,000,000 | int32 | 0.368528 s | 0.063986 s | 5.76x |
| 1,000,000 | int64 | 0.352461 s | 0.092306 s | 3.82x |
| 1,000,000 | nearly sorted | 0.057169 s | 0.034934 s | 1.64x |

At one million records, the selected native strategies were:

- dense: stable Counting Sort;
- timestamp: four-pass stable Radix Sort;
- int32: three-pass stable Radix Sort;
- int64: six-pass stable Radix Sort;
- nearly sorted: stable Counting Sort because the key range was dense.

## Median incremental peak RSS

Ratios below `1.00x` would favor the prototype. RSS includes the new result
list and native temporary buffers above the already-live input records.

| Distribution | `sorted(key=...)` | Keyed prototype | Prototype / baseline |
|---|---:|---:|---:|
| dense | 24.90 MiB | 26.68 MiB | 1.07x |
| timestamp | 24.70 MiB | 38.15 MiB | 1.54x |
| int32 | 26.82 MiB | 38.18 MiB | 1.42x |
| int64 | 26.75 MiB | 38.22 MiB | 1.43x |
| nearly sorted | 23.04 MiB | 26.69 MiB | 1.16x |

The Counting path is close to the baseline. The Radix path keeps two native
`(object pointer, uint64 key)` buffers and therefore has the clearest
reduced-memory opportunity.

## Pre-registered gate evaluation

The gate required at least two large disordered cases at `1.50x` speedup while
remaining below `2.00x` the baseline incremental peak RSS. Dense, timestamp,
int32, and int64 all passed. Correctness gates also passed.

The alternative gate of 30% lower memory did not pass. BielSort must not claim
that this prototype uses less memory than Python's keyed Timsort.

## Measurement corrections

Two invalid peak-RSS attempts were discarded before this report:

1. Data construction temporarily retained both a key list and the record list,
   making the construction high-water mark larger than the sorting peak.
   Construction now streams keys directly into records.
2. The supervisor initially ran time tests before memory workers. On Linux,
   `ru_maxrss` can retain a high-water mark across process execution, causing
   workers to report false zero increments. Isolated memory workers now run
   before the supervisor creates any large workload.

The versioned JSON contains only the corrected run.

## Remaining evidence before a public API

1. Reduce Radix peak memory without erasing the measured speed advantage.
   Completed in the compact-buffer follow-up.
2. Add a structured plan containing strategy, pass count, eligibility, and a
   conservative auxiliary-memory estimate.
3. Define a pre-execution memory-budget policy that does not call `key` twice.
4. Measure keyed records from public, documented datasets.
5. Compare against relevant third-party alternatives using equivalent
   semantics and including conversion costs.
6. Repeat on multiple operating systems and current CPython versions.

Synthetic records demonstrate a technical opportunity, not adoption,
customer willingness to pay, or a universal advantage.

## Reproduction

Build an editable native extension, then run:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python benchmarks/keyed_int64_prototype.py \
  -n 10000 100000 1000000 \
  -r 5 \
  --memory-repetitions 3 \
  --json-output benchmarks/results/2026-08-04-keyed-int64-prototype.json
```
