# Contributing to BielSort

Thank you for helping improve BielSort.

## Development setup

Use a supported CPython version and a virtual environment:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, use `.venv\Scripts\python` instead.

The C compiler must be compatible with the selected CPython distribution.

## Before submitting a change

1. Add or update tests for observable behavior.
2. Run the complete unit-test suite.
3. Run a benchmark when changing the native algorithm or heuristics.
4. Report correctness and performance separately.
5. Do not claim universal speedups from one distribution or machine.
6. Update `CHANGELOG.md` for user-visible changes.

For native changes on Linux, also run the sanitizer workflow or an equivalent
local build with `BIELSORT_SANITIZE=1`.

## Type checking

Install the pinned type-checking toolchain when changing public functions,
exports, aliases, dataclasses, or `.pyi` files:

```bash
python -m pip install -r requirements-typecheck.txt
python -m mypy.stubtest bielsort bielsort_native
python -m mypy --strict --python-version 3.9 tests/typing/api_contract.py
```

`stubtest` compares the declared package surface with runtime introspection.
The strict contract verifies representative inference through both the
canonical `bielsort` import and the compatibility package.

## Benchmarking

```bash
python benchmarks/benchmark.py -n 10000 100000 1000000 -r 5
python benchmarks/memory.py -n 1000000 -r 3
python benchmarks/numpy_comparison.py -n 10000 100000 1000000 -r 5
python benchmarks/workload_validation.py -n 10000 100000 1000000 -r 7
```

Close unrelated applications, keep the machine on stable power, and report:

- CPU and operating system;
- Python version and compiler;
- input distributions;
- number of repetitions;
- medians, not only the fastest run.

For application feedback, replace one workload proxy with an anonymized
deterministic generator, save the JSON report, and use the real-world use-case
issue form. Reports where BielSort loses are as useful as wins. Never publish
production data, credentials, or confidential identifiers.

The manual hosted-runner workflow is for maintainers validating an exact PyPI
wheel. Its shared runners are not a substitute for a contributor's application
benchmark and their absolute timings must not be compared across machines.

## Documentation

Install the pinned documentation toolchain in a virtual environment:

```bash
python -m pip install -r requirements-docs.txt
```

Preview the site locally while editing:

```bash
python -m mkdocs serve
```

Before submitting documentation changes, run the same strict build used in
continuous integration:

```bash
python -m mkdocs build --strict
```

The generated `site/` directory is local build output and must not be
committed. A merge to `main` deploys the validated site to GitHub Pages.

## Native-code rules

- Preserve stable sorting.
- Preserve the input list when using `sort()`.
- Preserve list identity and return `None` in `sort_in_place()`.
- Avoid releasing the GIL while mutating a caller-owned list.
- Check allocation failures and integer boundaries.
- Keep the Timsort fallback correct even when a heuristic is conservative.

## Pull requests

Keep changes focused. Explain the motivation, correctness argument, benchmark
method, results, and any memory tradeoffs.
