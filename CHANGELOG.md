# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow Semantic Versioning after the first public
release.

## [Unreleased]

### Added

- Added an unreleased research candidate for stable native keyless
  `reverse=True` in both new-list and in-place operations, with dedicated
  correctness, sanitizer, typing, and reproducible performance evidence.
- Added a private compact stable `argsort` prototype with an immutable native
  index buffer, compatible fallbacks, differential tests, and versioned
  construction, application, NumPy, and peak-memory evidence. No `argsort`
  name is public yet.
- Added private native compact-permutation application research, including
  exact-object and sequence-contract tests plus versioned time and peak-memory
  evidence for reusing one order across three parallel Python lists.
- Added an unreleased private stable compact top-k prototype and benchmark
  contract for selecting reusable smallest/largest indices without fully
  sorting eligible signed-int64 Python sequences.
- Added a private fused compact-permutation application experiment. It passed
  correctness, cross-platform CI, and the no-regression threshold but missed
  its pre-registered complete-permutation performance gate, so it is not
  proposed for public promotion.

## [0.2.0] - 2026-08-05

Prepared from the cross-platform validated `0.2.0rc1` candidate.

### Added

- Added stable native Counting and Radix paths for eligible new-list
  `sort(key=...)` calls with exact signed-int64 keys, including stable
  `reverse=True`, one key call per record, and exact-object Timsort replay.
- Added `sort_with_info()` and immutable `SortInfo` diagnostics with an
  optional conservative pre-key limit for BielSort's variable native
  auxiliary buffers.
- Added public keyed benchmarks, selector diagnostics, privacy-preserving
  workload evaluation, and bilingual adoption guidance.
- Added a reusable hosted-runner matrix that installs exact release-candidate
  wheels from TestPyPI and runs the complete suite against the published
  package.
- Added durable repository guidance and a development-status handoff so future
  contributors and chats can resume from verified project evidence.
- Added CI checks that compare public stubs with the runtime API and verify
  representative type inference for canonical and compatibility imports.

### Changed

- Kept in-place key calls, generic keys, unsuitable ordered inputs, and
  keyless reverse calls on CPython's Timsort rather than forcing a native path.
- Documented the bounded nearly ordered trade-off instead of claiming a
  universal speedup.

### Fixed

- Declared runtime `__all__` values in the package stubs and added the missing
  private native-extension stub required to validate the typed implementation.

## [0.2.0rc1] - 2026-08-04

Published to TestPyPI for installation testing. The production PyPI release
remains `0.1.0`.

### Added

- Connected the existing new-list
  `sort(key=...)` API to stable native Counting and Radix paths for exact
  signed-int64 key results, including `reverse=True`, with no new public name
  or parameter.
- Added public keyed-API benchmarks, exact key-call and stability tests, and
  user-facing diagnostics for native and fallback strategies.
- Added a `sort_with_info(..., key=...)` release candidate with immutable
  `SortInfo` diagnostics and a pre-key native auxiliary-memory guard.
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
- Added a privacy-preserving Workload Evaluator with local providers,
  equivalent new-list and in-place comparisons, raw timing samples,
  reviewable JSON/Markdown, and bilingual documentation.

### Changed

- Made the keyed native-memory preflight conservative across both compact
  Radix and the largest eligible Counting table instead of using only the
  Radix planning bound.
- Reduced the candidate `SortInfo` contract to operation-specific fields,
  derived `used_native` from the normalized algorithm, and aligned public
  memory field names with `max_native_auxiliary_bytes`.
- Kept `sort_in_place(key=...)` on direct Timsort after an adaptive experiment
  accelerated integer keys but introduced an unacceptable generic-key
  regression.
- Updated artifact downloads to the Node.js 24-compatible action generation.
- Refreshed the README, roadmap, architecture notes, and release guide to
  reflect the completed `0.1.0` GitHub and PyPI publication.
- Made namespaced `import bielsort` usage the primary documentation style to
  distinguish BielSort calls from `sorted()` and `list.sort()`.

### Fixed

- Provisioned an explicit host Python for cross-platform wheel-content
  validation, including GitHub's macOS runners where `python` is not available
  by default.
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
