# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow Semantic Versioning after the first public
release.

## [Unreleased]

### Added

- Modern `pyproject.toml` packaging and `src/` layout.
- Cross-platform CI and wheel-building workflows.
- Type information through PEP 561 marker and stub files.
- Project governance and contribution documentation.
- MIT license and standardized package license metadata.

## [0.1.0a1] - 2026-07-30

### Added

- Stable native counting sort for large dense signed 64-bit integer ranges.
- Stable native LSD radix sort using 11-bit digits.
- Adaptive Timsort fallbacks for small, nearly monotonic, non-integer,
  arbitrary-size integer, `key=`, and `reverse=` workloads.
- New-list and in-place APIs.
- Diagnostic APIs that expose the selected strategy.
- Deterministic correctness, stability, boundary, and fallback tests.
