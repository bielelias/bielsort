# Invalid streaming top-k measurement attempt

This artifact preserves the raw JSON emitted by the first attempted canonical
run on 2026-08-06. It is **not** a canonical result and must not be used for a
performance or memory claim.

The timing matrix completed, but the original memory worker subtracted two
`getrusage(RUSAGE_SELF).ru_maxrss` high-water marks. On this Linux process
tree, workers inherited a peak established by the timing parent. All three
algorithms consequently reported zero incremental RSS, the required ratios
were undefined, and report rendering stopped with a `TypeError`.

The harness was corrected without changing the pre-registered matrix, gates,
or thresholds. A worker now waits at a ready checkpoint while its parent
records current Linux RSS and samples that worker every 0.5 ms. The malformed
attempt remains here to make the instrumentation correction auditable.

- Protocol commit: `91e851f`
- Implementation commit: `73d43c2`
- Raw invalid artifact:
  `2026-08-06-streaming-topk-invalid-inherited-rusage.json`
