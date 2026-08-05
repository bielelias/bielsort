# Development status

This page is the durable engineering handoff for BielSort. It records the
current release state, accepted decisions, and the next verifiable gates so a
new contributor or development chat can resume from repository evidence.

## Release state

| Channel | Version | Status |
|---|---|---|
| Production PyPI | `0.1.0` | current stable release |
| GitHub Release | `v0.1.0` | current stable tag |
| TestPyPI | `0.2.0rc1` | published release candidate |
| Repository metadata | `0.2.0rc1` | matches the TestPyPI candidate |

The production PyPI version must remain `0.1.0` until the owner explicitly
approves a stable `0.2.0` release. Published files and version numbers are
immutable; a changed candidate must use a new version such as `0.2.0rc2`.

## What the 0.2 candidate adds

- stable native Counting or Radix selection for eligible new-list
  `sort(..., key=...)` calls with exact signed-int64 keys;
- stable `reverse=True` support for that keyed selector;
- one key call per record in encounter order, including fallback paths;
- immutable `SortInfo` diagnostics through `sort_with_info()`;
- a conservative pre-key limit for BielSort's variable native auxiliary
  buffers;
- direct Timsort behavior for in-place key calls and generic or unsuitable
  new-list workloads.

The candidate deliberately does not promise to beat Timsort for every input.
The accepted nearly ordered trade-off and measured wins/losses are recorded in
the versioned benchmark reports.

## Evidence already completed

- 104 deterministic functional, differential, stress, memory-guard, GC, and
  workload-tool tests pass locally and against a clean TestPyPI installation.
- AddressSanitizer and UndefinedBehaviorSanitizer validation passed.
- CI passed for CPython 3.9–3.14 on Linux and representative Windows and macOS
  hosts.
- The release workflow built and tested wheels on Linux, Windows, Intel macOS,
  and Apple Silicon macOS.
- TestPyPI contains 36 wheels and one source distribution for `0.2.0rc1`.
- A clean CPython 3.11 environment installed the published manylinux wheel and
  passed the complete 104-test suite outside the source tree.
- The public documentation builds in strict mode and distinguishes stable
  `0.1.0` from candidate `0.2.0rc1`.

## Promotion gates

- [ ] Run the manual TestPyPI candidate matrix against the published
  `0.2.0rc1` wheels on Linux, Windows, Intel macOS, and Apple Silicon macOS.
- [ ] Review the stable API surface and type hints once more after the
  published-wheel matrix passes.
- [ ] Prepare the stable `0.2.0` metadata and changelog on a dedicated branch,
  without publishing.
- [ ] Obtain explicit owner approval before creating `v0.2.0` or dispatching
  the production PyPI workflow.
- [ ] Install and test the production wheel in a fresh environment only after
  an approved publication.

External workload reports remain valuable adoption evidence, but they are not
an arbitrary waiting requirement for the stable release. Performance claims
must continue to distinguish synthetic measurements from real workloads.

## Resume checklist

Start from the repository root and inspect the current evidence:

```bash
git status --short --branch
git log -8 --oneline --decorate
python -m unittest discover -s tests -v
```

Then read this page, `ROADMAP.md`, `CHANGELOG.md`, and `docs/RELEASING.md`.
Work on one focused branch at a time and update this page when a gate changes.
