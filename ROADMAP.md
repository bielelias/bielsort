# Roadmap

## Before the first public release

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

## Candidate 0.1 release

- [x] Publish attested/tagged `0.1.0rc1` artifacts to TestPyPI.
- [x] Test installation from wheels in clean CI environments.
- [x] Freeze the public API for the 0.1 series.
- [x] Prepare tokenless TestPyPI publishing through GitHub OIDC.
- [x] Publish reproducible benchmark metadata.
- [x] Register the pending production PyPI Trusted Publisher.
- [x] Prepare guarded, tokenless production PyPI publishing.
- [x] Audit tracked files and Git history for common credential patterns.
- [x] Promote the validated candidate to `0.1.0`.
- [x] Update the public security and conduct reporting policies.
- [ ] Make the GitHub repository public.
- [ ] Enable GitHub private vulnerability reporting.
- [ ] Publish and verify `0.1.0` on production PyPI.

## Future research

- Unsigned 64-bit fast path.
- Safe float fast path with explicit NaN semantics.
- Reduced-memory radix buffers.
- Hardware-specific optimizations with portable fallbacks.
- Optional C API for embedding and other language bindings.
