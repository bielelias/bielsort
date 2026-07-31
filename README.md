# BielSort

[![PyPI version](https://img.shields.io/pypi/v/bielsort.svg)](https://pypi.org/project/bielsort/)
[![CPython 3.9-3.14](https://img.shields.io/badge/CPython-3.9--3.14-blue.svg)](https://pypi.org/project/bielsort/)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-0f766e.svg)](https://bielelias.github.io/bielsort/)
[![CI](https://github.com/bielelias/bielsort/actions/workflows/ci.yml/badge.svg)](https://github.com/bielelias/bielsort/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Current stable release: [`0.1.0` on PyPI](https://pypi.org/project/bielsort/0.1.0/)
> and [`v0.1.0` on GitHub](https://github.com/bielelias/bielsort/releases/tag/v0.1.0).
> The public API is stable for the 0.1 series, while performance heuristics may
> continue to evolve before 1.0.

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

- Development stage: beta (`0.1.0`)
- Published: PyPI and GitHub Releases
- Runtime: CPython 3.9+
- Native language: C
- Fast path: exact Python integers in signed 64-bit range
- Fallback: Python-compatible stable sorting
- License: MIT
- CI: CPython 3.9-3.14 on Linux, Windows, and macOS
- Wheels: Linux x86-64, Windows x86/x64, and macOS Intel/Apple Silicon

## Installation

Install the stable release from PyPI:

```bash
python -m pip install bielsort
```

For a reproducible installation, pin the current release:

```bash
python -m pip install bielsort==0.1.0
```

The package has no runtime dependencies. The canonical import is `bielsort`.

### Installing from a source checkout

The following commands are for a cloned project, not for a regular PyPI
installation. From the project directory:

```bash
python -m pip install .
```

The dot means **the current directory**. For development, `-e` creates an
editable installation:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Usage

```python
import bielsort

numbers = [8, -4, 10, 3, -4]

# Like sorted(): returns a new list.
ordered = bielsort.sort(numbers)

# Like list.sort(): mutates the list and returns None.
bielsort.sort_in_place(numbers)
```

Using the package namespace keeps the calls visually distinct from Python's
`sorted()` function and `list.sort()` method. Python has no standalone built-in
function named `sort()`.

`key=` and `reverse=` are supported and deliberately use the Timsort fallback:

```python
import bielsort

records = [{"score": 8}, {"score": 3}]
ordered = bielsort.sort(
    records,
    key=lambda item: item["score"],
    reverse=True,
)
```

The diagnostic APIs expose the selected strategy:

```python
import bielsort

ordered, strategy = bielsort.sort_with_strategy([3, 1, 2] * 10_000)
print(strategy)
```

The earlier `biel_sort*` names remain compatibility aliases for the 0.1
series. New code should use the four `sort*` names shown above.

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
million elements. Times are in seconds and speedups above `1.00x` favor
BielSort.

### New-list operation

| Input | `sorted()` (s) | BielSort (s) | Speedup |
|---|---:|---:|---:|
| dense range | 0.20259 | 0.04713 | 4.30x |
| random int32 | 0.24079 | 0.05009 | 4.81x |
| random int64 | 0.26314 | 0.07535 | 3.49x |
| 1024-bit integers | 0.33237 | 0.33417 | 0.99x |
| nearly sorted | 0.01691 | 0.01730 | 0.98x |

### In-place operation

| Input | `list.sort()` (s) | BielSort (s) | Speedup |
|---|---:|---:|---:|
| dense range | 0.18953 | 0.03203 | 5.92x |
| random int32 | 0.23666 | 0.03796 | 6.23x |
| random int64 | 0.26081 | 0.06028 | 4.33x |
| 1024-bit integers | 0.30962 | 0.31676 | 0.98x |
| nearly sorted | 0.01139 | 0.01097 | 1.04x |

These numbers are not universal guarantees. See
[`benchmarks/README.md`](benchmarks/README.md) for the benchmark policy and
reproduction commands. The versioned
[2026-07-30 Linux report](benchmarks/results/2026-07-30-linux-x86_64.md)
also records peak memory and NumPy comparisons. A separate
[Counting Sort optimization report](benchmarks/results/2026-07-30-counting-memory.md)
records the measured 36%-45% peak-memory reduction.

## Scope and limitations

- The accelerated path currently supports exact `int` objects in signed
  64-bit range.
- Floats, strings, subclasses, mixed types, huge integers, `key=`, and
  `reverse=` use Timsort.
- The project is CPython-specific because its native module uses the CPython C
  API.
- Prebuilt wheels currently target Linux x86-64, Windows x86/x64, and macOS
  Intel/Apple Silicon. Other platforms may need to build from source and are
  not yet part of the validated compatibility matrix.
- `bielsort` is the canonical import. The older `bielsort_native` import
  remains available for compatibility.
- Counting and radix paths allocate native buffers proportional to input size.
- BielSort is a hybrid implementation based on established sorting techniques;
  it should not be presented as a newly invented sorting theory.

## Development

- [Documentation website](https://bielelias.github.io/bielsort/)
- [Guia em português](https://bielelias.github.io/bielsort/pt-br/)
- [Use-case and adoption guide](https://bielelias.github.io/bielsort/use-cases/)
- [Casos de uso e adoção](https://bielelias.github.io/bielsort/use-cases-pt/)
- [Stable release on PyPI](https://pypi.org/project/bielsort/0.1.0/)
- [GitHub release `v0.1.0`](https://github.com/bielelias/bielsort/releases/tag/v0.1.0)
- [Continuous integration](https://github.com/bielelias/bielsort/actions/workflows/ci.yml)
- [Contributing guide](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security policy](SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Release guide](docs/RELEASING.md)
- [TestPyPI release-candidate archive](https://test.pypi.org/project/bielsort/0.1.0rc1/)
- [Benchmark results](benchmarks/results/2026-07-30-linux-x86_64.md)
- [Counting Sort memory optimization](benchmarks/results/2026-07-30-counting-memory.md)

## License

Copyright (c) 2026 Gabriel Fernandes Farah Elias.

BielSort is distributed under the [MIT License](LICENSE).

## Português

O BielSort é uma biblioteca de ordenação estável e adaptativa para CPython.
Ela acelera listas grandes de inteiros usando Counting Sort ou Radix Sort em C
e recorre ao Timsort nos casos em que o algoritmo padrão é mais adequado.

A primeira versão pública estável é a `0.1.0`, distribuída sob a licença MIT.
A compilação e os testes de wheels foram validados no CI para CPython 3.9 até
3.14 em Linux, Windows, macOS Intel e macOS Apple Silicon.

Instalação e uso recomendado:

```bash
python -m pip install bielsort
```

```python
import bielsort

ordenados = bielsort.sort([8, -4, 10, 3, -4])
```
