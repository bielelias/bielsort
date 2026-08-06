# Bounded-memory streaming top-k result

- Protocol commit: `91e851f`
- Implementation commit: `73d43c2`
- Canonical configuration: `True`
- Decision: `FAIL`

## Timing

| Domain | k | Direction | heapq (s) | BielSort (s) | Paired speedup | Route |
|---|---:|---|---:|---:|---:|---|
| natural-int64 | 100 | smallest | 0.166936 | 0.162380 | 1.00x | native-stream-int64 |
| natural-int64 | 100 | largest | 0.173016 | 0.170534 | 1.03x | native-stream-int64 |
| natural-int64 | 10000 | smallest | 0.212635 | 0.208780 | 1.12x | native-stream-int64 |
| natural-int64 | 10000 | largest | 0.254144 | 0.227766 | 1.11x | native-stream-int64 |
| natural-int64 | 100000 | smallest | 0.481586 | 0.274970 | 1.75x | native-stream-int64 |
| natural-int64 | 100000 | largest | 0.504415 | 0.279639 | 1.80x | native-stream-int64 |
| keyed-int64 | 100 | smallest | 0.228249 | 0.216638 | 1.05x | native-stream-int64 |
| keyed-int64 | 100 | largest | 0.228150 | 0.212378 | 1.07x | native-stream-int64 |
| keyed-int64 | 10000 | smallest | 0.274260 | 0.242152 | 1.13x | native-stream-int64 |
| keyed-int64 | 10000 | largest | 0.289278 | 0.250438 | 1.14x | native-stream-int64 |
| keyed-int64 | 100000 | smallest | 0.556863 | 0.310068 | 1.79x | native-stream-int64 |
| keyed-int64 | 100000 | largest | 0.559827 | 0.317016 | 1.78x | native-stream-int64 |
| keyed-huge-int | 100 | smallest | 0.321799 | 0.308450 | 1.07x | native-stream-generic |
| keyed-huge-int | 100 | largest | 0.311651 | 0.298698 | 1.04x | native-stream-generic |
| keyed-huge-int | 10000 | smallest | 0.347988 | 0.325583 | 1.08x | native-stream-generic |
| keyed-huge-int | 10000 | largest | 0.364167 | 0.337496 | 1.08x | native-stream-generic |
| keyed-huge-int | 100000 | smallest | 0.644483 | 0.502802 | 1.30x | native-stream-generic |
| keyed-huge-int | 100000 | largest | 0.634191 | 0.518686 | 1.21x | native-stream-generic |
| keyed-string | 100 | smallest | 0.490201 | 0.479633 | 1.02x | native-stream-generic |
| keyed-string | 100 | largest | 0.469284 | 0.455029 | 1.03x | native-stream-generic |
| keyed-string | 10000 | smallest | 0.551461 | 0.518878 | 1.06x | native-stream-generic |
| keyed-string | 10000 | largest | 0.486681 | 0.458960 | 1.05x | native-stream-generic |
| keyed-string | 100000 | smallest | 1.091912 | 0.913194 | 1.20x | native-stream-generic |
| keyed-string | 100000 | largest | 1.100400 | 0.902814 | 1.19x | native-stream-generic |

## Isolated incremental peak RSS

Linux RSS was sampled by the parent process every 0.5 ms after a worker-ready checkpoint.

| Domain | k | BielSort | heapq | Materializing façade | BielSort/heapq | BielSort/façade |
|---|---:|---:|---:|---:|---:|---:|
| keyed-int64 | 100 | 0.00 MiB | 0.25 MiB | 130.12 MiB | 0.00x | 0.00x |
| keyed-int64 | 10000 | 1.88 MiB | 2.50 MiB | 130.62 MiB | 0.75x | 0.01x |
| keyed-int64 | 100000 | 18.09 MiB | 23.79 MiB | 134.61 MiB | 0.76x | 0.13x |
| keyed-string | 100 | 0.12 MiB | 0.25 MiB | 160.75 MiB | 0.50x | 0.00x |
| keyed-string | 10000 | 2.25 MiB | 3.00 MiB | 161.25 MiB | 0.75x | 0.01x |
| keyed-string | 100000 | 21.47 MiB | 26.78 MiB | 165.41 MiB | 0.80x | 0.13x |

## Gate summary

- Minimum paired speedup: `1.00x`
- Signed-int64 target cases: `8/12`
- Generic near-parity cases: `12/12`
- semantic_probes_passed: `PASS`
- minimum_speedup_passed: `PASS`
- exact_target_passed: `PASS`
- generic_target_passed: `PASS`
- heapq_memory_passed: `FAIL`
- materializing_facade_memory_passed: `PASS`

These measurements are synthetic local evidence, not universal
performance guarantees or evidence of external demand. Passing
does not expose an API or authorize a package publication.
