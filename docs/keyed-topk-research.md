# Research proposal: direct stable keyed top-k

!!! warning "Design only"

    BielSort does not expose `top_k`. This page fixes the private experiment's
    contract and decision gates before implementation or canonical timing.

## User problem

The compact top-k prototype accepts a sequence of integer keys and returns a
reusable permutation. That is useful for parallel lists, but it is indirect
for the more common Python shape: a list of records with an integer field.

Examples include selecting:

- the ten slowest request records by latency;
- the largest transactions by signed amount;
- the lowest-cost route candidates;
- a stable leaderboard whose equal scores retain arrival order.

The eventual public idea is deliberately small:

```python
def top_k(
    iterable,
    k,
    *,
    key=None,
    largest=False,
): ...
```

It would return the selected records directly as a new fully sorted list. A
public API is not approved by this proposal.

## Stage-one private contract

The first native experiment will be named
`_topk_by_int64_key_prototype(iterable, k, key, largest=False, /)`. It targets
only exact signed-int64 key results so that the eligible core can be measured
without pretending that generic fallback semantics are already solved.

Its required behavior is:

- reject negative `k` before consuming the iterable;
- return `[]` for `k == 0` without consuming the iterable or calling `key`;
- otherwise consume the iterable once and call `key` exactly once per record;
- clamp `k` to the number of records;
- return at most `k` original objects in fully sorted order;
- preserve encounter order for equal keys for both smallest and largest;
- preserve exact object identity and leave reusable inputs unchanged;
- propagate exceptions raised by iteration or `key`;
- reject non-exact-int or out-of-int64 key results in this private stage.

For list and tuple inputs with small `k`, the intended algorithm is a native
stable heap using `O(n log k)` time and `O(k)` native entries. A one-shot
iterable must first be materialized, so its record references require `O(n)`
memory. The output always requires `O(k)` Python references.

## Why this is more practical than another permutation operation

Users can express the operation in one call and receive their original
records. They do not need to extract a key list, understand a private index
object, or apply that object to payload lists. The specialization remains
narrow: it is for large Python-native record collections, small `k`, and
exact signed-int64 keys. NumPy, DataFrame, and database-native data should
normally stay in those systems.

## Pre-registered benchmark

The canonical performance run will use one million tuple records, an
`operator.itemgetter(0)` key, `k` values 10, 100, and 1,000, four disordered
signed-int64 distributions, and both smallest and largest directions. That
produces 24 target cases. Each case will retain at least seven rotated timing
samples and compare:

1. the private native direct result;
2. `heapq.nsmallest()` or `heapq.nlargest()` with the same key;
3. full stable `sorted(..., key=..., reverse=...)[:k]` as a reference and
   context, not as the primary gate.

Construction of the record list is outside the timed region. Correctness is
checked by object identity against stable full sorting. A separate call-count
key validates exact key evaluation semantics outside timed samples.

The stage-one prototype advances only if:

1. every result is identity-equivalent to stable full sorting, including ties;
2. all call-count, empty, boundary, exception, and input-preservation tests
   pass;
3. at least 18 of 24 one-million-record target cases reach `1.25x` over the
   equivalent `heapq` operation;
4. no target case is more than 10% slower than `heapq`;
5. code inspection and tests confirm an `O(k)` native selection heap with no
   `O(n)` key array for reusable list or tuple inputs.

The fixed gates evaluate an eligible private core only. Passing them would
authorize work on a compatible fallback, memory guard, diagnostics, and API
review. It would not approve a public symbol, version bump, or release. A
failed gate will be recorded without changing thresholds after measurement.

## Reproduction

```bash
python benchmarks/keyed_topk_prototype.py \
  -n 100000 1000000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output keyed-topk.json
```

## First canonical result

The 2026-08-05 canonical run passed the unchanged stage-one gate. All 24
one-million-record cases were stable and identity-equivalent to full sorting.
Exactly 18 reached at least `1.25x` over `heapq`, no case regressed by more
than 10%, and the observed range was `1.09x–1.91x`.

All six cases below `1.25x` used full-range int64 keys, so magnitude-dependent
Python integer costs remain an explicit limitation. See the
[versioned result](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-keyed-topk.md)
and its linked raw samples. This result approves work on fallback and API
semantics only; the prototype remains private.

## Promotion questions after a passing core

Before a public proposal, BielSort would still need to answer:

- how generic and out-of-range keys fall back without a second key call;
- whether `key=None` should share the existing keyless top-k path;
- whether a conservative memory limit belongs in the API;
- how much advantage remains for common Python `lambda` and `attrgetter`
  callables;
- whether direct records or reusable indices represent actual user demand.

