# Structured keyed-int64 diagnostics — 2026-08-04

## Decision

The structured diagnostic is technically viable and its memory formulas track
the measured native peaks closely. Keep it internal while the public API and
budget semantics are designed.

The public `bielsort` namespace and the published 0.1 package remain unchanged.

## Internal research entry point

Maintainers can currently inspect the experimental result through the private
native module:

```python
from operator import attrgetter
from bielsort_native import _bielsort

ordered, info = _bielsort._sort_by_int64_key_prototype_with_info(
    records,
    attrgetter("timestamp"),
)
```

This name begins with an underscore deliberately. Applications must not depend
on it, and it is not re-exported by `bielsort`.

## Diagnostic schema

| Field | Meaning |
|---|---|
| `strategy` | Human-readable selected strategy |
| `algorithm` | `trivial`, `already-sorted`, `counting`, or `radix` |
| `reason` | Why that algorithm was selected |
| `n` | Number of materialized records |
| `key_domain` | Currently always `signed-int64` |
| `key_min`, `key_max` | Minimum and maximum evaluated keys |
| `key_span` | Unsigned distance between maximum and minimum |
| `radix_passes` | Executed variable Radix digits, otherwise `None` |
| `normalized` | Whether keys were shifted by the minimum |
| `stable` | Stability contract; currently always `True` |
| `key_calls` | Number of key evaluations; must equal `n` |
| `estimated_variable_auxiliary_bytes` | Formula for the selected path |
| `worst_case_variable_auxiliary_bytes` | Architecture-derived compact-Radix upper path |
| `memory_estimate_scope` | Explicit exclusions from the estimate |
| `prototype` | Prevents confusing the result with a stable public contract |

For an empty input, key minimum, maximum, span, and Radix passes are `None`.

## Memory formulas

The estimates cover result-list item pointers and variable native buffers above
the caller-owned input. They are derived from `sizeof(PyObject *)` and
`sizeof(Py_ssize_t)`, rather than assuming a 64-bit process:

- already ordered/trivial non-empty input: `(pointer_size + 8) * n`;
- compact Radix and native worst case: `(2 * pointer_size + 16) * n`;
- Counting conversion phase: `(pointer_size + 12) * n`;
- Counting sorting phase:
  `(2 * pointer_size + 4) * n + ssize_size * (key_span + 1)`;
- Counting estimate: the larger of its conversion and sorting phases.

On the current 64-bit build, these reduce to `16 * n` for an already ordered
input, `32 * n` for Radix, and generally
`20 * n + 8 * (key_span + 1)` for Counting. Deriving the values in C keeps the
diagnostic meaningful for the project's supported 32-bit Windows wheel too.

They deliberately exclude input objects, allocator bookkeeping and rounding,
the fixed C stack, interpreter state, and unrelated process memory. Therefore,
they are planning estimates, not hard RSS guarantees.

## Formula check at one million records

The observed RSS values come from the
[compact-buffer benchmark](2026-08-04-keyed-int64-compact.md).

| Distribution | Algorithm | Estimated | Observed median RSS |
|---|---|---:|---:|
| dense | Counting | 22.89 MiB | 22.72 MiB |
| timestamp | Radix, 4 passes | 30.52 MiB | 30.63 MiB |
| int32 | Radix, 3 passes | 30.52 MiB | 30.60 MiB |
| int64 | Radix, 6 passes | 30.52 MiB | 30.57 MiB |
| nearly sorted | Counting | 26.70 MiB | 26.69 MiB |

This close local agreement validates the buffer accounting, not a universal RSS
promise. Other allocators, operating systems, architectures, and Python builds
can add different overhead.

## Safe direction for a memory guard

A parameter named simply `memory_budget` would imply control over the whole
process, which BielSort cannot honestly guarantee. The narrower initial name
should be `max_native_auxiliary_bytes`.

For a sized input, the safe selection sequence is:

1. Read `n` without evaluating any key.
2. Compute the architecture-derived native worst case as
   `(2 * pointer_size + 16) * n` (`32 * n` on this 64-bit build).
3. If it fits, enter the native path and call each key once.
4. If it does not fit, either delegate directly to Timsort before any key call
   or raise before any key call, according to an explicit policy.

This avoids the incorrect sequence “evaluate keys, exceed budget, call
`sorted(key=...)`”, which would evaluate user code twice.

Important limitations remain:

- A Timsort fallback has its own allocations and is not constrained by the
  native-buffer estimate.
- An unsized iterable must first be materialized, creating a separate memory
  cost. The initial guarded API should accept sized sequences only or state
  materialization cost separately.
- A strict total-memory promise would require allocator-aware accounting or an
  external sorter, neither of which belongs in the first keyed API.

## Validation

- 45 functional and stress tests passed.
- The diagnostic contract is tested for empty, ordered, Counting, and full
  signed-int64 Radix inputs.
- ASan and UBSan passed all 45 tests.
- The structured function remains absent from the public package namespace.

## Next implementation gate

> Follow-up: the
> [native-memory guard report](2026-08-04-keyed-int64-memory-guard.md)
> implements and measures the private guard while retaining the public 0.1
> API.

Before a public 0.2 candidate:

1. Resolve the strict-int64 versus generic Timsort fallback contract.
2. Repeat correctness and wheel validation on supported CPython versions.
3. Choose final public names, result shape, and type annotations.
4. Publish a documented 0.2 release candidate only after those gates pass.
