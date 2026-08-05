# Roadmap

Current stable release: [`0.2.0` on PyPI](https://pypi.org/project/bielsort/0.2.0/)
and [`v0.2.0` on GitHub](https://github.com/bielelias/bielsort/releases/tag/v0.2.0),
published on 2026-08-05.

## Foundation completed for 0.1.0

- [x] Modern packaging with `pyproject.toml`.
- [x] `src/` package layout.
- [x] New-list and in-place APIs.
- [x] Deterministic tests and benchmark harness.
- [x] Linux, macOS, and Windows CI definitions.
- [x] Cross-platform wheel workflow validated on Linux x86-64, Windows
  x86/x64, macOS Intel, and macOS Apple Silicon.
- [x] Choose and add an open source license (MIT).
- [x] Confirm and create the `bielsort` repository on GitHub.
- [x] Check current `bielsort` name availability on PyPI and TestPyPI.
- [x] Add repository URLs and full author metadata.
- [x] Run CI successfully on all supported CPython versions.
- [x] Validate AddressSanitizer and UndefinedBehaviorSanitizer builds.
- [x] Measure peak memory in addition to execution time.
- [x] Reduce Counting Sort peak memory with compact keys and phased buffers.
- [x] Compare with NumPy including list-to-array conversion cost.
- [x] Complete the initial IP decision (defer INPI registration).

## Stable 0.1.0 publication

- [x] Publish attested/tagged `0.1.0rc1` artifacts to TestPyPI.
- [x] Test installation from wheels in clean CI environments.
- [x] Freeze the public API for the 0.1 series.
- [x] Prepare tokenless TestPyPI publishing through GitHub OIDC.
- [x] Publish reproducible benchmark metadata.
- [x] Register the production PyPI Trusted Publisher.
- [x] Prepare guarded, tokenless production PyPI publishing.
- [x] Audit tracked files and Git history for common credential patterns.
- [x] Promote the validated candidate to `0.1.0`.
- [x] Update the public security and conduct reporting policies.
- [x] Make the GitHub repository public.
- [x] Enable GitHub private vulnerability reporting.
- [x] Publish and verify `0.1.0` on production PyPI.
- [x] Publish searchable GitHub Pages documentation with a Portuguese guide.

## Adoption validation

- [x] Add transparent synthetic workload proxies and shareable JSON reports.
- [x] Add a manual published-wheel matrix for Linux, Windows, Intel macOS, and
  Apple Silicon macOS.
- [x] Publish the first reviewed hosted-runner consistency snapshot.
- [x] Add a privacy-preserving evaluator for user-owned workloads.
- [ ] Collect reproducible reports from at least three external workloads.
- [ ] Publish the first anonymized real-world case study, including losses.
- [ ] Define performance changes from measured external workloads rather than
  synthetic wins alone.

## 0.2 release candidate and promotion

- [x] Add stable adaptive signed-int64 keys to the new-list API.
- [x] Preserve one key call per record and exact-object Timsort fallback.
- [x] Add structured strategy and native-memory diagnostics.
- [x] Document and accept the bounded nearly ordered trade-off.
- [x] Pass local, cross-platform, sanitizer, wheel, and documentation checks.
- [x] Publish and clean-install `0.2.0rc1` from TestPyPI.
- [x] Validate the published TestPyPI wheels on the supported hosted-runner
  matrix.
- [x] Complete a final API/type-hint review for stable `0.2.0`.
- [x] Prepare stable metadata and changelog without publishing.
- [x] Publish and clean-install `0.2.0` after explicit owner approval.

## Future research

- [x] Prototype stable native keyless `reverse=True` for both public operation
  shapes and record the first local benchmark gate.
- [x] Validate the keyless reverse candidate in the supported cross-platform
  source-build CI and sanitizer workflow.
- [x] Validate built keyless reverse wheels with the supported installation
  matrix before considering it for a release.
- [x] Complete the promotion review and merge PR #30 after its source,
  sanitizer, documentation, and build-only wheel gates pass.
- [x] Build a private compact stable `argsort` prototype and measure complete
  permutation creation and application costs.
- [x] Add and validate a private native application path for reusing one
  compact permutation across parallel Python sequences.
- [x] Define a practical innovation roadmap from Python, NumPy, Arrow, Polars,
  pandas, and database selection patterns.
- [x] Implement the first private stable compact top-k prototype.
- [x] Validate stable compact top-k construction, three-sequence reuse, and
  compact storage against the fixed canonical gates.
- [x] Validate private fused `apply_many()` against repeated native
  application. The fixed performance gate did not pass, so no public
  promotion is planned from this result.
- [x] Design and pre-register a direct stable keyed top-k experiment for
  Python records before implementing or exposing a public function.
- [ ] Implement and validate the private exact-int64 keyed top-k core without
  adding a public symbol.
- [ ] Prototype native inverse and composition operations only after external
  demand justifies expanding the private permutation toolkit.
- [ ] Evaluate fused sorted-group boundaries and counts for telemetry/event
  workloads.
- [ ] Add an unsigned 64-bit fast path after a dedicated semantic and
  performance proposal.
- [ ] Define explicit NaN and signed-zero semantics before a float fast path.
- [ ] Evaluate reduced-memory radix buffers.
- [ ] Evaluate hardware-specific optimizations with portable fallbacks.
- [ ] Consider an optional C API and other language bindings only after the
  Python API demonstrates sustained adoption.