Until those questions have evidence, `_Permutation`, `apply_many()`, and the
new keyed operation remain implementation research.

## Stage two: compatible generic keys and memory guard

The next private candidate is an adaptive `_topk_by_key_prototype`. It starts
with normalized exact-int64 comparisons, but retains only the key objects of
the current `k` candidates. If an out-of-range integer or another Python key
type appears, it switches the existing heap to Python `<` comparisons and
continues without restarting iteration or calling `key` again.

The generic comparison contract follows stable sorting for well-behaved
strict weak orderings:

- compare keys with `<`, never compare records;
- treat keys as tied when neither is less than the other;
- use encounter position only to preserve stable ties;
- propagate key and comparison exceptions;
- keep at most `k` key references and `O(k)` native entries;
- use an exception-aware stable merge for the final `k` records rather than
  `qsort()`, whose comparator cannot propagate Python exceptions.

The strict `_topk_by_int64_key_prototype` remains unchanged so its versioned
stage-one result stays reproducible.

### Private memory guard

A private Python dispatcher will optionally accept
`max_native_auxiliary_bytes` and `on_memory_limit="heapq"` or `"raise"`.
With a limit, the input must be an exact list or tuple so the conservative
worst-case native allocation can be checked before calling `key`.

The estimate covers two `k`-entry native buffers: the selection heap and the
generic final-merge scratch space. It excludes the input objects and returned
Python list. If the limit is exceeded, the dispatcher either delegates to
`heapq.nsmallest()`/`nlargest()` before any key call or raises `MemoryError`
before any key call. This is a private research contract, not an approved
public signature.

### Pre-registered stage-two gates

Correctness and semantics are mandatory:

1. identity-equivalent results to stable full sorting for exact int64,
   arbitrary-size integers, strings, tuples, finite floats, and duplicate
   keys in both directions;
2. exactly one key call per encountered record, zero calls for `k == 0`, and
   correct propagation of iteration, key, and comparison exceptions;
3. guard decisions occur before key calls and both `heapq` and `raise`
   policies obey the fixed limit;
4. code inspection and tests confirm `O(k)` retained keys/native entries and
   no `O(n)` key array for reusable inputs.

The exact-int64 regression run reuses the 24 one-million-record stage-one
cases and seven rotated samples. It advances only if at least 18 cases remain
at or above `1.20x` over `heapq` and no adaptive case is more than 15% slower
than the frozen strict-int64 core.

The generic run uses 100,000 records, `k` values 10, 100, and 1,000, both
directions, seven rotated samples, and four domains: arbitrary-size integers,
strings, integer tuples, and finite floats. It advances only if no case is
more than 15% slower than `heapq`; acceleration is reported but is not a gate.

Passing these gates authorizes common-`lambda`/`attrgetter` and isolated-memory
experiments. It still does not approve `top_k`, a version bump, or a release.
Thresholds must not change after canonical measurements.

```bash
python benchmarks/keyed_topk_fallback.py \
  --exact-size 1000000 \
  --generic-size 100000 \
  -k 10 100 1000 \
  -r 7 \
  --json-output adaptive-keyed-topk.json
```

### First stage-two result

The 2026-08-05 canonical run did **not** pass the unchanged gate. Semantic and
`O(k)` memory requirements passed. Nineteen of 24 exact-int64 cases reached
`1.20x` over `heapq`, but 3 exceeded the allowed 15% regression against the
frozen strict core. One of 24 generic cases exceeded the allowed 15%
regression against `heapq`.

The implementation remains private. See the
[versioned failure report](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk.md)
and its linked raw samples. Any profiling or confirmation run must be
pre-registered separately and cannot erase this result.

### Pre-registered failure confirmation

The first follow-up changes no selection code and rechecks only the four
failed performance cases, plus two non-failing controls. Each case uses the
same deterministic data shape as the canonical run, three operation calls per
timed block, 15 rotated blocks, one untimed warm-up per algorithm, garbage
collection outside the timed region, and per-block average durations.

The exact cases compare adaptive with the frozen strict core at one million
records:

- dense, largest, `k=10`;
- dense, smallest, `k=1,000`;
- int32, largest, `k=100`;
- heavy duplicates, smallest, `k=100` as a control.

The generic cases compare adaptive with `heapq` at 100,000 records:

- arbitrary-size integer, smallest, `k=100`;
- string, smallest, `k=100` as a control.

The confirmation is consistent with host variability only if every failed
case reaches at least `0.87x` against its comparator and both controls remain
at least `0.87x`. Otherwise the regression is treated as reproducible and the
implementation must be profiled or redesigned. Passing this confirmation
does not retroactively pass stage two; a new complete canonical protocol
would still need separate pre-registration.

