# Roadmap

## Before the first public release

- [x] Modern packaging with `pyproject.toml`.
- [x] `src/` package layout.
- [x] New-list and in-place APIs.
- [x] Deterministic tests and benchmark harness.
- [x] Linux, macOS, and Windows CI definitions.
- [x] Cross-platform wheel workflow.
- [x] Choose and add an open source license (MIT).
- [ ] Confirm the `bielsort` name on PyPI and GitHub.
- [x] Add repository URLs and full author metadata.
- [ ] Run CI successfully on all supported CPython versions.
- [ ] Validate AddressSanitizer and UndefinedBehaviorSanitizer builds.
- [ ] Measure peak memory in addition to execution time.
- [ ] Compare with NumPy including list-to-array conversion cost.
- [x] Complete the initial IP decision (defer INPI registration).

## Candidate 0.1 release

- [ ] Publish signed/tagged `0.1.0rc1` artifacts to TestPyPI.
- [ ] Test installation from wheels on clean machines.
- [ ] Freeze the public API for the 0.1 series.
- [ ] Publish reproducible benchmark metadata.

## Future research

- Unsigned 64-bit fast path.
- Safe float fast path with explicit NaN semantics.
- Reduced-memory radix buffers.
- Hardware-specific optimizations with portable fallbacks.
- Optional C API for embedding and other language bindings.
