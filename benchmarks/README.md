# Benchmark policy

The benchmark imports `bielsort` and compares equivalent operations:

- `sorted(data)` against `bielsort.sort(data)`;
- `data.sort()` against `bielsort.sort_in_place(data)`.

Input copies for in-place algorithms are created before timing. Expected
results are also created outside the timed region.

Run:

```bash
python benchmarks/benchmark.py -n 10000 100000 1000000 -r 5
```

The included distributions exercise:

- dense signed ranges;
- random signed int32;
- random signed int64;
- arbitrary-size 1024-bit integers;
- nearly sorted lists;
- decreasing lists.

Performance claims must include machine, Python, compiler, distributions,
repetitions, and median timings. A speedup on one machine is not a universal
guarantee.

## Peak memory

The memory benchmark runs each algorithm in a separate child process so the
native C allocations contribute to the operating system's peak RSS:

```bash
python benchmarks/memory.py -n 1000000 -r 3
```

It currently supports Linux and macOS. Reported memory is the incremental peak
above the process state after generating the input. It is an operating-system
measurement, not an exact allocation trace.

## NumPy

Install the optional benchmark dependency and run:

```bash
python -m pip install -e ".[benchmark]"
python benchmarks/numpy_comparison.py -n 10000 100000 1000000 -r 5
```

`NumPy E2E` includes conversion from `list[int]` to `ndarray`, stable sorting,
and conversion back to `list[int]`. `NumPy array` measures stable sorting when
the input is already an `int64` array; it is intentionally shown as a
different API scenario.

## Workload validation

Run transparent synthetic proxies for event timestamps, signed record IDs,
and mostly ordered offsets:

```bash
python benchmarks/workload_validation.py \
  -n 10000 100000 1000000 \
  -r 7 \
  --json bielsort-workload-report.json
```

This command compares equivalent new-list operations and writes a shareable
report containing the environment, configuration, selected strategies,
whether a native fast path ran, medians, speedups, and winner for each case.
Algorithm order is interleaved deterministically. Input generation and
expected results stay outside the timed region.

These inputs are workload **proxies**, not claims about production behavior.
Potential users should replace a proxy with an anonymized deterministic
generator matching their data and report both positive and negative results.
See the [use-case guide](../docs/use-cases.md) for the adoption checklist.

## Published-wheel runner matrix

Maintainers can manually run the
[`Hosted runner validation`](../.github/workflows/workload-validation.yml)
workflow. It installs an exact BielSort version from PyPI on Ubuntu, Windows,
Intel macOS, and Apple Silicon macOS, then uploads one JSON report per runner.
The final job consolidates environment metadata, strategy selection, timings,
and within-runner ratios into Markdown.

GitHub-hosted machines have variable load. Use the matrix to validate wheel
installation, correctness, portability, and broad consistency. Do not use its
absolute seconds as stable hardware benchmarks or its synthetic inputs as
evidence of real user demand. See the
[hosted validation policy](../docs/external-validation.md).

## Versioned results

- [GitHub-hosted PyPI wheel consistency — 2026-07-31](results/2026-07-31-github-hosted.md)
- [Linux x86-64 — 2026-07-30](results/2026-07-30-linux-x86_64.md)
- [Counting Sort memory optimization — 2026-07-30](results/2026-07-30-counting-memory.md)
