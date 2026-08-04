# API reference

!!! warning "Unreleased 0.2 candidate"

    The repository's research branch can accelerate eligible signed-int64
    results from `sort(key=...)`. The published 0.1.0 wheel still sends every
    key call to Timsort.

The canonical public package is `bielsort`:

```python
import bielsort
```

The four stable functions mirror the two common Python sorting styles and add
optional diagnostic variants. The research branch also contains the
`sort_with_info()` candidate described below; it is not present in the
published 0.1.0 wheel.

## At a glance

| Function | Changes input? | Return value | Intended comparison |
|---|---:|---|---|
| `sort()` | No | new `list` | `sorted()` |
| `sort_in_place()` | Yes | `None` | `list.sort()` |
| `sort_with_strategy()` | No | `(list, str)` | diagnostics |
| `sort_in_place_with_strategy()` | Yes | `str` | diagnostics |
| `sort_with_info()` | No | `(list, SortInfo)` | keyed diagnostics and memory guard |

All four operations are stable: elements that compare equal retain their
original relative order.

## `sort`

```python
bielsort.sort(iterable, *, key=None, reverse=False)
```

Return a new sorted list and leave the input unchanged.

**Parameters**

- `iterable`: any iterable accepted by the implementation, including lists,
  tuples, and generators;
- `key`: optional one-argument key function;
- `reverse`: sort in descending order when `True`.

**Returns**

A new `list` containing the sorted elements.

```python
import bielsort

source = (5, -2, 8, 5)
result = bielsort.sort(source)

assert result == [-2, 5, 5, 8]
```

When `key` is not `None`, the 0.2 candidate evaluates it exactly once per item
and may select stable native Counting or Radix if every result is an exact
signed-int64 integer. Generic, overflow, small, and unsuitable ordered-run
cases use Timsort replay. `reverse=True` participates in the same adaptive
selection when a key is present; without a key it uses `sorted()`.

## `sort_in_place`

```python
bielsort.sort_in_place(values, *, key=None, reverse=False)
```

Sort a list in place, preserve its identity, and return `None`.

**Parameters**

- `values`: the list to mutate;
- `key`: optional one-argument key function;
- `reverse`: sort in descending order when `True`.

**Returns**

`None`, matching `list.sort()`.

```python
import bielsort

values = [5, -2, 8, 5]
identity = id(values)

result = bielsort.sort_in_place(values)

assert values == [-2, 5, 5, 8]
assert id(values) == identity
assert result is None
```

Passing a non-list value is an error for the in-place API.

Calls using `key=` or `reverse=True` deliberately remain direct
`list.sort()` operations in this candidate. An adaptive in-place experiment
was faster for integer keys but slower for generic keys, so it was not exposed.

## `sort_with_strategy`

```python
bielsort.sort_with_strategy(iterable, *, key=None, reverse=False)
```

Return a tuple containing the new sorted list and a human-readable description
of the selected strategy.

```python
import random
import bielsort

rng = random.Random(42)
values = [rng.randint(-(1 << 31), (1 << 31) - 1) for _ in range(100_000)]

ordered, strategy = bielsort.sort_with_strategy(values)
print(strategy)
```

## `sort_in_place_with_strategy`

```python
bielsort.sort_in_place_with_strategy(
    values,
    *,
    key=None,
    reverse=False,
)
```

Sort a list in place and return the human-readable strategy description.

```python
import bielsort

values = [3, 1, 2] * 10_000
strategy = bielsort.sort_in_place_with_strategy(values)

assert values == sorted(values)
print(strategy)
```

!!! warning "Diagnostic strings are not a control-flow API"

    Strategy descriptions are intended for debugging, benchmarks, and issue
    reports. Their wording may evolve as heuristics improve before 1.0. Do not
    make application correctness depend on an exact diagnostic string.

## `sort_with_info` — unreleased candidate

```python
bielsort.sort_with_info(
    iterable,
    *,
    key,
    reverse=False,
    max_native_auxiliary_bytes=None,
    on_memory_limit="timsort",
)
```

Sort by an explicit key and return an immutable `SortInfo` object. Unlike the
human-readable strategy string, its field names and normalized algorithm names
are designed for programmatic inspection.

```python
import bielsort

records = [
    {"name": "Ana", "score": 30},
    {"name": "Bia", "score": 10},
    {"name": "Caio", "score": 20},
]

ordered, info = bielsort.sort_with_info(
    records,
    key=lambda record: record["score"],
    max_native_auxiliary_bytes=32 * 1024 * 1024,
)

print(info.algorithm)
print(info.reason)
print(info.used_native)
print(info.estimated_native_auxiliary_bytes)
```

`on_memory_limit="timsort"` is the default: when the conservative native
estimate exceeds the limit, BielSort delegates before evaluating `key`.
`on_memory_limit="raise"` raises `MemoryError` at the same pre-key checkpoint.
Providing a limit requires an exact built-in `list` or `tuple`; without a
limit, any iterable accepted by `sort()` remains valid.

The memory values cover BielSort's result-list pointers and variable native
buffers. They are planning estimates, not measurements of total RSS, and
exclude input objects, key-object payloads, allocator overhead, Timsort
allocations, and fixed stack storage. The worst-case native value takes the
maximum of the possible Radix buffers and eligible Counting table.

### `SortInfo` fields

| Field | Meaning |
|---|---|
| `algorithm` | normalized `counting`, `radix`, `timsort`, `already-sorted`, or `trivial` |
| `reason` | human-readable selection explanation; wording may evolve |
| `size` | number of records |
| `reverse` | whether descending stable ordering was requested |
| `key_domain` | `signed-int64` for a committed native path, otherwise `python` |
| `key_min`, `key_max`, `key_span` | observed native-key range when available |
| `radix_passes` | selected Radix pass count, otherwise `None` |
| `used_native` | derived property indicating whether the final path was native |
| `estimated_native_auxiliary_bytes` | selected native variable-memory estimate, when applicable |
| `worst_case_native_auxiliary_bytes` | conservative native planning bound for the input size |
| `max_native_auxiliary_bytes` | requested limit or `None` |
| `native_memory_limit_exceeded` | whether that limit forced Timsort |

Successful keyed operations are always stable and call the explicit key once
per record, so those invariants are documented rather than duplicated as
fields. `SortInfo` is frozen, preventing callers from accidentally changing a
recorded decision.

## `__version__`

```python
import bielsort

print(bielsort.__version__)
```

For package-management code, `importlib.metadata.version("bielsort")` is also
available.

## Compatibility aliases

The original names remain aliases throughout the 0.1 series:

| Compatibility name | Canonical name |
|---|---|
| `biel_sort` | `sort` |
| `biel_sort_in_place` | `sort_in_place` |
| `biel_sort_diagnostico` | `sort_with_strategy` |
| `biel_sort_with_strategy` | `sort_with_strategy` |
| `biel_sort_in_place_diagnostico` | `sort_in_place_with_strategy` |
| `biel_sort_in_place_with_strategy` | `sort_in_place_with_strategy` |

The older `bielsort_native` import path is also retained for compatibility.
New code should use `import bielsort`.

## Behavior summary

- natural ascending exact signed 64-bit integers may use a native fast path;
- eligible exact signed-int64 results from new-list `sort(key=...)` may use a
  native stable path in the unreleased 0.2 candidate;
- generic new-list keys, keyless reverse calls, and in-place key/reverse calls
  use Python's Timsort;
- non-integers, integer subclasses, and arbitrary-size integers use Timsort;
- sorting is stable in every path;
- `sort()` preserves the source iterable;
- `sort_in_place()` preserves list identity and returns `None`.
