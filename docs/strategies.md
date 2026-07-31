# Strategy selection

BielSort is a hybrid library. It does not claim that one sorting algorithm is
best for every input. The selector takes a conservative path: an unnecessary
fallback may cost an optimization opportunity, but it must never change the
correct result.

## Selection flow

<div class="biel-flow" markdown>

<div class="biel-flow-step" data-step="Step 1" markdown>
### Preserve Python semantics

`key=` or `reverse=` immediately uses Timsort.
</div>

<div class="biel-flow-step" data-step="Step 2" markdown>
### Handle small inputs

Fewer than 2,048 elements use Timsort and avoid native buffer overhead.
</div>

<div class="biel-flow-step" data-step="Step 3" markdown>
### Sample the shape

Up to 256 evenly spaced values detect incompatible types, large magnitudes,
and nearly monotonic data.
</div>

<div class="biel-flow-step" data-step="Step 4" markdown>
### Scan compatible integers

A full scan determines order, numeric amplitude, and varying radix digits.
</div>

<div class="biel-flow-step" data-step="Step 5" markdown>
### Choose a native path

Large dense ranges may use Counting Sort; other compatible ranges use Radix
Sort.
</div>

<div class="biel-flow-step" data-step="Step 6" markdown>
### Return Python objects

The algorithms permute the original object references and preserve stable
ordering.
</div>

</div>

## Timsort fallback

<span class="biel-pill">Compatibility path</span>

CPython's built-in Timsort is selected for:

- fewer than 2,048 elements;
- already ordered or nearly monotonic data;
- floats, strings, mixed values, and general Python objects;
- integer subclasses;
- integers outside the signed 64-bit range;
- any call using `key=` or `reverse=`.

This is not an error or a degraded correctness mode. Timsort is often the best
algorithm for these inputs, especially when it can exploit existing ordered
runs.

## Native Counting Sort

<span class="biel-pill">Dense integer fast path</span>

Counting Sort is considered when all values are exact signed 64-bit Python
integers and:

- the input contains at least 250,000 elements;
- the numeric amplitude is below 4,000,000;
- the amplitude remains suitably proportional to the input size.

The implementation is stable. It compacts normalized keys to 32 bits and uses
phased buffers to reduce peak memory. If optional Counting Sort allocations
cannot be created, the selector can continue with Radix Sort.

## Native Radix Sort

<span class="biel-pill">General int64 fast path</span>

The stable LSD Radix Sort uses 11-bit digits. Signed order is transformed into
monotonic unsigned keys, and constant digits are skipped. For signed 64-bit
integers, at most six varying digit passes are needed.

When subtracting the minimum key reduces the effective range, the selector
normalizes the keys first. This can turn a range such as `[-1000, 1000]` into
`[0, 2000]` and reduce the required passes.

## Complexity

For `n` elements, numeric range `k`, and `p` varying radix digits:

| Strategy | Time | Additional memory | Best fit |
|---|---:|---:|---|
| Counting Sort | `Θ(n + k)` | `Θ(n + k)` | large, dense int64 ranges |
| Radix Sort | `Θ(pn)`, `1 ≤ p ≤ 6` | `Θ(n)` | large, varied int64 ranges |
| Timsort | best `Θ(n)`, worst `Θ(n log n)` | `O(n)` | general or structured data |

Because `p` is bounded for signed 64-bit integers, the native radix work is
linear in `n` for this fixed-width domain. That statement does not apply to
arbitrary-size Python integers, which use Timsort.

## Stability and object identity

The native algorithms move existing Python object pointers; they do not
recreate equal integers. Distribution steps preserve encounter order, so equal
values retain their relative object-identity order.

## GIL policy

- `sort()` owns a private, unpublished list copy and can release the GIL during
  native Counting/Radix data movement;
- `sort_in_place()` keeps the GIL because the list belongs to the caller and
  must not be exposed in a partially permuted state.

## Inspect the decision

Use a diagnostic API while benchmarking or reporting a problem:

```python
import bielsort

ordered, strategy = bielsort.sort_with_strategy([3, 1, 2] * 100_000)
print(strategy)
```

Diagnostic wording can change as the pre-1.0 heuristics evolve. Application
correctness should never depend on the exact string.
