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

The next milestone is now pre-registered in the
[direct keyed top-k proposal](keyed-topk-research.md): a private exact-int64
core that returns selected records directly, preserves stable ties and object
identity, and calls `key` once per record. Its canonical thresholds were fixed
before implementation. No public symbol or new version is planned at this
stage.

That stage-one core is now implemented and passes all 142 local tests,
warning-clean native compilation, runtime/stub comparison, strict Python 3.9
typing, and strict documentation. Its unchanged canonical gate passed exactly
18 of 24 one-million-record cases at `1.25x` or better over `heapq`; no case
regressed by more than 10%, and the range was `1.09x–1.91x`. See the
[direct keyed top-k research record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-keyed-topk.md).
The newest native commit also passes hosted ASan/UBSan and source-build CI on
Linux with CPython 3.9–3.14, Windows with CPython 3.11/3.14, and macOS with
CPython 3.11/3.14. A build-only wheel matrix remains required before any
promotion decision.

The next private stage is implemented locally: an adaptive `O(k)` keyed heap
that can switch to Python comparisons without repeating key calls, plus a
conservative pre-key native-memory guard. All 154 local tests, warning-clean
native compilation, runtime/stub comparison, strict Python 3.9 typing, and
strict documentation pass. Exact-int64 regression and four generic domains
have fixed continuation gates in the
[direct keyed top-k proposal](keyed-topk-research.md). The canonical run did
not pass: 3 of 24 exact cases exceeded the strict-core regression bound and 1
of 24 generic cases exceeded the `heapq` regression bound. Semantic and memory
requirements passed. See the
[adaptive keyed top-k research record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk.md).
The adaptive native commit passes hosted ASan/UBSan and source-build CI on
Linux with CPython 3.9–3.14, Windows with CPython 3.11/3.14, and macOS with
CPython 3.11/3.14. A fresh build-only wheel matrix and a passing complete
performance protocol remain required before any promotion decision.

An unchanged-code block-timed confirmation then placed all four failures and
both controls above their fixed `0.87x` bound. Exact failures measured
`0.95x–1.00x` against the strict core and the generic failure measured `1.33x`
over `heapq`, consistent with host variability. The
[confirmation record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-confirmation.md)
does not replace the failed canonical gate; a new complete block-timed
protocol is required for reconsideration. That protocol is now pre-registered
in the proposal: it retains all 48 cases, uses 11 rotated three-call blocks,
and makes median paired ratios the primary statistic. The implementation was
committed before execution, and the complete gate passed: 19 of 24 exact
cases reached `1.20x` over `heapq`, exact comparisons with the strict core
ranged from `0.94x–1.02x`, and all generic comparisons beat `heapq` by
`1.05x–1.36x`. The
[complete block-timed record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-block-canonical.md)
preserves the earlier failure separately. The pass authorizes only the
remaining private callable and isolated-memory experiments.

Those stage-three experiments are now complete under a separately
pre-registered protocol. Twenty-two of 24 common `itemgetter`, `attrgetter`,
and `lambda` cases reached `1.10x` over `heapq`, none fell below `0.90x`, and
all exact key-call probes passed. Across eight isolated memory cases, the
adaptive core used `0.28x–0.43x` the traced peak of `heapq`; all four
`k=100,000` cases passed the fixed 20% reduction target. The
[practical-callable and memory record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-practical.md)
retains every timing block and child-process sample. A private API review and
fresh build-only wheel matrix are next; no public symbol or release is
approved.

