# BielSort

> Alpha software: the API and performance heuristics may change before 1.0.

BielSort is an adaptive, stable sorting library for CPython. It specializes in
large `list[int]` workloads while preserving Python-compatible behavior through
Timsort fallbacks.

The native core selects among:

- stable counting sort for large, dense signed 64-bit integer ranges;
- stable LSD radix sort with 11-bit digits for other signed 64-bit integers;
- CPython's Timsort for small, nearly monotonic, non-integer, arbitrary-size
  integer, `key=`, and `reverse=` workloads.

It provides separate APIs to compete fairly with both `sorted()` and
`list.sort()`.

## Status

- Development stage: alpha (`0.1.0a1`)
- Runtime: CPython 3.9+
- Native language: C
- Fast path: exact Python integers in signed 64-bit range
- Fallback: Python-compatible stable sorting
- License: MIT
- CI: CPython 3.9-3.14 on Linux, Windows, and macOS
- Wheels: Linux x86-64, Windows x86/x64, and macOS Intel/Apple Silicon

## Installation

From the project directory:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Usage

```python
from bielsort import biel_sort, biel_sort_in_place

numbers = [8, -4, 10, 3, -4]

# Like sorted(): returns a new list.
ordered = biel_sort(numbers)

# Like list.sort(): mutates the list and returns None.
biel_sort_in_place(numbers)
```

`key=` and `reverse=` are supported and deliberately use the Timsort fallback:

```python
records = [{"score": 8}, {"score": 3}]
ordered = biel_sort(records, key=lambda item: item["score"], reverse=True)
```

The diagnostic APIs expose the selected strategy:

```python
from bielsort import (
    biel_sort_diagnostico,
    biel_sort_in_place_diagnostico,
)

ordered, strategy = biel_sort_diagnostico([3, 1, 2] * 10_000)
print(strategy)
```

## Complexity

For `n` elements, numeric range `k`, and `p` varying radix digits:

| Strategy | Time | Additional memory |
|---|---:|---:|
| Native counting | `Θ(n + k)` | `Θ(n + k)` |
| Native radix | `Θ(pn)`, `1 <= p <= 6` | `Θ(n)` |
| Timsort fallback | best `Θ(n)`, worst `Θ(n log n)` | `O(n)` |

For signed 64-bit integers, `p` is bounded by six and does not grow with `n`.

## Local benchmark snapshot

Median of five executions on the original Linux development machine with one
million elements:

| Input | `sorted()` | Biel new | Gain | `.sort()` | Biel in-place | Gain |
|---|---:|---:|---:|---:|---:|---:|
| dense range | 0.20259 s | 0.04713 s | 4.30x | 0.18953 s | 0.03203 s | 5.92x |
| random int32 | 0.24079 s | 0.05009 s | 4.81x | 0.23666 s | 0.03796 s | 6.23x |
| random int64 | 0.26314 s | 0.07535 s | 3.49x | 0.26081 s | 0.06028 s | 4.33x |
| 1024-bit integers | 0.33237 s | 0.33417 s | 0.99x | 0.30962 s | 0.31676 s | 0.98x |
| nearly sorted | 0.01691 s | 0.01730 s | 0.98x | 0.01139 s | 0.01097 s | 1.04x |

These numbers are not universal guarantees. See
[`benchmarks/README.md`](benchmarks/README.md) for the benchmark policy and
reproduction commands. The versioned
[2026-07-30 Linux report](benchmarks/results/2026-07-30-linux-x86_64.md)
also records peak memory and NumPy comparisons.

## Scope and limitations

- The accelerated path currently supports exact `int` objects in signed
  64-bit range.
- Floats, strings, subclasses, mixed types, huge integers, `key=`, and
  `reverse=` use Timsort.
- The project is CPython-specific because its native module uses the CPython C
  API.
- `bielsort` is the canonical import. The older `bielsort_native` import
  remains available for compatibility.
- Counting and radix paths allocate native buffers proportional to input size.
- BielSort is a hybrid implementation based on established sorting techniques;
  it should not be presented as a newly invented sorting theory.

## Development

- [Contributing guide](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security policy](SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Benchmark results](benchmarks/results/2026-07-30-linux-x86_64.md)

## License

Copyright (c) 2026 Gabriel Fernandes Farah Elias.

BielSort is distributed under the [MIT License](LICENSE).

## Português

O BielSort é uma biblioteca de ordenação estável e adaptativa para CPython.
Ela acelera listas grandes de inteiros usando Counting Sort ou Radix Sort em C
e recorre ao Timsort nos casos em que o algoritmo padrão é mais adequado.

A biblioteca ainda está em fase alfa e é distribuída sob a licença MIT. A
compilação e os testes de wheels já foram validados no CI para CPython 3.9 até
3.14 em Linux, Windows, macOS Intel e macOS Apple Silicon.
