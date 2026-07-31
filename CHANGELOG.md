# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow Semantic Versioning after the first public
release.

## [Unreleased]

## [0.1.0] - 2026-07-31

### Added

- First stable BielSort release, promoting the API and native sorting core
  exercised in `0.1.0rc1`.
- Guarded, tokenless production PyPI publishing that accepts only an exact
  stable-version tag selected through a manual workflow run.

### Changed

- Promoted the validated release candidate without runtime algorithm or public
  API changes.

## [0.1.0rc1] - 2026-07-30

### Added

- Modern `pyproject.toml` packaging and `src/` layout.
- Cross-platform CI and wheel-building workflows.
- Type information through PEP 561 marker and stub files.
- Project governance and contribution documentation.
- MIT license and standardized package license metadata.
- Tested wheel builds for CPython 3.9-3.14 on Linux x86-64, Windows x86/x64,
  macOS Intel, and macOS Apple Silicon.
- Deterministic stress tests for strategy boundaries and randomized inputs.
- AddressSanitizer and UndefinedBehaviorSanitizer build workflow.
- Isolated peak-memory and fair end-to-end NumPy benchmark harnesses.
- Versioned benchmark report with environment and methodology metadata.
- Counting Sort identity-order stress coverage.
- Canonical `sort`, `sort_in_place`, `sort_with_strategy`, and
  `sort_in_place_with_strategy` APIs.
- Tokenless TestPyPI publishing workflow using GitHub OIDC.

### Changed

- Reduced Counting Sort peak memory by compacting normalized keys to 32 bits
  and separating them from the object-pointer output.
- Kept the earlier `biel_sort*` API names as compatibility aliases.

## [0.1.0a1] - 2026-07-30

### Added

- Stable native counting sort for large dense signed 64-bit integer ranges.
- Stable native LSD radix sort using 11-bit digits.
- Adaptive Timsort fallbacks for small, nearly monotonic, non-integer,
  arbitrary-size integer, `key=`, and `reverse=` workloads.
- New-list and in-place APIs.
- Diagnostic APIs that expose the selected strategy.
- Deterministic correctness, stability, boundary, and fallback tests.
