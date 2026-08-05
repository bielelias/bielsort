# Architecture

## Public layer

The canonical `bielsort` package exposes five stable 0.2 functions:

- `sort`: returns a new sorted list;
- `sort_in_place`: mutates an exact list and returns `None`;
- `sort_with_strategy` and `sort_in_place_with_strategy`: diagnostic variants
  that also report the selected strategy;
- `sort_with_info`: returns a new sorted list and structured selection details.

The earlier `biel_sort*` spellings remain compatibility aliases. The older
`bielsort_native` package import also remains available for
compatibility, but new applications should use `import bielsort`.

Version 0.2 routes new-list `sort(key=...)` through the
internal adaptive selector. Exact signed-int64 results may use stable native
Counting or Radix; incompatible results use exact-object Timsort replay. The
in-place key path and keyless reverse path deliberately remain on Python's
built-in sorting to avoid generic-key regressions and semantic drift.

The same release adds `sort_with_info()` and the immutable `SortInfo` value
for explicit keyed calls. The public object normalizes private selector names
and exposes only reviewed fields. Its optional native-memory guard makes a
conservative pre-key decision for exact `list` or `tuple` inputs; it does not
claim to limit total process memory. The preflight bound is the maximum of the
compact-Radix buffers and the largest Counting table that the selector could
legally choose for that input size.

## Native selection

The C extension first handles trivial and small inputs, then samples up to 256
uniform positions.

The sample provides conservative early fallback for:

- incompatible object types or integer magnitudes;
- nearly nondecreasing inputs;
- nearly nonincreasing inputs.

For compatible inputs, a full scan:

- converts signed integer order to monotonic unsigned keys;
- counts ascending and descending transitions;
- determines the minimum, maximum, and varying radix digits;
- normalizes keys by the minimum when that reduces work.

## Counting path

Counting sort is selected only when:

- `n >= 250000`;
- the numeric amplitude is below a fixed memory limit;
- the amplitude is proportional to `n`.

The distribution is stable. If the optional count table cannot be allocated,
the implementation continues with radix sort.

After the range scan, normalized Counting Sort keys are compacted to
`uint32_t`; this is safe because the counting range limit is below four
million. The temporary full entries can then be released before allocating the
output pointer array and count table. This phased allocation reduces peak
memory while preserving the original Python objects and their stable order.

If an optional Counting Sort allocation fails after compaction, the full entry
representation is reconstructed and the implementation attempts Radix Sort.

## Radix path

The LSD radix uses 11-bit digits and at most six stable passes for signed
64-bit integers. Digits that are constant for the entire input are skipped.

Two native entry buffers hold Python object pointers and transformed keys.
Objects are not recreated. These buffers apply only to the Radix Sort path;
Counting Sort uses the compact representation described above.

## GIL policy

The new-list API owns an unpublished list copy and releases the GIL during
counting/radix data movement.

The in-place API keeps the GIL because the caller-owned list may otherwise be
mutated concurrently.

## Stability and references

Counting and radix distribution preserve encounter order for equal keys. The
native core permutes the same multiset of object pointers already owned by the
list, so the final pointer permutation does not change aggregate reference
ownership.

## Fallback

Timsort remains the correctness and compatibility fallback. A conservative
heuristic may choose Timsort unnecessarily, but it must never change the
result.
