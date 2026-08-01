# Evaluate a private workload

The BielSort Workload Evaluator compares the public wheel with `sorted()` and
`list.sort()` while keeping the input list on the user's machine. It writes
reviewable JSON and Markdown without raw values, provider paths, or automatic
uploads.

!!! warning "Run only your own provider"

    A provider is Python code executed locally. Never run an untrusted provider
    file. Review reports before sharing them: they include environment, size,
    timings, and sampled aggregate statistics by default.

## 1. Prepare an environment

The evaluator lives in the repository and exercises the stable PyPI wheel:

```bash
git clone https://github.com/bielelias/bielsort.git
cd bielsort
python3 -m venv .venv
source .venv/bin/activate
python -m pip install bielsort==0.1.0
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Create a provider

Copy the example to a local Git-ignored file:

```bash
cp benchmarks/workload_provider_example.py my_workload.py
```

Change only `load_values()` so it returns the exact `list` your application
already needs to sort:

```python
def load_values():
    values = load_ids_or_timestamps()
    return values
```

Do not print the elements or convert another container only to manufacture a
favorable comparison.

## 3. Run the evaluator

```bash
python benchmarks/workload_evaluator.py \
  my_workload.py:load_values \
  --label "anonymous-description" \
  --json bielsort-workload-report.json \
  --markdown bielsort-workload-report.md
```

After one warmup, the tool performs seven interleaved measurements of:

- `sorted(values)` and `bielsort.sort(values)` for new-list APIs;
- `list.sort()` and `bielsort.sort_in_place()` for in-place APIs.

In-place input copies, correctness validation, and result destruction remain
outside timed intervals. The original list is not modified.

!!! warning "Keep memory headroom"

    During evaluation, the tool retains the original list and a sorted
    reference while creating one candidate result at a time. Start with a
    smaller sample if the application is near its memory limit. The evaluator
    does not yet measure peak memory or the complete pipeline.

## 4. Review privacy

A normal report contains:

- container type and size;
- Python, BielSort, platform, and architecture;
- selected strategy;
- raw timing samples, medians, and ratios;
- aggregate statistics from at most 2,048 positions, including estimated
  duplicates, monotonicity, signs, and bit lengths.

It does not contain the original values or provider path. To omit sampled
distribution statistics too, run:

```bash
python benchmarks/workload_evaluator.py \
  my_workload.py:load_values \
  --minimal-metadata
```

Default `bielsort-workload-report*.json` and `.md` names are ignored by Git to
reduce accidental commits. Always open both files and perform your own review
before sharing them.

## 5. Share wins and losses

Paste the reviewed Markdown into the
[real-world use-case form](https://github.com/bielelias/bielsort/issues/new?template=use_case.yml)
and explain anonymously what produces the list and why it is sorted. A result
where `sorted()` wins is as useful as a speedup.

The evaluator measures isolated sorting. Measure full pipeline time and peak
memory before production adoption.
