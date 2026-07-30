# Counting Sort memory optimization — 2026-07-30

## Revisions

- Baseline: [`2081a78`](https://github.com/bielelias/bielsort/commit/2081a78)
- Optimized native core:
  [`ad57cd1`](https://github.com/bielelias/bielsort/commit/ad57cd1)

The candidate was measured on the same Linux x86-64 environment documented in
the [full 2026-07-30 report](2026-07-30-linux-x86_64.md).

## Method

Both revisions were measured with:

```bash
python benchmarks/memory.py -n 1000000 -r 5 --cases dense
```

Each sample ran in an isolated child process. The table reports medians of five
samples and incremental peak RSS after input generation.

## Result

| API | Baseline time | Optimized time | Time change | Baseline peak | Optimized peak | Peak change |
|---|---:|---:|---:|---:|---:|---:|
| Biel new list | 0.03723 s | 0.03223 s | -13.4% | 41.99 MiB | 26.73 MiB | -36.3% |
| Biel in-place | 0.04205 s | 0.02876 s | -31.6% | 34.39 MiB | 19.05 MiB | -44.6% |

The optimization met the predefined acceptance criteria:

- at least 20% lower peak memory for both APIs;
- no execution-time regression above 5%;
- stable ordering and API compatibility preserved;
- regular and deterministic stress tests passed;
- AddressSanitizer and UndefinedBehaviorSanitizer tests passed.

The machine was not isolated and CPU frequency was not pinned. Timing changes
should therefore be treated as measurements of this environment rather than
universal guarantees. The large memory margin is the primary result.

## Implementation

The Counting Sort path now compacts normalized keys to `uint32_t`, releases
the temporary 16-byte-per-element entry array, and then allocates an
8-byte-per-element object-pointer output. These phases avoid keeping two full
entry arrays alive simultaneously. The Radix Sort representation and fallback
behavior remain unchanged.
