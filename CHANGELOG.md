# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow Semantic Versioning after the first public
release.

## [Unreleased]

### Added

- Added a searchable documentation website with a visual landing page,
  installation guide, API reference, strategy explanation, performance and
  compatibility guides, and a Portuguese quick guide.
- Added strict documentation builds for pull requests and automatic GitHub
  Pages deployment from `main`.
- Added a workload-validation benchmark with transparent event, record-ID, and
  mostly ordered proxies plus shareable JSON reports.
- Added a use-case and adoption guide and a structured form for reporting real
  evaluations, including workloads where BielSort is not beneficial.
- Added a manual hosted-runner matrix that installs the public PyPI wheel on
  Linux, Windows, Intel macOS, and Apple Silicon macOS.
- Added a report consolidator and bilingual guidance that separates synthetic
  portability evidence from real workload adoption.
- Added the first reviewed five-runner consistency snapshot for the public
  `0.1.0` PyPI wheel.
- Added a raw-sample fallback profiler and a manual CPython 3.11/3.14 workflow
  for decomposing copy, dispatch, Timsort, and in-place costs.

### Changed

- Updated artifact downloads to the Node.js 24-compatible action generation.
- Refreshed the README, roadmap, architecture notes, and release guide to
  reflect the completed `0.1.0` GitHub and PyPI publication.
- Made namespaced `import bielsort` usage the primary documentation style to
  distinguish BielSort calls from `sorted()` and `list.sort()`.

### Fixed

- Isolated benchmark result destruction from the following timed operation,
  removing order-dependent cross-sample contamination and publishing a
  corrected hosted comparison.

## [0.1.0] - 2026-07-31

### Added

- First stable BielSort release, promoting the API and native sorting core
  exercised in `0.1.0rc1`.
- Guarded, tokenless production PyPI publishing that accepts only an exact
  stable-version tag selected through a manual workflow run.

### Changed

- Promoted the validated release candidate without runtime algorithm or public
  API changes.

### Security

- Updated the supported-version and private vulnerability reporting policy for
  the public `0.1.x` series.

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
