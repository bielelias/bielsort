# Corrected hosted validation and fallback investigation — 2026-07-31

This report records the investigation of BielSort's nearly ordered Timsort
fallback and supersedes the performance ratios in the earlier
[GitHub-hosted snapshot](2026-07-31-github-hosted.md). Installation,
correctness, and strategy-selection findings from that snapshot remain valid.

> [!IMPORTANT]
> The earlier benchmark retained each result until the following timed
> assignment. Destroying the previous list could therefore be charged to a
> different algorithm. The corrected harness validates and releases every
> output before another timer starts.

All runs installed the public `bielsort==0.1.0` binary wheel from PyPI and
verified that imports did not resolve to the repository checkout.

## What the bug changed

The most contradictory result was on the Ubuntu CPython 3.14 Timsort control.
After correcting result lifetimes and increasing repetitions, the apparent
large loss at 100,000 elements and large win at 1,000,000 both disappeared.

| n | Measurement | `sorted()` | BielSort | BielSort / `sorted()` |
|---:|---|---:|---:|---:|
| 100,000 | Earlier, contaminated | 0.876 ms | 2.138 ms | 0.41× |
| 100,000 | Corrected, 7 runs | 0.778 ms | 0.784 ms | 0.99× |
| 1,000,000 | Earlier, contaminated | 28.530 ms | 15.689 ms | 1.82× |
| 1,000,000 | Corrected, 7 runs | 12.300 ms | 12.964 ms | 0.95× |

This shows why a benchmark must control object lifetime, not only input
generation, garbage collection, and algorithm order.

## Corrected cross-platform summary

The complete corrected matrix used seven interleaved runs on five hosted
environments. Ratios are within-runner medians; values above `1.00×` favor
BielSort.

| n | Workload | Reports | Native path | BielSort fastest | Median vs `sorted()` | Median vs NumPy E2E |
|---:|---|---:|---:|---:|---:|---:|
| 100,000 | event timestamps | 5 | 5/5 | 5/5 | 7.50× | 3.11× |
| 100,000 | mostly ordered offsets | 5 | 0/5 | 1/5 | 0.99× | 4.28× |
| 100,000 | signed record IDs | 5 | 5/5 | 5/5 | 5.11× | 1.94× |
| 1,000,000 | event timestamps | 5 | 5/5 | 5/5 | 14.13× | 3.98× |
| 1,000,000 | mostly ordered offsets | 5 | 0/5 | 3/5 | 1.01× | 3.81× |
| 1,000,000 | signed record IDs | 5 | 5/5 | 5/5 | 7.55× | 2.29× |

The native-path winner pattern remained 20/20. The fallback control became a
near tie, as expected because both APIs ultimately call CPython's Timsort.

### Corrected Timsort controls

| Runner | n | `sorted()` | BielSort | Ratio | Winner |
|---|---:|---:|---:|---:|---|
| macOS ARM, Py3.11 | 100,000 | 0.999 ms | 0.923 ms | 1.08× | BielSort |
| macOS Intel, Py3.11 | 100,000 | 1.812 ms | 1.957 ms | 0.93× | `sorted()` |
| Ubuntu, Py3.11 | 100,000 | 0.829 ms | 0.843 ms | 0.98× | `sorted()` |
| Ubuntu, Py3.14 | 100,000 | 0.778 ms | 0.784 ms | 0.99× | `sorted()` |
| Windows, Py3.11 | 100,000 | 1.373 ms | 1.383 ms | 0.99× | `sorted()` |
| macOS ARM, Py3.11 | 1,000,000 | 19.321 ms | 19.014 ms | 1.02× | BielSort |
| macOS Intel, Py3.11 | 1,000,000 | 33.306 ms | 31.616 ms | 1.05× | BielSort |
| Ubuntu, Py3.11 | 1,000,000 | 13.515 ms | 13.889 ms | 0.97× | `sorted()` |
| Ubuntu, Py3.14 | 1,000,000 | 12.300 ms | 12.964 ms | 0.95× | `sorted()` |
| Windows, Py3.11 | 1,000,000 | 18.202 ms | 17.961 ms | 1.01× | BielSort |

Hosted-runner noise is larger than the expected dispatcher cost in several of
these rows. The alternating winners are not evidence that one Timsort wrapper
is generally faster.

## Isolated fallback profile

A second workflow measured copies, equivalent new-list operations, dispatcher
cost, and in-place calls separately. It retained all raw nanosecond samples and
used 21 deterministic interleaved repetitions for ordered, adjacent-swap, and
long-distance-swap inputs.

| Python | n | BielSort minus `sorted()` range | Speedup range |
|---:|---:|---:|---:|
| 3.11 | 10,000 | +0.0008 to +0.0015 ms | 0.969× to 0.983× |
| 3.11 | 100,000 | +0.0019 to +0.0050 ms | 0.989× to 0.997× |
| 3.11 | 1,000,000 | −0.0948 to +0.0281 ms | 0.995× to 1.007× |
| 3.14 | 10,000 | +0.0001 to +0.0006 ms | 0.978× to 0.998× |
| 3.14 | 100,000 | −0.0015 to +0.0011 ms | 0.996× to 1.005× |
| 3.14 | 1,000,000 | −0.0467 to +0.0501 ms | 0.989× to 1.004× |

The 100,000-element CPython 3.14 anomaly was not reproduced. At one million
elements, the sign of sub-0.1 ms differences changed across input patterns,
which is consistent with noise around equivalent Timsort work.

## Reviewed conclusions

1. The anomaly was a benchmark-lifetime defect, not a BielSort regression.
2. No native selector or sorting heuristic should change based on the old
   fallback ratios.
3. The public wheel remained correct and portable in every tested environment.
4. BielSort's native Counting and Radix paths still won all 20 comparisons on
   these transparent synthetic proxies.
5. Nearly ordered inputs should be described as Timsort-compatible behavior,
   not a BielSort acceleration claim.
6. These synthetic results do not establish real user demand or production
   capacity. Application benchmarks remain necessary before adoption.

## Reproduction and audit trail

- Issue: [#18](https://github.com/bielelias/bielsort/issues/18)
- Benchmark correction: [PR #20](https://github.com/bielelias/bielsort/pull/20)
- Corrected fallback profile, 21 repetitions:
  [run 30672452418](https://github.com/bielelias/bielsort/actions/runs/30672452418)
- Corrected five-runner workload matrix, 7 repetitions:
  [run 30672513742](https://github.com/bielelias/bielsort/actions/runs/30672513742)
- Profiler: `benchmarks/fallback_overhead.py`
- Workload harness: `benchmarks/workload_validation.py`
- Package: `bielsort==0.1.0` from PyPI
- Artifact retention: 30 days from each workflow run

