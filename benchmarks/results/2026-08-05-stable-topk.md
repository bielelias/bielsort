# Stable compact top-k research record

Date: 2026-08-05

Status: private prototype; canonical local continuation gate passed. This is
not a public API, release commitment, or universal performance claim.

## Question

Can BielSort select stable smallest/largest indices from a large Python
integer sequence faster and more compactly than equivalent standard-library
approaches, then reuse those indices across parallel sequences?

The prototype uses a native `O(n log k)` stable heap for eligible exact
signed-int64 lists and tuples when `k <= n / 8`. It returns the existing
private immutable 32- or 64-bit permutation buffer. Equal values retain their
original order, including at the top-k boundary.

## Method

- Input sizes: 100,000 and 1,000,000 elements.
- Selected counts: 10, 100, and 1,000.
- Distributions: dense range, random int32, random int64, and heavy duplicates.
- Directions: smallest and largest.
- Samples: median of seven rotated executions per operation.
- Construction baselines: stable full `sorted(range(n), key=...)` and the
  equivalent `heapq.nsmallest()`/`heapq.nlargest()` indices.
- Reuse comparison: build the stable indices once and apply them to three
  parallel Python sequences.
- Correctness: every result is checked against stable full sorting.

Environment: CPython 3.11.2, GCC 12.2.0, Linux x86-64 with glibc 2.36. Results
on other machines may differ.

## Decision

The pre-registered gate passed:

- all results were correct and stable;
- 24/24 one-million-element construction cases exceeded `1.25x` over `heapq`;
- 24/24 one-million-element reuse cases exceeded `1.25x` over `heapq`;
- neither construction nor reuse had a target case more than 10% slower;
- every compact payload was at most half the shallow Python index-list size.

Across the 24 one-million-element target cases, construction was
`1.56x–3.36x` faster than `heapq` and `15.41x–36.99x` faster than fully sorting
all indices. Building and applying the result to three sequences was
`1.55x–3.45x` faster than the equivalent `heapq` flow.

## One-million-element results

`Reuse vs heapq` includes index construction and native application to three
parallel sequences. Payload excludes the small permutation-object header.

| Case | Direction | k | vs heapq | vs full sorted | Reuse vs heapq | Payload |
|---|---|---:|---:|---:|---:|---:|
| dense | smallest | 10 | 3.19x | 34.97x | 3.31x | 40 B |
| dense | largest | 10 | 3.18x | 35.42x | 3.05x | 40 B |
| dense | smallest | 100 | 3.32x | 36.99x | 3.23x | 400 B |
| dense | largest | 100 | 3.09x | 34.40x | 3.10x | 400 B |
| dense | smallest | 1,000 | 3.36x | 30.52x | 3.45x | 4,000 B |
| dense | largest | 1,000 | 3.18x | 31.29x | 3.22x | 4,000 B |
| int32 | smallest | 10 | 2.08x | 20.44x | 2.02x | 40 B |
| int32 | largest | 10 | 2.13x | 21.14x | 2.12x | 40 B |
| int32 | smallest | 100 | 2.14x | 20.80x | 2.14x | 400 B |
| int32 | largest | 100 | 2.13x | 20.57x | 2.12x | 400 B |
| int32 | smallest | 1,000 | 2.20x | 19.62x | 2.26x | 4,000 B |
| int32 | largest | 1,000 | 2.22x | 20.05x | 2.20x | 4,000 B |
| int64 | smallest | 10 | 1.63x | 16.15x | 1.59x | 40 B |
| int64 | largest | 10 | 1.56x | 15.89x | 1.55x | 40 B |
| int64 | smallest | 100 | 1.60x | 15.67x | 1.58x | 400 B |
| int64 | largest | 100 | 1.60x | 15.81x | 1.57x | 400 B |
| int64 | smallest | 1,000 | 1.75x | 15.65x | 1.73x | 4,000 B |
| int64 | largest | 1,000 | 1.70x | 15.41x | 1.70x | 4,000 B |
| heavy duplicates | smallest | 10 | 3.33x | 19.26x | 3.21x | 40 B |
| heavy duplicates | largest | 10 | 3.09x | 18.24x | 3.15x | 40 B |
| heavy duplicates | smallest | 100 | 3.28x | 19.04x | 3.24x | 400 B |
| heavy duplicates | largest | 100 | 3.13x | 18.38x | 3.15x | 400 B |
| heavy duplicates | smallest | 1,000 | 3.34x | 18.04x | 3.37x | 4,000 B |
| heavy duplicates | largest | 1,000 | 3.23x | 17.56x | 3.17x | 4,000 B |

For comparison, the compact payload is 40, 400, or 4,000 bytes for the three
`k` values. The corresponding shallow Python index lists are 184, 920, and
8,856 bytes before the referenced Python integer objects are counted; including
those objects, the measured sizes are 464, 3,720, and 36,856 bytes.

## Limits and next gate

- These are deterministic synthetic distributions on one local machine, not
  production workload evidence.
- The optimized contract is currently exact signed-int64 Python values in a
  reusable sequence. Generic values and large `k` use the compatible full
  argsort path.
- The private API needs sanitizer and supported-platform CI validation before
  any public naming or promotion review.
- A future public proposal must specify return type, errors, typing, naming,
  and the relationship to `sorted()`, `heapq`, and the compact permutation.

Raw configuration, all 48 construction and reuse cases, every timing sample,
strategies, storage measurements, and environment metadata are retained in
[`2026-08-05-stable-topk.json`](2026-08-05-stable-topk.json).

## Reproduction

```bash
python benchmarks/topk_prototype.py \
  -n 100000 1000000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output stable-topk.json
```
