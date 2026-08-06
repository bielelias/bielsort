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
- Pre-registered the contract and fixed benchmark gates for a private direct
  stable keyed top-k experiment over Python records. No public `top_k` symbol
  is added by the proposal.
- Added that private exact-int64 keyed top-k core with stable direct record
  results, one key call per record, iterable support, differential tests, and
  versioned raw timing evidence. Its first canonical gate passed, but generic
  fallback and public API review remain future work.
- Pre-registered the semantic, memory, exact-int64 regression, and generic-key
  gates for a private adaptive top-k continuation. No public API is added by
  this stage-two design.
- Implemented the private adaptive `O(k)` keyed heap, exception-aware stable
  generic merge, and pre-key `heapq`/`raise` native-memory guard. Canonical
  stage-two semantics and memory checks passed, but the unchanged performance
  gate failed in four cases, so the candidate is not approved for promotion.
- Pre-registered an unchanged-code, block-timed confirmation of those four
  failures plus two controls; it cannot replace the failed canonical result.
- Recorded that all four failures and both controls passed the confirmation
  bound without code changes, consistent with host timing variability. The
  original stage-two gate remains failed.
- Added and pre-registered a complete paired-block stage-two protocol before
  execution. Its separate 48-case gate passed without changing selection
  code, while preserving the first failed result; only further private
  callable and isolated-memory experiments are authorized.
- Added a pre-registered common-callable and isolated-memory protocol. Both
  gates passed: 22 of 24 `itemgetter`/`attrgetter`/`lambda` cases reached
  `1.10x` over `heapq`, and the adaptive core used 0.28x–0.43x its traced peak
  memory across the fixed cases. Public API promotion remains unapproved.
- Completed the private direct top-k promotion review, selecting a provisional
  `top_k`/`top_k_with_info` contract and explicit remaining gates without
  adding either name to the public package.
- Pre-registered a private unified stable top-k façade covering natural
  ordering, explicit keys, immutable structured diagnostics, conservative
  memory limits, and a fixed partial-selection/full-sort crossover. No public
  symbol or release is added by the protocol.
- Implemented that private façade with natural signed-int64 detection,
  adaptive large-`k` routing, normalized immutable diagnostics, and
  differential, callback-safety, iterable, exception, and memory-guard tests.
- Recorded a passing 50-case canonical façade gate: every result and route
  matched, no paired median fell below `0.85x`, and 47 cases reached at least
  `0.95x`. The three retained below-parity cases are natural-string fallbacks;
  public API and release decisions remain unapproved.
- Pre-registered a private bounded-memory streaming top-k experiment for
  one-shot Python iterables. Its contract requires stable ties, one key call,
  `O(k)` retained state, pre-consumption memory decisions, and comparison with
  `heapq`; no public symbol or release is added by the proposal.
- Implemented the first private streaming candidate and preserved its fixed
  canonical result. Every semantic and timing gate passed, as did the
  materializing-façade memory gate, but incremental RSS at `k=100,000` was
  `0.76x–0.80x` `heapq` instead of the required maximum `0.70x`; promotion is
  therefore not approved.
- Corrected an inherited-`ru_maxrss` benchmark defect with a worker-ready
  checkpoint and parent-sampled Linux RSS. The malformed attempt and its raw
  samples remain versioned separately from the canonical result.
- Added a second streaming layout that reuses the result list, reconstructs
  retained int64 keys only on a late generic switch, and sorts in place. It
  passed both fixed memory gates (`0.62x–0.67x` `heapq` at `k=100,000`) but
  reached the `1.10x` signed-int64 target in 7 of 12 cases rather than 8, so
  this second canonical result also remains unapproved.
- Evaluated stable medium-`k` Radix finishing and lower-movement exact heap
  repairs without changing the streaming protocol. Both additional canonical
  records preserved the semantic, generic-timing, and memory wins but still
  reached only 7 of 12 signed-int64 targets. A final bottom-up Floyd screening
  produced the same count, so the private candidate remains unapproved and no
  public symbol or release metadata changed.
