# Bounded-memory streaming top-k result

- Protocol commit: `91e851f`
- Implementation commit: `ddb8ff2`
- Canonical configuration: `True`
- Decision: `FAIL`

## Timing

| Domain | k | Direction | heapq (s) | BielSort (s) | Paired speedup | Route |
|---|---:|---|---:|---:|---:|---|
| natural-int64 | 100 | smallest | 0.156101 | 0.152880 | 1.02x | native-stream-int64 |
| natural-int64 | 100 | largest | 0.156191 | 0.154137 | 1.02x | native-stream-int64 |
| natural-int64 | 10000 | smallest | 0.190987 | 0.174362 | 1.09x | native-stream-int64 |
| natural-int64 | 10000 | largest | 0.201903 | 0.179556 | 1.13x | native-stream-int64 |
| natural-int64 | 100000 | smallest | 0.414337 | 0.244831 | 1.69x | native-stream-int64 |
| natural-int64 | 100000 | largest | 0.416383 | 0.244543 | 1.70x | native-stream-int64 |
| keyed-int64 | 100 | smallest | 0.204481 | 0.194726 | 1.05x | native-stream-int64 |
| keyed-int64 | 100 | largest | 0.205060 | 0.197363 | 1.06x | native-stream-int64 |
| keyed-int64 | 10000 | smallest | 0.248081 | 0.221060 | 1.12x | native-stream-int64 |
| keyed-int64 | 10000 | largest | 0.255924 | 0.222183 | 1.14x | native-stream-int64 |
| keyed-int64 | 100000 | smallest | 0.465915 | 0.264405 | 1.77x | native-stream-int64 |
| keyed-int64 | 100000 | largest | 0.476767 | 0.274325 | 1.74x | native-stream-int64 |
| keyed-huge-int | 100 | smallest | 0.272606 | 0.260616 | 1.05x | native-stream-generic |
| keyed-huge-int | 100 | largest | 0.283417 | 0.270966 | 1.05x | native-stream-generic |
| keyed-huge-int | 10000 | smallest | 0.319239 | 0.296997 | 1.07x | native-stream-generic |
| keyed-huge-int | 10000 | largest | 0.329899 | 0.312292 | 1.08x | native-stream-generic |
| keyed-huge-int | 100000 | smallest | 0.532672 | 0.462444 | 1.15x | native-stream-generic |
| keyed-huge-int | 100000 | largest | 0.532825 | 0.473107 | 1.13x | native-stream-generic |
| keyed-string | 100 | smallest | 0.425990 | 0.407515 | 1.04x | native-stream-generic |
| keyed-string | 100 | largest | 0.425867 | 0.413896 | 1.03x | native-stream-generic |
| keyed-string | 10000 | smallest | 0.480059 | 0.460534 | 1.04x | native-stream-generic |
| keyed-string | 10000 | largest | 0.473855 | 0.457434 | 1.04x | native-stream-generic |
| keyed-string | 100000 | smallest | 0.935978 | 0.837846 | 1.12x | native-stream-generic |
| keyed-string | 100000 | largest | 0.936351 | 0.833993 | 1.12x | native-stream-generic |

## Isolated incremental peak RSS

Linux RSS was sampled by the parent process every 0.5 ms after a worker-ready checkpoint.

| Domain | k | BielSort | heapq | Materializing façade | BielSort/heapq | BielSort/façade |
|---|---:|---:|---:|---:|---:|---:|
| keyed-int64 | 100 | 0.12 MiB | 0.25 MiB | 130.38 MiB | 0.50x | 0.00x |
| keyed-int64 | 10000 | 1.50 MiB | 2.50 MiB | 130.75 MiB | 0.60x | 0.01x |
| keyed-int64 | 100000 | 14.75 MiB | 23.75 MiB | 134.75 MiB | 0.62x | 0.11x |
| keyed-string | 100 | 0.00 MiB | 0.25 MiB | 161.00 MiB | 0.00x | 0.00x |
| keyed-string | 10000 | 1.88 MiB | 3.00 MiB | 161.50 MiB | 0.62x | 0.01x |
| keyed-string | 100000 | 17.88 MiB | 26.75 MiB | 165.55 MiB | 0.67x | 0.11x |

## Gate summary

- Minimum paired speedup: `1.02x`
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
