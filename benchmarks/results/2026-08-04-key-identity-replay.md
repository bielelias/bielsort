# Exact key-identity replay — 2026-08-04

## Decision

**Accept exact key-object preservation in the private adaptive selector.** The
progressive fallback now gives CPython Timsort the same objects returned by the
user's `key` callable, rather than newly created integers with equal values.
This removes the known observable compatibility gap with `sorted(key=...)`.

The change retains the major random-int64 speedup and did not increase measured
peak RSS in the sampled one-million-record cases. It remains private 0.2
research; the public BielSort 0.1 API and version are unchanged.

## Why identity can matter

Ordinary integer ordering depends only on value, so a reconstructed Python
integer normally behaves identically. A custom key type can nevertheless
compare itself with an integer and inspect that integer with `is`. CPython
Timsort compares the exact objects originally returned by `key`; a transparent
fallback should do the same.

The regression test places a custom identity-aware key after 4,095 exact
signed-int64 keys. Its cross-type comparator rejects any integer whose identity
is not one of the original key results. Both ascending and reverse adaptive
fallbacks now match `sorted()` and call `key` once per record in input order.

## Ownership and memory

During progressive extraction, C owns one temporary reference and one pointer
slot for each evaluated exact key. If extraction encounters a generic key,
those exact objects are transferred by reference to the one-shot replay cache.
If every key is native-eligible, all temporary references and the pointer
buffer are released before Counting or Radix allocates its destination buffers.

The extraction phase therefore uses at most 24 bytes per record on a 64-bit
build: result-list pointer, normalized int64 key, and exact-key pointer. Compact
Radix still peaks at the existing 32-byte variable-buffer estimate, so the
configured native worst-case guard remains unchanged. Key-object payloads and
allocator overhead are explicitly outside that estimate.

At one million records, three isolated RSS samples measured:

| Key distribution | `sorted(key=...)` | Adaptive BielSort | Ratio |
|---|---:|---:|---:|
| random int64 | 24.85 MiB | 30.43 MiB | 1.22x |
| string fallback | 23.46 MiB | 22.98 MiB | 0.98x |

These ratios are effectively unchanged from the prior 1.23x and 0.98x local
checkpoint. They are operating-system RSS observations, not universal bounds.

## Median time

Five rotated samples ran locally on Linux x86-64 with CPython 3.11. Speedups
above 1.00x favor BielSort.

| Direction | Records | Key distribution | Adaptive path | Speedup |
|---|---:|---|---|---:|
| ascending | 10,000 | random int64 | Radix | 2.45x |
| ascending | 100,000 | random int64 | Radix | 2.73x |
| ascending | 1,000,000 | random int64 | Radix | 3.78x |
| ascending | 10,000 | string | progressive Timsort | 1.05x |
| ascending | 100,000 | string | progressive Timsort | 0.98x |
| ascending | 1,000,000 | string | progressive Timsort | 1.05x |
| reverse | 10,000 | random int64 | Radix | 2.53x |
| reverse | 100,000 | random int64 | Radix | 2.83x |
| reverse | 1,000,000 | random int64 | Radix | 3.86x |
| reverse | 10,000 | string | progressive Timsort | 1.03x |
| reverse | 100,000 | string | progressive Timsort | 0.92x |
| reverse | 1,000,000 | string | progressive Timsort | 1.00x |

Retaining exact references reduced random-int64 speedup by roughly 3%-5%
relative to the immediately preceding local checkpoint. The compatibility gain
is accepted because large native cases remain materially faster and generic
fallback stays near parity. The isolated 0.92x sample is retained as a
regression signal rather than hidden; more repetitions and hosted results are
needed before treating it as a stable penalty.

Raw samples:

- [`2026-08-04-key-identity-ascending.json`](2026-08-04-key-identity-ascending.json)
- [`2026-08-04-key-identity-reverse.json`](2026-08-04-key-identity-reverse.json)
- [`2026-08-04-key-identity-memory.json`](2026-08-04-key-identity-memory.json)

## Validation

- 85 tests pass in the optimized build.
- The same 85 tests pass under ASan and UBSan.
- The C extension compiles with `-Wall -Wextra -Werror`.
- Reference-count tests cover native commit and user-key exceptions.
- Identity-aware differential tests cover ascending and reverse replay.
- Existing stability, exception, full-int64, memory-guard, GC, Counting, Radix,
  sparse-run, and randomized differential tests remain green.

## Remaining gates

The identity discrepancy is resolved. Remaining work before a public 0.2
candidate is selector policy for known nearly-ordered/spaced losses, the public
API and typing contract, final user-facing diagnostics, documentation, and a
fresh supported-wheel matrix after those changes.

Nothing in this experiment was merged into `main` or published.