- Added a market-opportunity review comparing the private research with
  CPython, NumPy, pandas, Polars, Arrow, more-itertools, and Sorted Containers.
  It selects a compact stable reorder plan for aligned Python sequences as the
  next discovery candidate while explicitly recording weak performance-demand
  evidence and deferring implementation until a separate API/usability
  protocol is pre-registered.
- Pre-registered that compact reorder-plan API and usability protocol. It
  selects provisional `argsort(values, *, reverse=False)` and
  `Permutation.apply()` semantics, defers `key=` and `apply_many()`, and fixes
  complete Python, `sort_together()`, NumPy conversion, NumPy-resident,
  semantic, memory, and portability gates before implementation. No public
  symbol or release metadata changed.
- Implemented the protocol as a private keyword-only façade plus contract and
  benchmark-harness tests. The new harness fixes four aligned-sequence shapes,
  complete-flow timing, isolated peak RSS, raw samples, and a clean-tree guard
  for its single canonical run; that run and any public promotion remain
  separate decisions.
- Preserved the first reorder-plan canonical attempt as invalid after every
  `ru_maxrss` subtraction returned zero. The corrected pre-registered memory
  method uses a child-ready checkpoint and parent-sampled Linux RSS without
  changing workloads, algorithms, repetitions, or thresholds; undefined
  ratios now render as `n/a`.
- Preserved a second invalid attempt after discovering that parent RSS
  sampling included post-operation correctness validation. A new
  `operation-complete` handshake stops sampling while measured outputs remain
  alive and authorizes validation only afterward; the unchanged timing gates
  passed, but no combined decision is claimed from the invalid run.
- Recorded the corrected compact reorder-plan canonical decision from a clean
  committed tree. All direct-Python, `sort_together()`, and end-to-end NumPy
  time gates passed, and the three disordered one-million-record workflows
  used `0.44x–0.55x` direct Python's incremental peak RSS. The overall gate
  remains failed because the nearly ordered memory control measured `1.1205x`
  against its frozen `1.10x` ceiling; no public API, version, or release is
  approved.
- Pre-registered a separate nearly ordered memory continuation before changing
  implementation. It limits the hypothesis to avoiding the eager exact-list/
  tuple pointer snapshot, retains every original gate, and adds a `1.05x`
  focused median RSS ceiling plus paired-sample and time controls. The prior
  failed result remains authoritative and no public symbol is added.
- Implemented the private continuation with `PySequence_Fast` acquisition for
  exact list/tuple inputs, retained materialization for other reusable
  sequences, and added safety, route, evaluator, and gate tests. A dedicated
  harness is ready for its single complete decision run; no result is claimed
  before that clean committed execution.
- Recorded a passing single-run memory continuation without weakening any
  gate. Nearly ordered median RSS fell to `0.9928x` direct Python, all three
  paired samples passed the `1.10x` bound, and the 100,000/one-million time
  ratios passed at `1.29x`/`0.97x`. All original time, memory, and compact-
  payload gates also passed; the prior failed result remains versioned and no
  public API or release is approved.

### Fixed

- Removed an unused private streaming comparator left by the final heap
  experiment, restoring warning-clean `-Wall -Wextra -Werror` builds without
  changing the selected algorithm.
- Hardened the private keyed top-k native loops against input-list resizing
  from `key` or generic comparison callbacks. The current record is retained
  across Python calls and size changes now raise `RuntimeError` instead of
  risking invalid borrowed-reference access.
- Repeated the fixed practical callable and isolated-memory protocol after the
  safety change. Both gates passed again without weakening their thresholds;
  the separate result preserves every raw sample.
- Passed the hardened commit through hosted Linux/Windows/macOS source builds,
  ASan/UBSan, strict documentation, and a four-platform non-publishing wheel
  matrix. No package index or release was modified.

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
