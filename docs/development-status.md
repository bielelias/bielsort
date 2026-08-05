# Development status

This page is the durable engineering handoff for BielSort. It records the
current release state, accepted decisions, and the next verifiable gates so a
new contributor or development chat can resume from repository evidence.

## Release state

| Channel | Version | Status |
|---|---|---|
| Production PyPI | `0.2.0` | current stable release |
| GitHub Release | `v0.2.0` | current stable tag |
| TestPyPI | `0.2.0rc1` | validated candidate archive |
| Repository metadata | `0.2.0` | matches the stable release |

The stable `0.2.0` release was prepared from the exact cross-platform validated
`0.2.0rc1` candidate. Published files and version numbers are immutable; any
future candidate or stable release must use a new PEP 440 version.

## What version 0.2 adds

- stable native Counting or Radix selection for eligible new-list
  `sort(..., key=...)` calls with exact signed-int64 keys;
- stable `reverse=True` support for that keyed selector;
- one key call per record in encounter order, including fallback paths;
- immutable `SortInfo` diagnostics through `sort_with_info()`;
- a conservative pre-key limit for BielSort's variable native auxiliary
  buffers;
- direct Timsort behavior for in-place key calls and generic or unsuitable
  new-list workloads.

Version 0.2 deliberately does not promise to beat Timsort for every input.
The accepted nearly ordered trade-off and measured wins/losses are recorded in
the versioned benchmark reports.

## Evidence already completed

- The current 105-test functional, differential, stress, memory-guard, GC,
  workload-tool, and API-contract suite passes locally.
- AddressSanitizer and UndefinedBehaviorSanitizer validation passed.
- CI passed for CPython 3.9–3.14 on Linux and representative Windows and macOS
  hosts.
- The release workflow built and tested wheels on Linux, Windows, Intel macOS,
  and Apple Silicon macOS.
- TestPyPI contains 36 wheels and one source distribution for `0.2.0rc1`.
- A clean CPython 3.11 environment installed the published manylinux wheel and
  passed the complete 104-test suite outside the source tree.
