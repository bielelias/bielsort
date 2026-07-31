# GitHub-hosted PyPI wheel consistency — 2026-07-31

This snapshot records
[GitHub Actions run 30670579360](https://github.com/bielelias/bielsort/actions/runs/30670579360).
Every runner installed the public `bielsort==0.1.0` wheel from PyPI with
`--only-binary=:all:` and verified that the imported package did not come from
the repository checkout.

The workload matrix used 100,000 and 1,000,000 elements, five repetitions,
stable NumPy sorting, and deterministic interleaving of algorithm order. Input
generation and expected results were outside the timed region.

> [!IMPORTANT]
> GitHub-hosted runners are shared, ephemeral machines. These results validate
> installation, correctness, strategy consistency, and broad performance
> behavior. They are not stable hardware benchmarks, production capacity
> measurements, real application workloads, or evidence of user demand.

## Environments

| Context | Platform | Architecture | Python | BielSort | NumPy |
|---|---|---|---:|---:|---:|
| macOS ARM | macOS 26.4 | arm64 | 3.11.9 | 0.1.0 | 2.4.6 |
| macOS Intel | macOS 15.7.7 | x86_64 | 3.11.9 | 0.1.0 | 2.4.6 |
| Ubuntu | Linux 6.17 / glibc 2.39 | x86_64 | 3.11.15 | 0.1.0 | 2.4.6 |
| Ubuntu newest Python | Linux 6.17 / glibc 2.39 | x86_64 | 3.14.6 | 0.1.0 | 2.5.1 |
| Windows | Windows 10.0.26100 | AMD64 | 3.11.9 | 0.1.0 | 2.4.6 |

All five binary-wheel installations, package-source checks, correctness
validations, benchmarks, JSON uploads, and report consolidation jobs passed.

## Consistency summary

Median speedups combine dimensionless within-runner ratios, not absolute times
from different machines. A value above `1.00×` favors BielSort.

| n | Workload | Reports | Native path | BielSort fastest | Median vs `sorted()` | Median vs NumPy E2E |
|---:|---|---:|---:|---:|---:|---:|
| 100,000 | event timestamps | 5 | 5/5 | 5/5 | 5.82× | 2.70× |
| 100,000 | mostly ordered offsets | 5 | 0/5 | 0/5 | 0.76× | 3.09× |
| 100,000 | signed record IDs | 5 | 5/5 | 5/5 | 4.24× | 1.99× |
| 1,000,000 | event timestamps | 5 | 5/5 | 5/5 | 9.82× | 3.45× |
| 1,000,000 | mostly ordered offsets | 5 | 0/5 | 5/5 | 1.21× | 3.91× |
| 1,000,000 | signed record IDs | 5 | 5/5 | 5/5 | 5.85× | 2.08× |

## Short replication

[Run 30671059062](https://github.com/bielelias/bielsort/actions/runs/30671059062)
repeated the complete matrix with three measurements after upgrading artifact
downloads to the Node.js 24-compatible action. All jobs passed without the
earlier deprecation annotation, and the winner pattern was identical:

- BielSort won all 20 native-path comparisons again;
- `sorted()` won all five 100,000-element mostly ordered controls again;
- BielSort using its Timsort fallback won all five 1,000,000-element mostly
  ordered controls again.

The replicated median ratios were `5.28×` and `8.26×` versus `sorted()` for
event timestamps at 100,000 and 1,000,000 elements, and `3.98×` and `4.96×`
for signed record IDs. Shared-runner limitations still apply.

## Complete results

Times are medians in seconds. The NumPy column includes conversion from
`list[int]` to `ndarray`, stable sorting, and conversion back to `list[int]`.

| Runner | n | Workload | Strategy | `sorted()` | BielSort | NumPy E2E | vs `sorted()` | vs NumPy | Winner |
|---|---:|---|---|---:|---:|---:|---:|---:|---|
| macOS ARM | 100,000 | event timestamps | Radix, 2 passes | 0.020442 | 0.002292 | 0.008266 | 8.92× | 3.61× | BielSort |
| macOS ARM | 100,000 | mostly ordered | Timsort fallback | 0.001010 | 0.001209 | 0.005221 | 0.84× | 4.32× | `sorted()` |
| macOS ARM | 100,000 | signed record IDs | Radix, 6 passes | 0.021466 | 0.003637 | 0.008567 | 5.90× | 2.36× | BielSort |
| macOS ARM | 1,000,000 | event timestamps | Stable Counting | 0.274182 | 0.025965 | 0.106945 | 10.56× | 4.12× | BielSort |
| macOS ARM | 1,000,000 | mostly ordered | Timsort fallback | 0.018440 | 0.015841 | 0.068284 | 1.16× | 4.31× | BielSort |
| macOS ARM | 1,000,000 | signed record IDs | Radix, 6 passes | 0.286910 | 0.049078 | 0.102106 | 5.85× | 2.08× | BielSort |
| macOS Intel | 100,000 | event timestamps | Radix, 2 passes | 0.023255 | 0.003088 | 0.009654 | 7.53× | 3.13× | BielSort |
| macOS Intel | 100,000 | mostly ordered | Timsort fallback | 0.001176 | 0.001619 | 0.005990 | 0.73× | 3.70× | `sorted()` |
| macOS Intel | 100,000 | signed record IDs | Radix, 6 passes | 0.023561 | 0.005676 | 0.010019 | 4.15× | 1.77× | BielSort |
| macOS Intel | 1,000,000 | event timestamps | Stable Counting | 0.457272 | 0.052932 | 0.133949 | 8.64× | 2.53× | BielSort |
| macOS Intel | 1,000,000 | mostly ordered | Timsort fallback | 0.026044 | 0.021493 | 0.084119 | 1.21× | 3.91× | BielSort |
| macOS Intel | 1,000,000 | signed record IDs | Radix, 6 passes | 0.460283 | 0.091566 | 0.134729 | 5.03× | 1.47× | BielSort |
| Ubuntu 3.11 | 100,000 | event timestamps | Radix, 2 passes | 0.023634 | 0.004105 | 0.010838 | 5.76× | 2.64× | BielSort |
| Ubuntu 3.11 | 100,000 | mostly ordered | Timsort fallback | 0.001009 | 0.001331 | 0.004118 | 0.76× | 3.09× | `sorted()` |
| Ubuntu 3.11 | 100,000 | signed record IDs | Radix, 6 passes | 0.025206 | 0.005659 | 0.011272 | 4.45× | 1.99× | BielSort |
| Ubuntu 3.11 | 1,000,000 | event timestamps | Stable Counting | 0.374226 | 0.034403 | 0.119188 | 10.88× | 3.46× | BielSort |
| Ubuntu 3.11 | 1,000,000 | mostly ordered | Timsort fallback | 0.019075 | 0.014759 | 0.049904 | 1.29× | 3.38× | BielSort |
| Ubuntu 3.11 | 1,000,000 | signed record IDs | Radix, 6 passes | 0.391768 | 0.061230 | 0.136334 | 6.40× | 2.23× | BielSort |
| Ubuntu 3.14 | 100,000 | event timestamps | Radix, 2 passes | 0.024359 | 0.004188 | 0.011325 | 5.82× | 2.70× | BielSort |
| Ubuntu 3.14 | 100,000 | mostly ordered | Timsort fallback | 0.000822 | 0.002074 | 0.004820 | 0.40× | 2.32× | `sorted()` |
| Ubuntu 3.14 | 100,000 | signed record IDs | Radix, 6 passes | 0.024806 | 0.005850 | 0.012523 | 4.24× | 2.14× | BielSort |
| Ubuntu 3.14 | 1,000,000 | event timestamps | Stable Counting | 0.362352 | 0.036897 | 0.127174 | 9.82× | 3.45× | BielSort |
| Ubuntu 3.14 | 1,000,000 | mostly ordered | Timsort fallback | 0.027018 | 0.014140 | 0.060081 | 1.91× | 4.25× | BielSort |
| Ubuntu 3.14 | 1,000,000 | signed record IDs | Radix, 6 passes | 0.385044 | 0.064062 | 0.140633 | 6.01× | 2.20× | BielSort |
| Windows 3.11 | 100,000 | event timestamps | Radix, 2 passes | 0.026249 | 0.005211 | 0.012435 | 5.04× | 2.39× | BielSort |
| Windows 3.11 | 100,000 | mostly ordered | Timsort fallback | 0.001824 | 0.002003 | 0.005472 | 0.91× | 2.73× | `sorted()` |
| Windows 3.11 | 100,000 | signed record IDs | Radix, 6 passes | 0.027569 | 0.008498 | 0.014627 | 3.24× | 1.72× | BielSort |
| Windows 3.11 | 1,000,000 | event timestamps | Stable Counting | 0.397743 | 0.062083 | 0.148598 | 6.41× | 2.39× | BielSort |
| Windows 3.11 | 1,000,000 | mostly ordered | Timsort fallback | 0.029246 | 0.024227 | 0.061172 | 1.21× | 2.52× | BielSort |
| Windows 3.11 | 1,000,000 | signed record IDs | Radix, 6 passes | 0.415906 | 0.108198 | 0.169361 | 3.84× | 1.57× | BielSort |

## Reviewed conclusions

1. The public wheel installed and returned correct results in all five
   environments.
2. Strategy selection was identical across the matrix:
   - 100,000 event timestamps used two-pass Radix Sort;
   - 1,000,000 event timestamps used stable Counting Sort;
   - signed record IDs used six-pass Radix Sort;
   - mostly ordered offsets used the Timsort fallback.
3. BielSort was fastest in all 20 native-path comparisons against both
   `sorted()` and NumPy end to end.
4. `sorted()` was faster in all five 100,000-element mostly ordered controls.
   The largest ratio difference was on CPython 3.14, but the absolute BielSort
   overhead remained about 1.25 milliseconds on that runner.
5. BielSort was faster in the five 1,000,000-element mostly ordered controls,
   but those executions used Timsort. This is a wrapper/copy-path observation,
   not evidence of native algorithm acceleration.
6. The matrix supports retaining the current native heuristics. It also makes
   small and nearly ordered inputs the clearest target for future dispatcher
   overhead investigation, after real workload evidence is available.

## Reproduction and audit trail

- Workflow: `.github/workflows/workload-validation.yml`
- Input generator: `benchmarks/workload_validation.py`
- Report validator: `benchmarks/summarize_workload_reports.py`
- Package source: `https://pypi.org/project/bielsort/0.1.0/`
- Workflow run: `https://github.com/bielelias/bielsort/actions/runs/30670579360`
- Short replication: `https://github.com/bielelias/bielsort/actions/runs/30671059062`
- Repetitions: 5
- Sizes: 100,000 and 1,000,000
- JSON artifact retention: 30 days from the workflow run
