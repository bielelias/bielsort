# Performance

BielSort targets a specific workload: large Python lists containing exact
signed 64-bit integers. Performance outside that scope is intentionally left
to Timsort.

!!! warning "Measurements, not guarantees"

    The results below describe one development machine and fixed input
    distributions. CPU, Python build, allocator state, input shape, and system
    load can all change the outcome. Benchmark your real workload before making
    an engineering decision.

## One-million-element snapshot

Median of five executions on the original Linux development machine. Times are
in seconds; a speedup above `1.00×` favors BielSort.

### New-list operation

This compares `sorted(data)` with `bielsort.sort(data)`.

| Input | `sorted()` (s) | BielSort (s) | Speedup |
|---|---:|---:|---:|
| Dense range | 0.20259 | 0.04713 | 4.30× |
| Random int32 | 0.24079 | 0.05009 | 4.81× |
| Random int64 | 0.26314 | 0.07535 | 3.49× |
| 1024-bit integers | 0.33237 | 0.33417 | 0.99× |
| Nearly sorted | 0.01691 | 0.01730 | 0.98× |

### In-place operation

This compares `data.sort()` with `bielsort.sort_in_place(data)`.

| Input | `list.sort()` (s) | BielSort (s) | Speedup |
|---|---:|---:|---:|
| Dense range | 0.18953 | 0.03203 | 5.92× |
| Random int32 | 0.23666 | 0.03796 | 6.23× |
| Random int64 | 0.26081 | 0.06028 | 4.33× |
| 1024-bit integers | 0.30962 | 0.31676 | 0.98× |
| Nearly sorted | 0.01139 | 0.01097 | 1.04× |

Splitting the operations matters: `sorted()` and `bielsort.sort()` allocate a
new list, while `list.sort()` and `bielsort.sort_in_place()` mutate an existing
list. Input copies for in-place benchmarks are created before timing.

## Unreleased `sort(key=...)` candidate

The 0.2 research branch connects the existing new-list `key` parameter to the
adaptive signed-int64 selector. Eleven rotated samples pinned to one CPU
measured these speedups over `sorted(key=...)`:

| Direction / key distribution | 10,000 | 100,000 | 1,000,000 |
|---|---:|---:|---:|
| ascending dense int64 | 3.36× | 4.10× | 5.09× |
| ascending random int64 | 2.37× | 2.93× | 3.67× |
| ascending string fallback | 1.03× | 0.99× | 1.00× |
| reverse dense int64 | 3.91× | 4.14× | 5.13× |
| reverse random int64 | 2.42× | 2.68× | 3.53× |
| reverse string fallback | 1.04× | 0.98× | 0.98× |

The in-place keyed experiment was rejected for this candidate: despite large
integer-key gains, its private compatibility copy made sampled generic keys up
to 17% slower. `sort_in_place(key=...)` therefore remains a direct Timsort
operation. See the
[candidate report](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-08-04-keyed-public-api-candidate.md)
for the contract, method, raw data, and release gates.

## Reading the result honestly

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### Favorable

Large, unsorted, exact int64 lists can reach the native Counting or Radix path
and showed substantial gains on this machine.
</div>

<div class="biel-card" markdown>
### Neutral

Arbitrary-size integers use Timsort, so BielSort should be close to the built-in
operation rather than faster.
</div>

<div class="biel-card" markdown>
### Built-in advantage

Small and nearly sorted inputs already match Timsort's strengths. The selector
falls back because native buffers would not be worthwhile.
</div>

</div>

## Memory tradeoff

Native speed requires auxiliary buffers proportional to input size. An
isolated one-million-element measurement found substantially higher peak memory
than Python's built-in sort on favorable integer distributions.

A later Counting Sort buffer optimization produced these focused results:

| API | Baseline peak | Optimized peak | Reduction |
|---|---:|---:|---:|
| New list | 41.99 MiB | 26.73 MiB | 36.3% |
| In place | 34.39 MiB | 19.05 MiB | 44.6% |

The optimization also preserved stable ordering and passed regular, stress,
AddressSanitizer, and UndefinedBehaviorSanitizer tests. Memory remains a real
tradeoff, not a solved cost.

## NumPy comparison

NumPy has two different scenarios:

- **end to end:** convert `list[int]` to an array, sort, and convert back;
- **array native:** begin and end with an existing `numpy.ndarray`.

At one million elements on the recorded machine:

| Input | BielSort (s) | NumPy end to end (s) | NumPy array (s) |
|---|---:|---:|---:|
| Dense range | 0.05257 | 0.09432 | 0.05881 |
| Random int64 | 0.07975 | 0.11835 | 0.06677 |

BielSort won the equivalent end-to-end list operation in these measurements.
When the input was already an array, NumPy was faster for the int64 case. These
APIs should not be presented as interchangeable.

## Reproduce the benchmarks

Clone the repository, create an environment, and install the editable project:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[benchmark]"
```

Run the timing, memory, and NumPy comparisons:

```bash
python benchmarks/benchmark.py -n 10000 100000 1000000 -r 5
python benchmarks/memory.py -n 1000000 -r 3
python benchmarks/numpy_comparison.py -n 10000 100000 1000000 -r 5
```

To evaluate transparent workload proxies and save a report that can be shared
in a GitHub issue, run:

```bash
python benchmarks/workload_validation.py \
  -n 10000 100000 1000000 \
  -r 7 \
  --json bielsort-workload-report.json
```

On Windows, activate `.venv\Scripts\Activate.ps1`. The isolated peak-memory
benchmark currently supports Linux and macOS.

Continue with the [use-case and adoption guide](use-cases.md) before deciding
whether an isolated speedup is meaningful to an application.

## Recorded methodology

The repository retains the exact environment, commands, and longer tables:

- [Linux x86-64 report — 2026-07-30](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-07-30-linux-x86_64.md)
- [Counting Sort memory optimization](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-07-30-counting-memory.md)
- [Corrected hosted validation and fallback investigation](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-07-31-fallback-investigation.md)
- [Benchmark policy](https://github.com/bielelias/bielsort/blob/main/benchmarks/README.md)
