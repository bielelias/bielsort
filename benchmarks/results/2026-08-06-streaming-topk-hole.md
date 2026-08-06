# Bounded-memory streaming top-k result

- Protocol commit: `91e851f`
- Implementation commit: `e56c96d`
- Canonical configuration: `True`
- Decision: `FAIL`

## Timing

| Domain | k | Direction | heapq (s) | BielSort (s) | Paired speedup | Route |
|---|---:|---|---:|---:|---:|---|
| natural-int64 | 100 | smallest | 0.169747 | 0.170425 | 0.96x | native-stream-int64 |
| natural-int64 | 100 | largest | 0.165830 | 0.168670 | 0.98x | native-stream-int64 |
| natural-int64 | 10000 | smallest | 0.242269 | 0.220382 | 1.08x | native-stream-int64 |
| natural-int64 | 10000 | largest | 0.255344 | 0.220924 | 1.14x | native-stream-int64 |
| natural-int64 | 100000 | smallest | 0.456157 | 0.262768 | 1.74x | native-stream-int64 |
| natural-int64 | 100000 | largest | 0.501487 | 0.268936 | 1.83x | native-stream-int64 |
| keyed-int64 | 100 | smallest | 0.230504 | 0.217820 | 1.05x | native-stream-int64 |
| keyed-int64 | 100 | largest | 0.233637 | 0.223413 | 1.05x | native-stream-int64 |
| keyed-int64 | 10000 | smallest | 0.270177 | 0.235425 | 1.14x | native-stream-int64 |
| keyed-int64 | 10000 | largest | 0.276239 | 0.242345 | 1.13x | native-stream-int64 |
| keyed-int64 | 100000 | smallest | 0.534240 | 0.290313 | 1.84x | native-stream-int64 |
| keyed-int64 | 100000 | largest | 0.562443 | 0.295498 | 1.90x | native-stream-int64 |
| keyed-huge-int | 100 | smallest | 0.308286 | 0.299837 | 1.03x | native-stream-generic |
| keyed-huge-int | 100 | largest | 0.323130 | 0.300588 | 1.07x | native-stream-generic |
| keyed-huge-int | 10000 | smallest | 0.347886 | 0.327410 | 1.07x | native-stream-generic |
| keyed-huge-int | 10000 | largest | 0.374804 | 0.348465 | 1.06x | native-stream-generic |
| keyed-huge-int | 100000 | smallest | 0.590301 | 0.538027 | 1.09x | native-stream-generic |
| keyed-huge-int | 100000 | largest | 0.624034 | 0.536190 | 1.14x | native-stream-generic |
| keyed-string | 100 | smallest | 0.473192 | 0.461329 | 1.03x | native-stream-generic |
| keyed-string | 100 | largest | 0.492462 | 0.467382 | 1.03x | native-stream-generic |
| keyed-string | 10000 | smallest | 0.563931 | 0.564308 | 1.04x | native-stream-generic |
| keyed-string | 10000 | largest | 0.566052 | 0.535320 | 1.08x | native-stream-generic |
| keyed-string | 100000 | smallest | 1.133230 | 0.986606 | 1.13x | native-stream-generic |
| keyed-string | 100000 | largest | 1.181287 | 1.009389 | 1.15x | native-stream-generic |

## Isolated incremental peak RSS

Linux RSS was sampled by the parent process every 0.5 ms after a worker-ready checkpoint.

| Domain | k | BielSort | heapq | Materializing façade | BielSort/heapq | BielSort/façade |
|---|---:|---:|---:|---:|---:|---:|
| keyed-int64 | 100 | 0.12 MiB | 0.38 MiB | 130.38 MiB | 0.33x | 0.00x |
| keyed-int64 | 10000 | 1.71 MiB | 2.62 MiB | 130.50 MiB | 0.65x | 0.01x |
| keyed-int64 | 100000 | 14.88 MiB | 23.75 MiB | 134.61 MiB | 0.63x | 0.11x |
| keyed-string | 100 | 0.12 MiB | 0.25 MiB | 160.88 MiB | 0.50x | 0.00x |
| keyed-string | 10000 | 1.88 MiB | 3.00 MiB | 161.38 MiB | 0.62x | 0.01x |
| keyed-string | 100000 | 17.88 MiB | 26.76 MiB | 165.34 MiB | 0.67x | 0.11x |

## Gate summary

- Minimum paired speedup: `0.96x`
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