```bash
python -m benchmarks.keyed_topk_confirmation \
  --exact-size 1000000 \
  --generic-size 100000 \
  --blocks 15 \
  --calls-per-block 3 \
  --json-output adaptive-keyed-topk-confirmation.json
```

### Confirmation result

The unchanged-code confirmation was consistent with host variability: every
failed case and control exceeded the fixed `0.87x` bound. The three exact
cases measured `0.95x–1.00x` against the strict core, and the previously
failed huge-integer case measured `1.33x` over `heapq`.

See the
[versioned confirmation](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-confirmation.md).
The original stage-two gate remains failed. A complete block-timed protocol
must be pre-registered before any new promotion decision.

### Pre-registered complete block-timed protocol

The second complete stage-two decision keeps the adaptive selection code
unchanged and repeats all 48 original cases with the block method used by the
focused confirmation. It complements the first failed canonical run; it does
not delete, replace, or reinterpret that result.

The exact section retains all 24 combinations of one million records, the
`dense`, `int32`, `int64`, and `heavy-duplicates` domains, `k` values 10, 100,
and 1,000, and both directions. Each case compares `heapq`, the frozen strict
int64 core, and the adaptive core. The generic section retains all 24
combinations of 100,000 records, the arbitrary-size integer, string, integer
tuple, and finite-float domains, the same `k` values, and both directions. It
compares `heapq` and the adaptive core.

For every case, the protocol will:

1. construct records and the stable full-sort identity reference outside the
   timed region;
2. run one untimed, identity-checked warm-up per algorithm;
3. collect 11 paired blocks, rotating algorithm order between blocks;
4. time three complete calls per algorithm inside each block and retain their
   per-call average as the block sample;
5. keep garbage collection outside timed regions and identity-check every
   result;
6. preserve every raw block sample, the environment, and the fixed
   configuration in a versioned JSON record.

The primary comparisons are paired within each block. Each case reports the
median of `comparator block / adaptive block`; ratios of independent medians
are context only and cannot decide the gate. Timing spread is reported with
the median absolute deviation, but it is diagnostic rather than an exclusion
rule. The benchmark implementation itself must be committed before the one
canonical execution.

Correctness, one-call key semantics, memory-guard semantics, and the `O(k)`
retained-key contract remain mandatory from stage two. The complete timing
gate passes only if the canonical shape is present and:

1. at least 18 of 24 exact cases have a median paired adaptive speedup of at
   least `1.20x` over `heapq`;
2. no exact case has a median paired adaptive speedup below `0.87x` against
   the frozen strict core;
3. no generic case has a median paired adaptive speedup below `0.87x` against
   `heapq`.

A passing result permits the already-planned common-`lambda`/`attrgetter` and
isolated-memory experiments, followed by a private promotion review. It does
not approve a public `top_k`, a version bump, a tag, or a package release. A
failure remains versioned and requires profiling or redesign before another
complete protocol is proposed; thresholds will not change after execution.

```bash
python -m benchmarks.keyed_topk_block_canonical \
  --exact-size 1000000 \
  --generic-size 100000 \
  -k 10 100 1000 \
  --blocks 11 \
  --calls-per-block 3 \
  --implementation-commit COMMIT_SHA \
  --json-output adaptive-keyed-topk-block-canonical.json
```

### Complete block-timed result

The 2026-08-05 execution passed the fixed complete gate. Nineteen of 24 exact
cases reached `1.20x` over `heapq`; no exact case fell below `0.87x` against
the frozen strict core, and no generic case fell below `0.87x` against
`heapq`. The observed paired ranges were `1.10x–1.82x` over `heapq` and
`0.94x–1.02x` against the strict core for exact inputs, and `1.05x–1.36x`
over `heapq` for generic inputs.

The [versioned complete result](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-block-canonical.md)
preserves all samples and links the earlier failed gate independently. The
pass authorizes common-callable and isolated-memory experiments only; the
operation and dispatcher remain private.

## Stage three: practical callables and isolated memory

The next private decision tests two remaining practical questions without
changing the adaptive selection code: whether its advantage survives common
Python key-call shapes, and whether its `O(k)` design produces a useful
measured memory bound rather than only a structural claim.

### Pre-registered callable protocol

All performance cases use the same one-million-element collection of
two-field named-tuple records with dense signed-int64 scores and stable
duplicates. Only the callable changes:

- `operator.itemgetter(0)`;
- `lambda record: record[0]`;
- `operator.attrgetter("score")`;
- `lambda record: record.score`.

Combining the four callables with `k` values 10, 100, and 1,000 and both
smallest and largest directions produces 24 target cases. Each case compares
the unchanged adaptive core with `heapq.nsmallest()` or `heapq.nlargest()`.
Record construction and the stable identity reference remain outside timing.