- The published-wheel
  [hosted matrix](https://github.com/bielelias/bielsort/actions/runs/30971193214)
  installed `0.2.0rc1` from TestPyPI and passed all 104 tests on Linux with
  CPython 3.9–3.14, Windows with CPython 3.11/3.14, Intel macOS with CPython
  3.11, and Apple Silicon macOS with CPython 3.14.
- The public documentation builds in strict mode and presents stable `0.2.0`
  while preserving the validated `0.2.0rc1` evidence as release history.
- The final 0.2 API review freezes canonical exports and signatures, compares
  six runtime modules with their PEP 561 stubs through `mypy.stubtest`, and
  verifies representative type inference in strict mode. A clean wheel and
  source distribution include the type files and pass `twine check`.
- The prepublication stable `0.2.0` source distribution and CPython 3.11 wheel
  passed `twine check`; a fresh environment installed that local wheel and
  passed all 105 tests outside the source tree.
- The approved production
  [workflow](https://github.com/bielelias/bielsort/actions/runs/30973448781)
  rebuilt, tested, and published 36 wheels plus the source distribution from
  the exact `v0.2.0` tag through PyPI Trusted Publishing.
- A clean CPython 3.11 environment downloaded the public `0.2.0` manylinux
  wheel without cache, exercised the native keyed Radix path, and passed all
  105 tests outside the source tree.

## Promotion gates

- [x] Run the manual TestPyPI candidate matrix against the published
  `0.2.0rc1` wheels on Linux, Windows, Intel macOS, and Apple Silicon macOS.
- [x] Review the stable API surface and type hints once more after the
  published-wheel matrix passes.
- [x] Prepare the stable `0.2.0` metadata and changelog on a dedicated branch,
  without publishing.
- [x] Obtain explicit owner approval before creating `v0.2.0` or dispatching
  the production PyPI workflow.
- [x] Install and test the production wheel in a fresh environment only after
  an approved publication.

External workload reports remain valuable adoption evidence, but they are not
an arbitrary waiting requirement for the stable release. Performance claims
must continue to distinguish synthetic measurements from real workloads.

## Unreleased 0.3 research

The `research/keyless-reverse-0.3` branch contains the first post-0.2
candidate. It applies the stable native Counting/Radix transformation to
keyless `reverse=True` for both new-list and in-place calls. Local disordered
integer samples measured `2.71x–6.17x` over `sorted(reverse=True)` and
`2.87x–7.41x` over `list.sort(reverse=True)`. Ordered Timsort fallbacks ranged
from `0.91x` to `1.13x`, including the negative result.

The candidate passes 109 optimized and sanitized local tests, warning-clean
native compilation, and the typed API checks. PR
[#30](https://github.com/bielelias/bielsort/pull/30) passed source-build CI on
CPython 3.9–3.14 for Linux and representative Windows and macOS hosts, the
hosted sanitizer job, public-stub checks, and strict documentation. The
non-publishing [build-only wheel run](https://github.com/bielelias/bielsort/actions/runs/31032231434)
also passed on Linux, Windows, macOS Intel, and macOS ARM, including wheel tests,
content validation, artifact upload, and source-distribution creation. The PR
was merged into `main` as
[commit `31fb517`](https://github.com/bielelias/bielsort/commit/31fb5179979b1d1718199eb1800ef3302caaed83),
whose [post-merge CI](https://github.com/bielelias/bielsort/actions/runs/31034748359),
sanitizer, and documentation deployment also passed. The code remains an
unreleased research candidate rather than a package release. The full report
is the versioned
[keyless reverse research record](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-08-05-keyless-reverse.md).

A separate [compact stable `argsort` proposal](argsort-research.md) fixes the
intended semantics and benchmark gates without adding a public function. Its
first private implementation passed 119 optimized local tests and both
pre-registered construction gates. At one million disordered integers, its
seven-sample local timing record measures `4.51x–8.04x` over Python's stable
index baseline, while isolated peak RSS is 45%–47% lower. The first report
also records that nearly sorted construction is 32% slower with 14% more peak
RSS, and that iterating compact indices in Python is slower than applying an
existing `list[int]`. The initial evidence is in the
[compact argsort research record](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-08-05-compact-argsort.md).
The same 119 tests passed locally with AddressSanitizer and
UndefinedBehaviorSanitizer. Stub/runtime comparison, strict Python 3.9 typing,
and a clean local wheel/source build also passed. PR
[#32](https://github.com/bielelias/bielsort/pull/32) passed source-build CI on
Linux with CPython 3.9–3.14, Windows with CPython 3.11/3.14, and macOS with
CPython 3.11/3.14, together with hosted sanitizer, public-stub, and strict
documentation checks. The non-publishing
[build-only wheel run](https://github.com/bielelias/bielsort/actions/runs/31038877694)
also passed on Linux, Windows, macOS Intel, and macOS ARM, including wheel
tests, content validation, artifact upload, and source-distribution creation.
The PR was merged into `main` as
[commit `ac3b771`](https://github.com/bielelias/bielsort/commit/ac3b7710366fb8835ed2ae6a71096eddf556b7c6).

The follow-up private branch adds native permutation application without a
public export. Its 122 optimized and sanitized local tests, warning-clean
build, runtime/stub comparison, and strict Python 3.9 typing all pass. Native
application is `2.14x–4.86x` faster than the precomputed Python-index baseline
at one million elements. Building one order and applying it to three parallel
lists reaches `4.93x–6.41x` in the three disordered one-million-element cases
and reduces their measured incremental peak RSS by 51%–56%. Nearly sorted
complete flows remain within the fixed no-regression gate, although their
permutation construction alone is still slower. See the
[native application research record](https://github.com/bielelias/bielsort/blob/main/benchmarks/results/2026-08-05-compact-argsort-native-apply.md).
The local wheel and source distribution pass metadata validation, and a clean
environment installs the wheel and exercises the native application outside
the source tree.
PR [#33](https://github.com/bielelias/bielsort/pull/33) passes source-build CI
on Linux with CPython 3.9–3.14, Windows with CPython 3.11/3.14, and macOS with
CPython 3.11/3.14, plus hosted sanitizers, public stubs, and strict
documentation. Its non-publishing
[build-only wheel run](https://github.com/bielelias/bielsort/actions/runs/31041438904)
also passes on Linux, Windows, macOS Intel, and macOS Apple Silicon, including
wheel tests, content validation, artifact upload, and source-distribution
creation. The prototype has passed its private research gates; public API
design and promotion remain separate decisions. It was squash-merged into
`main` as
[commit `73c0d22`](https://github.com/bielelias/bielsort/commit/73c0d22).

The next private branch implements stable compact top-k selection for exact
signed-int64 Python sequences. Its pre-registered local benchmark gate passed
all 24 one-million-element construction cases and all 24 build-once/apply-three
reuse cases. Construction measured `1.56x–3.36x` over equivalent `heapq`
selection and `15.41x–36.99x` over stable full index sorting; reuse measured
`1.55x–3.45x` over the equivalent `heapq` flow. The compact result uses four
bytes per selected index at this input size and preserves encounter order for
ties. See the
[stable top-k research record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-stable-topk.md).
The candidate passes 133 optimized and sanitized local tests, warning-clean
native compilation, runtime/stub comparison, strict Python 3.9 typing, and
strict documentation. The private `apply_many()` continuation also passes
the hosted source-build matrix and sanitizers, but its fixed performance gate
did not pass: 12 of 15 target cases reached `1.05x`, while only 2 of 6 complete
permutations reached the required `1.10x`. It is not approved for public
promotion. The earlier local wheel and source distribution pass metadata
validation, and a clean environment installs the wheel and passes all 130
pre-continuation tests outside the source tree. Draft PR
[#34](https://github.com/bielelias/bielsort/pull/34) passes source-build CI on
Linux with CPython 3.9–3.14, Windows with CPython 3.11/3.14, and macOS with
CPython 3.11/3.14, plus hosted sanitizers, public stubs, and strict
documentation. Its non-publishing
[build-only wheel run](https://github.com/bielelias/bielsort/actions/runs/31046012832)
also passes on Linux, Windows, macOS Intel, and macOS Apple Silicon, including
wheel tests, content validation, artifact upload, and source-distribution
creation. The candidate remains private; public API design, promotion review,
and any release remain later decisions.

## Resume checklist

Start from the repository root and inspect the current evidence:

```bash
git status --short --branch
git log -8 --oneline --decorate
python -m unittest discover -s tests -v
```

Then read this page, `ROADMAP.md`, `CHANGELOG.md`, and `docs/RELEASING.md`.
Work on one focused branch at a time and update this page when a gate changes.
