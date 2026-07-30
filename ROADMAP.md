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
- [ ] Confirm the `bielsort` package name on PyPI.
- [x] Add repository URLs and full author metadata.
- [x] Run CI successfully on all supported CPython versions.
- [x] Validate AddressSanitizer and UndefinedBehaviorSanitizer builds.
- [x] Measure peak memory in addition to execution time.
- [x] Reduce Counting Sort peak memory with compact keys and phased buffers.
- [x] Compare with NumPy including list-to-array conversion cost.
- [x] Complete the initial IP decision (defer INPI registration).

## Candidate 0.1 release

- [ ] Publish signed/tagged `0.1.0rc1` artifacts to TestPyPI.
- [x] Test installation from wheels in clean CI environments.
- [ ] Freeze the public API for the 0.1 series.
- [x] Publish reproducible benchmark metadata.

## Future research

- Unsigned 64-bit fast path.
- Safe float fast path with explicit NaN semantics.
- Reduced-memory radix buffers.
- Hardware-specific optimizations with portable fallbacks.
- Optional C API for embedding and other language bindings.
