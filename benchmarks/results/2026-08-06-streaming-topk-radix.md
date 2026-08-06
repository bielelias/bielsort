# Bounded-memory streaming top-k result

- Protocol commit: `91e851f`
- Implementation commit: `0b96727`
- Canonical configuration: `True`
- Decision: `FAIL`

## Timing

| Domain | k | Direction | heapq (s) | BielSort (s) | Paired speedup | Route |
|---|---:|---|---:|---:|---:|---|
| natural-int64 | 100 | smallest | 0.152063 | 0.153761 | 1.00x | native-stream-int64 |
| natural-int64 | 100 | largest | 0.157477 | 0.156257 | 1.00x | native-stream-int64 |
| natural-int64 | 10000 | smallest | 0.189424 | 0.180538 | 1.07x | native-stream-int64 |
| natural-int64 | 10000 | largest | 0.201034 | 0.182529 | 1.11x | native-stream-int64 |
| natural-int64 | 100000 | smallest | 0.414448 | 0.245112 | 1.69x | native-stream-int64 |
| natural-int64 | 100000 | largest | 0.418802 | 0.245593 | 1.70x | native-stream-int64 |
| keyed-int64 | 100 | smallest | 0.205969 | 0.197334 | 1.05x | native-stream-int64 |
| keyed-int64 | 100 | largest | 0.206481 | 0.196442 | 1.05x | native-stream-int64 |
| keyed-int64 | 10000 | smallest | 0.248483 | 0.219775 | 1.13x | native-stream-int64 |
| keyed-int64 | 10000 | largest | 0.270879 | 0.240743 | 1.14x | native-stream-int64 |
| keyed-int64 | 100000 | smallest | 0.554497 | 0.297333 | 1.80x | native-stream-int64 |
| keyed-int64 | 100000 | largest | 0.619661 | 0.318079 | 1.87x | native-stream-int64 |
| keyed-huge-int | 100 | smallest | 0.313435 | 0.301099 | 1.05x | native-stream-generic |
| keyed-huge-int | 100 | largest | 0.307147 | 0.294642 | 1.05x | native-stream-generic |
| keyed-huge-int | 10000 | smallest | 0.347630 | 0.321101 | 1.08x | native-stream-generic |
| keyed-huge-int | 10000 | largest | 0.357523 | 0.338560 | 1.05x | native-stream-generic |
| keyed-huge-int | 100000 | smallest | 0.556739 | 0.489161 | 1.19x | native-stream-generic |
| keyed-huge-int | 100000 | largest | 0.792582 | 0.726859 | 1.06x | native-stream-generic |
| keyed-string | 100 | smallest | 0.602439 | 0.594138 | 0.99x | native-stream-generic |
| keyed-string | 100 | largest | 0.601340 | 0.593442 | 1.00x | native-stream-generic |
| keyed-string | 10000 | smallest | 0.627746 | 0.600612 | 1.02x | native-stream-generic |
| keyed-string | 10000 | largest | 0.544930 | 0.511885 | 1.05x | native-stream-generic |
| keyed-string | 100000 | smallest | 0.929650 | 0.824064 | 1.11x | native-stream-generic |
| keyed-string | 100000 | largest | 0.924415 | 0.860407 | 1.07x | native-stream-generic |

## Isolated incremental peak RSS

Linux RSS was sampled by the parent process every 0.5 ms after a worker-ready checkpoint.

| Domain | k | BielSort | heapq | Materializing façade | BielSort/heapq | BielSort/façade |
|---|---:|---:|---:|---:|---:|---:|
| keyed-int64 | 100 | 0.12 MiB | 0.25 MiB | 130.38 MiB | 0.50x | 0.00x |
| keyed-int64 | 10000 | 1.62 MiB | 2.50 MiB | 130.62 MiB | 0.65x | 0.01x |
| keyed-int64 | 100000 | 14.75 MiB | 23.76 MiB | 134.77 MiB | 0.62x | 0.11x |
| keyed-string | 100 | 0.00 MiB | 0.25 MiB | 160.88 MiB | 0.00x | 0.00x |
| keyed-string | 10000 | 1.88 MiB | 2.88 MiB | 161.38 MiB | 0.65x | 0.01x |
| keyed-string | 100000 | 17.75 MiB | 26.81 MiB | 165.62 MiB | 0.66x | 0.11x |

## Gate summary

- Minimum paired speedup: `0.99x`
- Signed-int64 target cases: `7/12`
- Generic near-parity cases: `12/12`
- semantic_probes_passed: `PASS`
- minimum_speedup_passed: `PASS`
- exact_target_passed: `FAIL`
- generic_target_passed: `PASS`
- heapq_memory_passed: `PASS`
- materializing_facade_memory_passed: `PASS`

These measurements are synthetic local evidence, not universal
performance guarantees or evidence of external demand. Passing
does not expose an API or authorize a package publication.
