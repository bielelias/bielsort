# Invalid reorder-plan canonical attempt — 2026-08-06

## Decision

**This attempt is invalid and cannot pass or fail the frozen protocol.** The
timing matrix completed, but every memory worker reported zero incremental
peak RSS. The generated JSON is retained rather than overwritten:
[`2026-08-06-reorder-plan-canonical-invalid-ru-maxrss.json`](2026-08-06-reorder-plan-canonical-invalid-ru-maxrss.json).

The report generator then raised `TypeError` while formatting an undefined
memory ratio. No canonical Markdown result was created, and no threshold,
workload, algorithm, or timing result is changed by this diagnosis.

## Cause

The worker captured `resource.getrusage(...).ru_maxrss` after constructing its
large Python input and subtracted that process high-water mark after the
operation. Input construction had already established a peak that none of the
measured operations exceeded, so every subtraction yielded zero. A ratio such
as `0 / 0` is undefined and cannot be treated as evidence of equal memory use.

This is an instrumentation defect, not a BielSort memory result. The same
high-water issue had already required a ready-checkpoint correction in the
streaming benchmark, but the new harness incorrectly reused the older method.

## Completed timing evidence

The timing portion is preserved as diagnostic evidence only. Its unchanged
gate calculation passed all three sections:

- six of six disordered large cases reached `1.50x` over direct Python;
- six of six reached `1.25x` over `sort_together()`;
- six of six reached parity with end-to-end NumPy conversion;
- the small and nearly ordered regression floors passed.

These observations do not satisfy the complete protocol because the required
memory evidence is invalid.

## Frozen correction before another decision run

Only memory instrumentation may change:

1. A worker constructs its input, releases temporary garbage, prints a
   flushed `ready` checkpoint, and waits.
2. The parent samples the worker's current Linux RSS from `/proc/<pid>/statm`.
3. The parent starts the operation and samples current RSS every 0.5 ms until
   the worker exits.
4. Incremental peak RSS is the sampled peak minus the ready-checkpoint RSS.
5. A zero denominator is rendered as `n/a` rather than raising an exception.

The four workloads, five algorithms, sizes, seeds, seven timing repetitions,
three memory repetitions, identity checks, and every numerical gate remain
unchanged. The corrected code and this invalid record must be committed before
one corrected canonical decision run.

## Attempt metadata

- Commit: `b545851c65b1bfbe8585f87eb7a2c0cc3a4e7633`
- Started from a clean worktree: yes
- JSON marked canonical: yes
- Result: invalid instrumentation; no promotion decision

```bash
python benchmarks/reorder_plan_candidate.py --canonical \
  --json-output benchmarks/results/2026-08-06-reorder-plan-canonical.json \
  --markdown-output benchmarks/results/2026-08-06-reorder-plan-canonical.md
```
