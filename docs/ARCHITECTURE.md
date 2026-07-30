# Architecture

## Public layer

`bielsort_native.bielsort` exposes four primary functions:

- `biel_sort`: returns a new sorted list;
- `biel_sort_in_place`: mutates an exact list and returns `None`;
- two diagnostic variants that also report the selected strategy.

`key=` and `reverse=` deliberately delegate to Python's built-in sorting to
preserve its semantics.

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
