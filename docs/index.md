---
hide:
  - toc
---

<div class="biel-hero" markdown>

<span class="biel-kicker">Stable release · 0.1.0</span>

# Sorting that adapts to your data

BielSort is a stable sorting library for CPython. It accelerates favorable
large integer lists with native Counting Sort or Radix Sort, then falls back to
Python's Timsort whenever that is the safer or more compatible choice.

<div class="biel-actions" markdown>
[Install and start](getting-started.md){ .md-button .md-button--primary }
[Explore the API](api.md){ .md-button }
[View on PyPI](https://pypi.org/project/bielsort/){ .md-button }
</div>

</div>

<div class="biel-stats" markdown>
<div class="biel-stat"><strong>3.9–3.14</strong><span>CPython versions</span></div>
<div class="biel-stat"><strong>4</strong><span>canonical functions</span></div>
<div class="biel-stat"><strong>36</strong><span>prebuilt wheels</span></div>
<div class="biel-stat"><strong>MIT</strong><span>open source license</span></div>
</div>

## Why BielSort?

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### Adaptive by design

The library inspects the workload and selects Counting Sort, Radix Sort, or
Timsort instead of forcing one algorithm onto every input.
</div>

<div class="biel-card" markdown>
### Python-compatible

Sorting remains stable. `key=`, `reverse=`, non-integers, huge integers, and
small or nearly ordered inputs deliberately use Python's mature Timsort.
</div>

<div class="biel-card" markdown>
### Native fast paths

The C extension targets exact Python integers in the signed 64-bit range and
provides both new-list and in-place operations.
</div>

</div>

## Start in seconds

```bash
python -m pip install bielsort
```

=== "Return a new list"

    ```python
    import bielsort

    numbers = [8, -4, 10, 3, -4]
    ordered = bielsort.sort(numbers)

    print(ordered)  # [-4, -4, 3, 8, 10]
    print(numbers)  # unchanged
    ```

=== "Sort in place"

    ```python
    import bielsort

    numbers = [8, -4, 10, 3, -4]
    bielsort.sort_in_place(numbers)

    print(numbers)  # [-4, -4, 3, 8, 10]
    ```

## Pick the operation that matches your code

| Need | Python | BielSort |
|---|---|---|
| Create a new sorted list | `sorted(values)` | `bielsort.sort(values)` |
| Mutate an existing list | `values.sort()` | `bielsort.sort_in_place(values)` |
| See the selected strategy | — | `bielsort.sort_with_strategy(values)` |
| Mutate and see the strategy | — | `bielsort.sort_in_place_with_strategy(values)` |

!!! note "A specialized tool, not a universal replacement"

    BielSort is most interesting for large `list[int]` workloads. Python's
    built-in sorting remains an excellent default for general objects, small
    inputs, nearly ordered data, `key=`, and `reverse=`. See
    [limits and compatibility](limitations.md) before choosing it for a
    production workload.

## Continue learning

- [Install BielSort and run the first checks](getting-started.md)
- [Read the complete API reference](api.md)
- [Understand how the strategy is selected](strategies.md)
- [Review performance results and methodology](performance.md)
- [Leia o guia em português](pt-br.md)
