# Use cases and adoption

BielSort has a deliberately narrow promise: make some large `list[int]` and,
in the unreleased 0.2 candidate, new-list signed-int64 `key=` workloads faster
without requiring callers to migrate their data to a different container. The
only reliable way to decide whether it helps is to measure the complete
operation in the application that owns the data.

!!! success "A promising fit"

    Your data already exists as a large Python list, contains exact integers in
    the signed 64-bit range, needs natural ascending order, and is sufficiently
    unsorted. In the candidate API, records with an exact signed-int64 key are
    also eligible for new-list sorting. Sorting must account for a meaningful
    share of the pipeline runtime.

!!! warning "Usually not a fit"

    Prefer Python's built-in sort for small, nearly ordered, mixed-object,
    generic-key, in-place-key, or keyless-reverse workloads. If the pipeline
    already uses NumPy, Polars, Pandas, or a database, keeping the data in that
    system is normally more valuable than converting it only for BielSort.

## Start with a decision checklist

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### Exact `list[int]`?
Native paths require exact Python integers; conversions change the comparison.
</div>

<div class="biel-card" markdown>
### Signed 64-bit range?
Larger integers deliberately fall back to Timsort.
</div>

<div class="biel-card" markdown>
### Large enough?
Native buffers are most relevant for tens or hundreds of thousands of values.
</div>

<div class="biel-card" markdown>
### Natural ascending order?
Natural integers are the original target. The candidate also supports an
explicit new-list key returning exact signed-int64 integers.
</div>

<div class="biel-card" markdown>
### Measured bottleneck?
Accelerating a small fraction of total runtime has little application impact.
</div>

<div class="biel-card" markdown>
### Memory headroom?
BielSort trades additional memory for its integer fast paths.
</div>

</div>

## Transparent workload proxies

The repository includes three deterministic, synthetic proxies. They are not
presented as production data; each isolates a plausible shape that a user can
replace with an anonymized generator matching the real workload.

<div class="biel-grid" markdown>

<div class="biel-card" markdown>
### Event timestamps
Unordered second-resolution timestamps from one day, with duplicates. This is
a dense range that may favor Counting Sort at scale.
</div>

<div class="biel-card" markdown>
### Signed record IDs
Unordered signed 64-bit identifiers across a wide range exercise Radix Sort.
</div>

<div class="biel-card" markdown>
### Mostly ordered offsets
Append-like offsets with a few displaced values should trigger Timsort and
demonstrate compatibility rather than a native speedup.
</div>

</div>

Install the project with the optional benchmark dependency and run:

```bash
python -m pip install -e ".[benchmark]"
python benchmarks/workload_validation.py \
  -n 10000 100000 1000000 \
  -r 7 \
  --json bielsort-workload-report.json
```

The comparison includes equivalent new-list operations:

- `sorted(values)`;
- `bielsort.sort(values)`;
- NumPy end to end: `list[int]` to `ndarray`, stable sort, then back to
  `list[int]`.

Input generation and the expected result are outside the timed region. The
algorithm order is interleaved deterministically, and the report records
medians, environment metadata, strategies, whether a native fast path ran,
winners, and speedups. If NumPy is not needed, pass `--without-numpy`.

## Measure application impact, not only sorting

A large sorting speedup can still have little user-visible impact. If sorting
is 10% of a pipeline and becomes four times faster, the complete pipeline is
only about 1.08 times faster:

```text
overall speedup = 1 / (0.90 + 0.10 / 4) = 1.08x
```

Record at least:

1. total pipeline time before and after;
2. isolated sort time using equivalent input and output types;
3. peak memory and process memory limits;
4. input length, value range, duplicate rate, and existing order;
5. CPU, operating system, Python version, and repetition count.

## Share a real result

Use the [BielSort Workload Evaluator](evaluator.md) to compare APIs while the
list remains on your machine. It writes JSON and Markdown without raw values or
automatic uploads; review both before sharing.

Use the
[real-world use case form](https://github.com/bielelias/bielsort/issues/new?template=use_case.yml)
to report a win, a loss, or an incompatibility. Negative results are useful:
they improve the selector, documentation, and understanding of the library's
actual niche.

Do not upload proprietary datasets or confidential identifiers. Prefer a
small anonymized generator that reproduces the input distribution.

## Production adoption gate

Consider adoption only after all of these are true:

- correctness matches the current implementation on representative inputs;
- the end-to-end pipeline improvement is material to the application;
- peak memory remains within a safe operating margin;
- a compatible wheel exists for every deployment target;
- Timsort fallback behavior is acceptable for unsupported inputs;
- the application pins a tested BielSort version and has a rollback path.

This process may conclude that `sorted()`, NumPy, or a database remains the
better choice. That is a successful validation result, not a failed benchmark.

For package and cross-platform evidence, continue with the
[hosted runner validation](external-validation.md). It tests the published
wheel independently but does not replace an application workload.