The subsequent [private promotion review](topk-api-review.md) selects a
provisional `top_k`/`top_k_with_info` contract, structured diagnostics,
pre-key memory-guard semantics, and adaptive heap/full-sort fallbacks. It
promotes the experiment only to an implementation candidate; no public name
is added. Adversarial review also reproduced a process crash when `key`
resized an exact input list while the C core held a borrowed item. The private
loop is now hardened to retain the current record and raise `RuntimeError` for
size changes caused by key evaluation or generic comparison. The affected
candidate passes a warning-clean local build, all 156 optimized tests, and
strict documentation. The unchanged practical performance/memory protocol was
then repeated on hardened commit `e0d6107` and passed: 19 of 24 callable cases
reached `1.10x`, none fell below `0.90x`, and adaptive traced peak memory
remained `0.28x–0.43x` of `heapq`. The
[separate safety revalidation](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-practical-safety.md)
preserves all samples. The hardened branch then passed
[source-build CI](https://github.com/bielelias/bielsort/actions/runs/31060360543)
for Linux CPython 3.9–3.14, Windows 3.11/3.14, and macOS 3.11/3.14; public
stubs and strict documentation also passed. Hosted
[ASan/UBSan](https://github.com/bielelias/bielsort/actions/runs/31060360542)
passed the complete suite. Finally, the non-publishing
[wheel matrix](https://github.com/bielelias/bielsort/actions/runs/31060438846)
built, tested, inspected, and uploaded wheels for Linux, Windows, macOS Intel,
and macOS Apple Silicon from exact commit `f7565bd`, plus its source
distribution. Every publication job was skipped.

The unified-façade experiment is now implemented privately. It combines
natural ordering and explicit keys, uses immutable normalized diagnostics, and
switches generic workloads from partial selection to a full stable sort at the
pre-registered `k >= n/8` crossover. Its 50-case canonical gate passed without
retuning: all correctness, routing, and semantic probes passed; no paired
median fell below `0.85x`; and 47 cases reached `0.95x` or better. Signed-int64
cases measured `1.49x–4.45x`, while the retained natural-string minimum was
`0.91x`. The
[versioned façade record](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-unified-topk-facade.md)
links every raw sample. Both optimized and local ASan/UBSan runs pass all 174
tests, along with warning-clean compilation, runtime/stub checks, strict Python
3.9 typing, and strict docs. The exact implementation also passed fresh hosted
[source-build CI](https://github.com/bielelias/bielsort/actions/runs/31062370200),
[ASan/UBSan](https://github.com/bielelias/bielsort/actions/runs/31062370239),
[strict documentation](https://github.com/bielelias/bielsort/actions/runs/31062370208),
and a
[non-publishing wheel matrix](https://github.com/bielelias/bielsort/actions/runs/31062939080)
on Linux, Windows, macOS Intel, and macOS Apple Silicon. No public name,
version, merge, or publication is approved.

The private streaming top-k protocol now has a first implementation and an
unchanged-gate canonical record. All semantics passed, including one-shot
consumption, stable ties, one key call per record, early release, and the
pre-consumption memory guard. Every timing case stayed at or above `1.00x`
`heapq`; 8 of 12 signed-int64 cases reached `1.10x`, all 12 generic cases
reached the `0.95x` floor, and `k=100,000` reached `1.19x–1.80x`. Memory versus
the materializing façade passed at `0.00x–0.13x`.

The overall decision remains **failed** because candidate/`heapq` incremental
RSS at `k=100,000` measured `0.76x` for signed-int64 keys and `0.80x` for
string keys, above the fixed `0.70x` maximum. The
[canonical record](https://github.com/bielelias/bielsort/blob/research/streaming-topk-0.3/benchmarks/results/2026-08-06-streaming-topk.md)
preserves all samples. An earlier attempt inherited the timing parent's RSS
high-water mark and is versioned explicitly as invalid; the corrected harness
uses a worker-ready checkpoint and parent-sampled Linux RSS. The next private
step may reduce the retained layout and repeat the same gate, but must not
weaken or replace this failed result. No runtime symbol is public.

Implementation commit `ddb8ff2` performed that retained-layout reduction. It
reuses the eventual result list, stores only normalized key/index state on the
exact path, reconstructs cached integers only after a late generic switch,
and replaces final merge buffers with in-place heapsort. The unchanged memory
gate now passes: `k=100,000` measures `0.62x` `heapq` for signed-int64 keys and
`0.67x` for strings, with `0.11x` the materializing façade in both cases. All
generic timing checks pass and the minimum of all 24 cases is `1.02x`.

That second canonical decision is still **failed** because 7 of 12 exact
cases reached `1.10x`, one short of the fixed requirement; the medium natural
smallest case measured approximately `1.095x`. The
[compact-layout record](https://github.com/bielelias/bielsort/blob/research/streaming-topk-0.3/benchmarks/results/2026-08-06-streaming-topk-compact.md)
is retained independently. A bounded medium-`k` finishing optimization may be
tested next, while the already passing large-`k` in-place layout and all fixed
thresholds remain unchanged.

That finishing pass is now complete. Commit `0b96727` added stable medium-`k`
Radix finishing while retaining the compact large-`k` layout. Its canonical
memory ratios passed at `0.62x` `heapq` for signed-int64 records and `0.66x`
for strings, and all generic timing cases passed, but the exact count remained
7 of 12. The independent
[Radix record](https://github.com/bielelias/bielsort/blob/research/streaming-topk-0.3/benchmarks/results/2026-08-06-streaming-topk-radix.md)
is preserved as **failed**.

A following exact heap/Radix optimization at commit `e56c96d` also passed
semantics, the no-regression floor, generic timing, and both memory gates. Its
large exact cases reached `1.74x–1.90x`, while signed-int64 and string memory
at `k=100,000` remained `0.63x` and `0.67x` `heapq`. Natural smallest
selection at `k=10,000` measured `1.08x`, leaving the decision at 7 of 12
again. The separate
[heap optimization record](https://github.com/bielelias/bielsort/blob/research/streaming-topk-0.3/benchmarks/results/2026-08-06-streaming-topk-hole.md)
is therefore also **failed**.

The final bottom-up Floyd repair passes 189 optimized and sanitized local
tests plus warning-clean compilation, strict typing, and strict docs. Its
exact-only screening still reached 7 of 12 target cases, so no further
canonical run, hosted promotion matrix, public API, merge, or release is
approved. Future streaming work should begin with a new pre-registered idea
or external workload evidence rather than rerunning this unchanged gate.

The subsequent [market opportunity review](market-opportunities.md) pauses
new algorithm variants. NumPy, Polars, and Arrow already provide mature
indirect sorting and indexed application in columnar storage, while
more-itertools already addresses sorting aligned Python iterables together.
The remaining plausible niche is a compact stable reorder plan for aligned
Python sequences without mandatory container conversion. Existing compact
permutation evidence makes this the strongest 0.3 discovery candidate, but
only functional demand—not large-scale performance demand—is established.
The next gate is a separately pre-registered API/usability and end-to-end
baseline review; no implementation, public name, merge, or release follows
from the market review alone.

That gate is now frozen in the
[compact reusable reorder-plan review](reorder-plan-api-review.md). It selects
provisional `argsort(values, *, reverse=False)` and `Permutation.apply()`
semantics for aligned reusable sequences, explicitly defers `key=` and
`apply_many()`, and fixes complete-flow comparisons with direct Python,
`more_itertools.sort_together()`, end-to-end NumPy conversion, and
NumPy-resident negative controls. New thresholds cover semantics, usability,
time, isolated peak RSS, typing, sanitizers, source builds, and wheels.
Existing prototype results do not satisfy this new protocol. No public export,
version change, merge, tag, or publication is authorized yet.

The corresponding private façade, 32-/64-bit buffer fixture, contract tests,
and complete-flow benchmark harness are now implemented on the focused
research branch. The harness refuses canonical mode unless the exact frozen
sizes, workloads, repetition counts, optional baselines, output artifacts, and
a clean committed tree are present.

The first attempt completed the unchanged timing grid but cannot be a decision
run: every memory worker produced `0 / 0` because it subtracted a post-input
`ru_maxrss` high-water mark, and Markdown generation then rejected the
undefined ratio. Its JSON and diagnosis are retained in the
[invalid-attempt record](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical-invalid-ru-maxrss.md).
The corrected, pre-registered memory method waits at a child-ready checkpoint
and is sampled by the Linux parent every 0.5 ms. No workload, threshold, or
algorithm changed.

The first correction produced valid nonzero sampling but still included the
post-operation reference order used only for validation. Its
[validation-overlap record](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical-invalid-validation-rss.md)
preserves the passing time grid and void RSS values. A final pre-registered
`operation-complete` handshake now stops parent sampling before validation.
Both invalid attempts remain versioned and all original gates remain binding;
the invalid values do not contribute to the final decision.

The corrected
[canonical reorder-plan record](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-canonical.md)
is now complete from clean commit `8886573`. All frozen time gates passed:
each of the six disordered large cases cleared the direct-Python,
`sort_together()`, and end-to-end NumPy target counts. At one million records,
the three disordered complete flows were `4.83x–5.88x` faster than direct
Python and used `0.44x–0.55x` its incremental peak RSS. The overall gate still
**failed** because the nearly ordered memory control reached `1.1205x` direct
Python, above the unchanged `1.10x` ceiling. The private API is not approved
for promotion. Any continuation must pre-register a new, narrow memory
hypothesis and preserve this result.

That continuation is now pre-registered in the
[nearly ordered reorder-plan memory protocol](reorder-plan-memory-continuation.md).
It attributes the likely excess to the eager `PySequence_List` pointer
snapshot and permits only replacing it with `PySequence_Fast` plus adapting
the internal fallback to fast sequences. All original gates remain binding;
the focused one-million-record nearly ordered median must additionally reach
at most `1.05x` direct Python's RSS, with at least two of three paired samples
at or below `1.10x`. No implementation change or new measurement is claimed
by the protocol itself.

The bounded implementation now acquires private argsort inputs through
`PySequence_Fast`, so exact built-in lists and tuples receive only an owned
reference during the operation while subclasses and custom sequences retain
materialization. The internal Timsort route accepts either fast-sequence
representation. New tests cover every route for exact list/tuple inputs,
materialized reusable sequences, source resizing during generic comparison,
and the frozen focused-gate calculation. The dedicated continuation harness
is implemented. All 212 optimized and locally sanitized tests pass, along with
warning-clean compilation, strict typing/stub comparison, and strict
documentation.

The single clean-tree
[memory-continuation result](https://github.com/bielelias/bielsort/blob/research/reorder-plan-0.3/benchmarks/results/2026-08-06-reorder-plan-memory-continuation.md)
passed without changing a gate. Nearly ordered median RSS reached `0.9928x`
direct Python, all three paired ratios stayed below `1.10x`, and its time
ratios were `1.29x` at 100,000 and `0.97x` at one million. All original gates
also passed: the three disordered one-million-record flows measured
`5.56x–6.79x` direct Python and `0.39x–0.50x` its incremental peak RSS. The
earlier failed canonical result remains preserved. Hosted source-build,
sanitizer, documentation, and build-only wheel matrices plus a final API
review are still required before any promotion decision.

## Resume checklist

Start from the repository root and inspect the current evidence:

```bash
git status --short --branch
git log -8 --oneline --decorate
python -m unittest discover -s tests -v
```

Then read this page, `ROADMAP.md`, `CHANGELOG.md`, and `docs/RELEASING.md`.
Work on one focused branch at a time and update this page when a gate changes.
