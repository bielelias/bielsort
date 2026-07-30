# Benchmark policy

The benchmark compares equivalent operations:

- `sorted(data)` against `biel_sort(data)`;
- `data.sort()` against `biel_sort_in_place(data)`.

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

## Versioned results

- [Linux x86-64 — 2026-07-30](results/2026-07-30-linux-x86_64.md)
- [Counting Sort memory optimization — 2026-07-30](results/2026-07-30-counting-memory.md)
