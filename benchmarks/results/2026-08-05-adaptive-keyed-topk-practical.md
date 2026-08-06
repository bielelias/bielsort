# Adaptive keyed top-k practical callables and memory: 2026-08-05

## Decision

**Both separately pre-registered stage-three gates passed.** Twenty-two of 24
common-callable cases reached at least `1.10x` over `heapq`, versus the
required 18, and none fell below the fixed `0.90x` regression floor. All four
callables preserved stable identity, evaluated `key` exactly once per record
in encounter order, and made zero calls for `k == 0`.

The isolated-memory gate also passed. All eight cases had measurable traced
peaks, none exceeded the fixed `1.25x` adaptive/`heapq` ceiling, and all four
`k=100,000` cases met the required `0.80x` reduction target.

Passing authorizes a private API proposal and a build-only wheel validation.
It does not expose `top_k`, change the package version, create a tag, merge the
draft PR, or publish a package.

## Provenance and method

The protocol was fixed in commit `1c793b9`, the benchmark was implemented and
pushed in commit `1fe522c`, and the measured adaptive selection code remained
unchanged from commit `fdc9bb5`.

The callable section uses one million named-tuple records with dense int64
scores and stable duplicates. It combines four key-call shapes, `k` values
10, 100, and 1,000, and both directions. Each case receives one warm-up and
nine rotated paired blocks of three calls. The primary statistic is the
median of paired `heapq/adaptive` ratios.

The memory section runs before timing. Each of three samples per algorithm and
case uses a fresh child process, constructs the input before measurement,
retains the result while reading the peak, and validates stable object
identity after measurement. Incremental traced peak is primary; incremental
RSS and worker time are diagnostic only.

The raw JSON retains every block and worker sample, semantic probes,
configuration, provenance, environment, and machine-evaluated decisions:
[2026-08-05-adaptive-keyed-topk-practical.json](2026-08-05-adaptive-keyed-topk-practical.json).

## Common-callable timing

| Callable | Cases at least 1.10x | Adaptive vs `heapq` |
|---|---:|---:|
| `itemgetter(0)` | 6/6 | 1.50x–1.69x |
| `lambda record: record[0]` | 5/6 | 1.10x–1.20x |
| `attrgetter("score")` | 6/6 | 1.41x–1.58x |
| `lambda record: record.score` | 5/6 | 1.08x–1.22x |

The two cases below the `1.10x` target were retained rather than rounded into
successes:

| Callable | k | Direction | Adaptive vs `heapq` |
|---|---:|---|---:|
| `lambda record: record[0]` | 100 | largest | 1.099x |
| `lambda record: record.score` | 100 | largest | 1.078x |

Both remain above the `0.90x` regression floor. Across all 24 cases, the
complete range was `1.08x–1.69x`. Relative median absolute deviation across
the 48 algorithm/case series had a middle value of 1.87%, a 90th-percentile
value of 4.71%, and a maximum of 7.04%.

The result shows a practical distinction: C-level `itemgetter` and
`attrgetter` preserve larger gains, while Python `lambda` execution is shared
work that moves both algorithms closer together. The adaptive core still won
every measured case on this machine.

## Isolated peak memory

| Key domain | k | Direction | `heapq` traced | Adaptive traced | Adaptive/`heapq` |
|---|---:|---|---:|---:|---:|
| dense int64 | 1,000 | smallest | 111.7 KiB | 31.5 KiB | 0.28x |
| dense int64 | 1,000 | largest | 111.7 KiB | 31.5 KiB | 0.28x |
| dense int64 | 100,000 | smallest | 10.68 MiB | 3.05 MiB | 0.29x |
| dense int64 | 100,000 | largest | 10.68 MiB | 3.05 MiB | 0.29x |
| arbitrary-size integer | 1,000 | smallest | 111.7 KiB | 47.1 KiB | 0.42x |
| arbitrary-size integer | 1,000 | largest | 111.7 KiB | 47.1 KiB | 0.42x |
| arbitrary-size integer | 100,000 | smallest | 10.68 MiB | 4.58 MiB | 0.43x |
| arbitrary-size integer | 100,000 | largest | 10.68 MiB | 4.58 MiB | 0.43x |

The adaptive result used approximately 71% less traced peak memory for exact
int64 keys and 57% less for arbitrary-size integers. This agrees with code
inspection: reusable inputs do not receive an `O(n)` key cache, and the
adaptive implementation retains at most `O(k)` keys and native entries.

The process-RSS diagnostic recorded about 24.4 MiB of incremental high-water
usage for `heapq` at `k=100,000` and zero additional high-water pages for the
adaptive workers. Smaller cases were not measurable by RSS. These values are
reported in the raw record but are not used as a claim or gate because process
allocators can reuse already committed pages.

## Interpretation

Stage three closes the synthetic engineering evidence requested before API
design: common callables remain competitive, key-call semantics are exact,
and isolated traced memory shows a substantial `O(k)` advantage. The result
is about stable top-k selection of Python records, not complete sorting and
not the public BielSort 0.2 API.

The next step is a private promotion review that defines naming, signature,
fallback, memory-limit, and diagnostics behavior. External workload demand
and cross-platform wheel validation remain separate requirements before any
public release proposal.

## Environment

- Python: CPython 3.11.2
- Compiler: GCC 12.2.0
- Platform: Linux 6.7.0, x86-64, glibc 2.36

These measurements describe one machine and are not universal guarantees.