Each algorithm receives one untimed warm-up. The measurement then retains
nine paired blocks of three complete calls, rotates algorithm order, keeps
garbage collection outside timed regions, and identity-checks every result.
The primary statistic is the median of paired `heapq/adaptive` block ratios;
independent median ratios and median absolute deviations are diagnostic only.
A separate untimed probe must confirm exactly one key call per encountered
record for every callable and zero calls when `k == 0`.

The callable gate passes only if the complete canonical shape is present,
every semantic probe passes, at least 18 of 24 cases reach `1.10x` over
`heapq`, and no case falls below `0.90x`. These thresholds measure practical
usefulness while allowing callable cost shared by both algorithms to reduce
the larger core-only speedups.

### Pre-registered isolated-memory protocol

Peak memory is measured before performance timing so the supervisor has never
held a large workload. Every algorithm/domain/direction/repetition runs in a
fresh child process. The child constructs one million named-tuple records,
starts measurement only after construction and garbage collection, retains
the returned result while reading the peak, and validates exact stable object
identity after stopping measurement.

The eight memory cases combine:

- dense exact signed-int64 scores and arbitrary-size integer scores;
- `k` values 1,000 and 100,000;
- smallest and largest directions;
- `operator.attrgetter("score")` for both adaptive and `heapq` operations.

Each case retains three isolated samples per algorithm. Incremental traced
peak memory is the primary metric because it observes Python allocator and
`PyMem` blocks after the input baseline; incremental process peak RSS is
retained as an operating-system diagnostic. Worker elapsed time is also
diagnostic and cannot decide the memory gate.

The memory gate requires a measurable median traced peak for every comparator,
no adaptive/comparator median ratio above `1.25x`, and at least two of the four
`k=100,000` cases at or below `0.80x`. Code inspection and the existing guard
must still confirm at most `O(k)` retained key objects/native entries and no
`O(n)` key array for reusable inputs. RSS values are reported honestly but
cannot fail the gate because allocator high-water behavior is platform
dependent.

Both callable and memory gates must pass before a private promotion review.
Passing would authorize an API proposal and build-only wheel validation, not
a public symbol, version bump, tag, merge, or package release. Thresholds and
canonical shapes will not change after measurement, and a failed result will
remain versioned.

```bash
python -m benchmarks.keyed_topk_practical \
  --time-size 1000000 \
  --memory-size 1000000 \
  -k 10 100 1000 \
  --time-blocks 9 \
  --calls-per-block 3 \
  --memory-k 1000 100000 \
  --memory-repetitions 3 \
  --implementation-commit COMMIT_SHA \
  --json-output adaptive-keyed-topk-practical.json
```

### Stage-three result

The 2026-08-05 canonical execution passed both fixed gates. Twenty-two of 24
callable cases reached `1.10x` over `heapq`, no case fell below `0.90x`, and
all one-call/zero-call semantic probes passed. C-level `itemgetter` and
`attrgetter` shapes measured `1.41x–1.69x`; Python `lambda` shapes measured
`1.08x–1.22x`.

All eight isolated-memory cases passed. The adaptive core used 0.28x–0.29x
the traced peak of `heapq` for exact int64 keys and 0.42x–0.43x for
arbitrary-size integers, while retaining the structural `O(k)` contract. See
the [versioned practical result](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-practical.md).

The pass authorizes a private promotion and API-design review plus build-only
wheel validation. The operation remains private and no release is approved.

## Private promotion review

The [private API review](topk-api-review.md) promotes this work to an API
implementation candidate but deliberately keeps every symbol private. It
selects the future `top_k`/`top_k_with_info` shape, stable compatibility rules,
structured diagnostics, memory-guard behavior, and adaptive fallback model.

The review also found a native callback-safety defect: a `key` that resized an
exact input list could invalidate a borrowed item reference. The candidate now
keeps the current record alive and raises `RuntimeError` if `key` or generic
comparison changes the source length. The affected performance/memory gates,
sanitizers, source CI, and build-only wheels must pass again before further
promotion work.

The exact stage-three performance and isolated-memory protocol was repeated on
the hardened commit `e0d6107` and passed again. Nineteen of 24 callable cases
reached `1.10x`, none fell below `0.90x`, and adaptive traced peak memory
remained `0.28x–0.43x` of `heapq`. The
[separate safety revalidation](https://github.com/bielelias/bielsort/blob/research/stable-topk-0.3/benchmarks/results/2026-08-05-adaptive-keyed-topk-practical-safety.md)
preserves every sample without replacing the earlier result. Hosted
sanitizers, source CI, and build-only wheels remain pending.
