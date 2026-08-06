"""Run the pre-registered bounded-memory streaming top-k protocol.

The protocol was frozen in commit 91e851f before this harness and before the
private streaming implementation. Canonical results require unchanged default
configuration and a separately recorded implementation commit.
"""

import argparse
import gc
import heapq
import json
import operator
import os
import platform
import statistics
import subprocess
import sys
import time
import weakref
from dataclasses import FrozenInstanceError
from pathlib import Path

import bielsort
import bielsort_native


PROTOCOL_COMMIT = "91e851f"
CANDIDATE = "candidate"
HEAPQ = "heapq"
MATERIALIZING_FACADE = "materializing-facade"
DOMAINS = (
    "natural-int64",
    "keyed-int64",
    "keyed-huge-int",
    "keyed-string",
)
MEMORY_DOMAINS = ("keyed-int64", "keyed-string")
DIRECTIONS = ("smallest", "largest")
K_VALUES = (100, 10_000, 100_000)
REGRESSION_FLOOR = 0.85
EXACT_TARGET = 1.10
MINIMUM_EXACT_TARGET_CASES = 8
GENERIC_TARGET = 0.95
MINIMUM_GENERIC_TARGET_CASES = 9
HEAPQ_MEMORY_RATIO_LIMIT = 0.70
FACADE_MEMORY_RATIO_LIMIT = 0.35


def _candidate_function():
    from bielsort_native._streaming_topk import stream_top_k

    return stream_top_k


def _facade_function():
    from bielsort_native._topk_facade import top_k_adaptive

    return top_k_adaptive


def median_absolute_deviation(values):
    center = statistics.median(values)
    return statistics.median([abs(value - center) for value in values])


def rotate(values, offset):
    offset %= len(values)
    return values[offset:] + values[:offset]


def dense_value(index, size, salt):
    span = max(257, size // 8)
    return ((index * 1_000_003 + salt * 97_409) % span) - span // 2


def stream_values(size, domain, salt=1):
    """Return a fresh one-shot generator without an O(n) backing container."""
    if domain == "natural-int64":
        return (
            dense_value(index, size, salt)
            for index in range(size)
        )
    if domain == "keyed-int64":
        return (
            (dense_value(index, size, salt), index)
            for index in range(size)
        )
    if domain == "keyed-huge-int":
        return (
            (
                (dense_value(index, size, salt) << 96)
                + ((index * 65_537) & ((1 << 48) - 1)),
                index,
            )
            for index in range(size)
        )
    if domain == "keyed-string":
        return (
            (
                "group-{0:05d}".format(
                    (dense_value(index, size, salt) + size) % 4_096
                ),
                index,
            )
            for index in range(size)
        )
    raise ValueError(f"unknown domain: {domain}")


def key_for_domain(domain):
    return None if domain == "natural-int64" else operator.itemgetter(0)


def run_algorithm(algorithm, size, domain, k, largest, return_info=False):
    values = stream_values(size, domain)
    key = key_for_domain(domain)
    if algorithm == CANDIDATE:
        return _candidate_function()(
            values,
            k,
            key=key,
            largest=largest,
            return_info=return_info,
        )
    if return_info:
        raise ValueError("only the candidate provides diagnostics")
    if algorithm == HEAPQ:
        selection = heapq.nlargest if largest else heapq.nsmallest
        return selection(k, values, key=key)
    if algorithm == MATERIALIZING_FACADE:
        return _facade_function()(values, k, key=key, largest=largest)
    raise ValueError(f"unknown algorithm: {algorithm}")


def ensure_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label} differs from the stable reference")


def measure_case(size, domain, k, largest, blocks):
    key = key_for_domain(domain)
    expected = sorted(
        stream_values(size, domain),
        key=key,
        reverse=largest,
    )[:k]
    for algorithm in (HEAPQ, CANDIDATE):
        result = run_algorithm(algorithm, size, domain, k, largest)
        ensure_equal(result, expected, algorithm)
        del result

    samples = {HEAPQ: [], CANDIDATE: []}
    algorithms = [HEAPQ, CANDIDATE]
    for block in range(blocks):
        for algorithm in rotate(algorithms, block):
            gc.collect()
            gc.disable()
            try:
                started = time.perf_counter()
                result = run_algorithm(
                    algorithm,
                    size,
                    domain,
                    k,
                    largest,
                )
                elapsed = time.perf_counter() - started
            finally:
                gc.enable()
            ensure_equal(result, expected, algorithm)
            samples[algorithm].append(elapsed)
            del result

    diagnostic_result, info = run_algorithm(
        CANDIDATE,
        size,
        domain,
        k,
        largest,
        return_info=True,
    )
    ensure_equal(diagnostic_result, expected, "diagnostic candidate")
    if info.processed != size or info.selected != min(k, size):
        raise AssertionError("stream diagnostics report incorrect counts")
    medians = {
        algorithm: statistics.median(durations)
        for algorithm, durations in samples.items()
    }
    paired_speedups = [
        baseline / candidate
        for baseline, candidate in zip(samples[HEAPQ], samples[CANDIDATE])
    ]
    return {
        "samples_s": samples,
        "medians_s": medians,
        "median_absolute_deviations_s": {
            algorithm: median_absolute_deviation(durations)
            for algorithm, durations in samples.items()
        },
        "paired_speedups": paired_speedups,
        "median_paired_speedup": statistics.median(paired_speedups),
        "ratio_of_medians": medians[HEAPQ] / medians[CANDIDATE],
        "diagnostics": info.as_dict(),
    }


def run_timing_matrix(size, blocks, domains, k_values, directions):
    rows = []
    print("STREAMING TOP-K (median paired speedup; higher favors BielSort)")
    print(
        f"{'domain':<18} {'k':>9} {'direction':<8} "
        f"{'heapq':>10} {'candidate':>10} {'speedup':>8} {'route':<24}"
    )
    print("-" * 96)
    for domain in domains:
        for k in k_values:
            if k > size:
                continue
            for direction in directions:
                largest = direction == "largest"
                measurement = measure_case(
                    size,
                    domain,
                    k,
                    largest,
                    blocks,
                )
                row = {
                    "domain": domain,
                    "k": k,
                    "direction": direction,
                    **measurement,
                }
                rows.append(row)
                print(
                    f"{domain:<18} {k:>9} {direction:<8} "
                    f"{measurement['medians_s'][HEAPQ]:>10.5f} "
                    f"{measurement['medians_s'][CANDIDATE]:>10.5f} "
                    f"{measurement['median_paired_speedup']:>7.2f}x "
                    f"{measurement['diagnostics']['algorithm']:<24}"
                )
    return rows


class OneShot:
    def __init__(self, values):
        self.values = values
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations != 1:
            raise AssertionError("input was iterated more than once")
        return iter(self.values)


class TrackedRecord:
    def __init__(self, value, position):
        self.value = value
        self.position = position


class LessOnlyKey:
    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        raise AssertionError("equality must not be required")


def run_semantic_probes():
    stream_top_k = _candidate_function()
    records = [TrackedRecord(index % 7, index) for index in range(200)]
    source = OneShot(records)
    calls = []
    result = stream_top_k(
        source,
        80,
        key=lambda record: calls.append(record) or record.value,
    )
    expected = sorted(records, key=lambda record: record.value)[:80]
    if any(left is not right for left, right in zip(result, expected)):
        raise AssertionError("stable identity probe failed")
    if calls != records or source.iterations != 1:
        raise AssertionError("one-call or one-shot probe failed")

    largest = stream_top_k(
        records,
        80,
        key=lambda record: LessOnlyKey(record.value),
        largest=True,
    )
    expected_largest = sorted(
        records,
        key=lambda record: LessOnlyKey(record.value),
        reverse=True,
    )[:80]
    if any(
        left is not right
        for left, right in zip(largest, expected_largest)
    ):
        raise AssertionError("largest less-only stable probe failed")

    untouched = OneShot([1])
    if stream_top_k(untouched, 0, key=object()) != []:
        raise AssertionError("zero-k result is incorrect")
    if untouched.iterations != 0:
        raise AssertionError("zero-k consumed the input")

    rejected_references = []

    def tracked_stream():
        for index in range(2_000):
            record = TrackedRecord(2_000 - index, index)
            if index < 1_000:
                rejected_references.append(weakref.ref(record))
            yield record
            if index == 1_500:
                gc.collect()
                if sum(ref() is not None for ref in rejected_references) > 16:
                    raise AssertionError(
                        "rejected records were retained with the stream"
                    )

    lifetime = stream_top_k(
        tracked_stream(),
        10,
        key=lambda record: record.value,
    )
    if len(lifetime) != 10:
        raise AssertionError("lifetime probe selected the wrong count")

    guarded = OneShot(records)
    try:
        stream_top_k(
            guarded,
            100,
            key=lambda record: record.value,
            max_native_auxiliary_bytes=0,
            on_memory_limit="raise",
        )
    except MemoryError:
        pass
    else:
        raise AssertionError("memory raise probe did not raise")
    if guarded.iterations != 0:
        raise AssertionError("memory guard consumed the stream")

    fallback_source = OneShot(records)
    fallback_result, fallback_info = stream_top_k(
        fallback_source,
        20,
        key=lambda record: record.value,
        max_native_auxiliary_bytes=0,
        on_memory_limit="heapq",
        return_info=True,
    )
    if fallback_info.algorithm != "heapq" or fallback_source.iterations != 1:
        raise AssertionError("memory fallback route probe failed")
    if any(
        left is not right
        for left, right in zip(fallback_result, expected[:20])
    ):
        raise AssertionError("memory fallback result probe failed")

    try:
        fallback_info.algorithm = "changed"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("stream diagnostics are mutable")

    if any(
        hasattr(module, name)
        for module in (bielsort, bielsort_native)
        for name in ("stream_top_k", "StreamTopKInfo", "top_k", "TopKInfo")
    ):
        raise AssertionError("private streaming names leaked publicly")
    return {
        "stable_identity": True,
        "one_key_call_per_record": True,
        "one_shot": True,
        "zero_k_no_consumption": True,
        "less_only_keys": True,
        "early_release": True,
        "preconsumption_memory_guard": True,
        "immutable_diagnostics": True,
        "public_api_unchanged": True,
    }


def current_linux_rss_bytes(process_id):
    """Read current resident memory without an inherited high-water mark."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError("sampled RSS measurement currently requires Linux")
    try:
        statm = Path(f"/proc/{process_id}/statm").read_text(
            encoding="ascii"
        )
    except FileNotFoundError:
        return None
    resident_pages = int(statm.split()[1])
    return resident_pages * os.sysconf("SC_PAGE_SIZE")


def memory_worker(algorithm, size, domain, k):
    gc.collect()
    print(json.dumps({"event": "ready"}), flush=True)
    if not sys.stdin.readline():
        raise RuntimeError("memory controller closed before the start signal")
    result = run_algorithm(algorithm, size, domain, k, False)
    payload = {
        "algorithm": algorithm,
        "size": size,
        "domain": domain,
        "k": k,
        "selected": len(result),
    }
    print(json.dumps(payload, sort_keys=True), flush=True)


def run_memory_child(script, algorithm, size, domain, k):
    if not sys.platform.startswith("linux"):
        raise RuntimeError("sampled RSS measurement currently requires Linux")
    command = [
        sys.executable,
        str(script),
        "--memory-worker",
        algorithm,
        domain,
        str(k),
        "--size",
        str(size),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    ready_line = process.stdout.readline()
    try:
        ready = json.loads(ready_line)
    except json.JSONDecodeError:
        process.terminate()
        stdout, stderr = process.communicate()
        raise RuntimeError(
            "memory worker did not provide its ready signal: "
            f"{ready_line}{stdout}{stderr}"
        )
    if ready != {"event": "ready"}:
        process.terminate()
        process.communicate()
        raise RuntimeError(f"unexpected memory-worker signal: {ready}")

    baseline = current_linux_rss_bytes(process.pid)
    if baseline is None:
        process.terminate()
        process.communicate()
        raise RuntimeError("memory worker exited before sampling began")
    sampled_peak = baseline
    process.stdin.write("start\n")
    process.stdin.flush()
    process.stdin.close()
    process.stdin = None
    while process.poll() is None:
        current = current_linux_rss_bytes(process.pid)
        if current is not None and current > sampled_peak:
            sampled_peak = current
        time.sleep(0.0005)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise subprocess.CalledProcessError(
            process.returncode,
            command,
            output=stdout,
            stderr=stderr,
        )
    payload = json.loads(stdout.strip().splitlines()[-1])
    payload.update(
        {
            "measurement": "parent-sampled-linux-rss",
            "sampling_interval_seconds": 0.0005,
            "baseline_current_rss_bytes": baseline,
            "sampled_peak_rss_bytes": sampled_peak,
            "incremental_peak_rss_bytes": max(0, sampled_peak - baseline),
        }
    )
    return payload


def run_memory_matrix(script, size, samples, domains, k_values):
    rows = []
    print("\nISOLATED INCREMENTAL PEAK RSS")
    print(
        f"{'domain':<14} {'k':>9} {'candidate':>12} "
        f"{'heapq':>12} {'facade':>12} {'cand/heap':>10} {'cand/fac':>10}"
    )
    print("-" * 90)
    for domain in domains:
        for k in k_values:
            if k > size:
                continue
            raw = {
                algorithm: [
                    run_memory_child(script, algorithm, size, domain, k)
                    for _ in range(samples)
                ]
                for algorithm in (
                    CANDIDATE,
                    HEAPQ,
                    MATERIALIZING_FACADE,
                )
            }
            medians = {
                algorithm: statistics.median(
                    sample["incremental_peak_rss_bytes"]
                    for sample in algorithm_samples
                )
                for algorithm, algorithm_samples in raw.items()
            }
            heapq_ratio = (
                medians[CANDIDATE] / medians[HEAPQ]
                if medians[HEAPQ]
                else None
            )
            facade_ratio = (
                medians[CANDIDATE] / medians[MATERIALIZING_FACADE]
                if medians[MATERIALIZING_FACADE]
                else None
            )
            row = {
                "domain": domain,
                "k": k,
                "samples": raw,
                "median_incremental_peak_rss_bytes": medians,
                "candidate_to_heapq_ratio": heapq_ratio,
                "candidate_to_materializing_facade_ratio": facade_ratio,
            }
            rows.append(row)
            print(
                f"{domain:<14} {k:>9} "
                f"{medians[CANDIDATE] / (1024 ** 2):>10.2f} MiB "
                f"{medians[HEAPQ] / (1024 ** 2):>10.2f} MiB "
                f"{medians[MATERIALIZING_FACADE] / (1024 ** 2):>10.2f} MiB "
                f"{heapq_ratio if heapq_ratio is not None else float('nan'):>9.2f}x "
                f"{facade_ratio if facade_ratio is not None else float('nan'):>9.2f}x"
            )
    return rows


def evaluate_gates(timing_rows, memory_rows, semantic_probes, canonical):
    speedups = [row["median_paired_speedup"] for row in timing_rows]
    exact_rows = [
        row
        for row in timing_rows
        if row["domain"] in ("natural-int64", "keyed-int64")
    ]
    generic_rows = [
        row
        for row in timing_rows
        if row["domain"] in ("keyed-huge-int", "keyed-string")
    ]
    exact_target_count = sum(
        row["median_paired_speedup"] >= EXACT_TARGET
        for row in exact_rows
    )
    generic_target_count = sum(
        row["median_paired_speedup"] >= GENERIC_TARGET
        for row in generic_rows
    )
    heapq_memory_checks = [
        row["candidate_to_heapq_ratio"] is not None
        and row["candidate_to_heapq_ratio"] <= HEAPQ_MEMORY_RATIO_LIMIT
        for row in memory_rows
        if row["k"] == 100_000
    ]
    facade_memory_checks = [
        row["candidate_to_materializing_facade_ratio"] is not None
        and row["candidate_to_materializing_facade_ratio"]
        <= FACADE_MEMORY_RATIO_LIMIT
        for row in memory_rows
        if row["k"] in (100, 10_000)
    ]
    checks = {
        "semantic_probes_passed": all(semantic_probes.values()),
        "minimum_speedup_passed": bool(speedups)
        and min(speedups) >= REGRESSION_FLOOR,
        "exact_target_passed": exact_target_count
        >= MINIMUM_EXACT_TARGET_CASES,
        "generic_target_passed": generic_target_count
        >= MINIMUM_GENERIC_TARGET_CASES,
        "heapq_memory_passed": bool(heapq_memory_checks)
        and all(heapq_memory_checks),
        "materializing_facade_memory_passed": bool(facade_memory_checks)
        and all(facade_memory_checks),
    }
    return {
        "canonical_configuration": canonical,
        "checks": checks,
        "passed": canonical and all(checks.values()),
        "minimum_speedup": min(speedups) if speedups else None,
        "exact_target_count": exact_target_count,
        "exact_case_count": len(exact_rows),
        "generic_target_count": generic_target_count,
        "generic_case_count": len(generic_rows),
    }


def environment_metadata():
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "executable": sys.executable,
    }


def render_report(payload):
    decision = payload["decision"]
    lines = [
        "# Bounded-memory streaming top-k result",
        "",
        f"- Protocol commit: `{payload['protocol_commit']}`",
        f"- Implementation commit: `{payload['implementation_commit']}`",
        f"- Canonical configuration: `{decision['canonical_configuration']}`",
        f"- Decision: `{'PASS' if decision['passed'] else 'FAIL'}`",
        "",
        "## Timing",
        "",
        "| Domain | k | Direction | heapq (s) | BielSort (s) | Paired speedup | Route |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for row in payload["timing"]:
        lines.append(
            "| {domain} | {k} | {direction} | {baseline:.6f} | "
            "{candidate:.6f} | {speedup:.2f}x | {route} |".format(
                domain=row["domain"],
                k=row["k"],
                direction=row["direction"],
                baseline=row["medians_s"][HEAPQ],
                candidate=row["medians_s"][CANDIDATE],
                speedup=row["median_paired_speedup"],
                route=row["diagnostics"]["algorithm"],
            )
        )
    lines.extend(
        [
            "",
            "## Isolated incremental peak RSS",
            "",
            "Linux RSS was sampled by the parent process every 0.5 ms after "
            "a worker-ready checkpoint.",
            "",
            "| Domain | k | BielSort | heapq | Materializing façade | BielSort/heapq | BielSort/façade |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["memory"]:
        medians = row["median_incremental_peak_rss_bytes"]
        heapq_ratio = row["candidate_to_heapq_ratio"]
        facade_ratio = row["candidate_to_materializing_facade_ratio"]
        lines.append(
            "| {domain} | {k} | {candidate:.2f} MiB | {heapq:.2f} MiB | "
            "{facade:.2f} MiB | {heapq_ratio} | {facade_ratio} |".format(
                domain=row["domain"],
                k=row["k"],
                candidate=medians[CANDIDATE] / (1024 ** 2),
                heapq=medians[HEAPQ] / (1024 ** 2),
                facade=medians[MATERIALIZING_FACADE] / (1024 ** 2),
                heapq_ratio=(
                    "n/a" if heapq_ratio is None else f"{heapq_ratio:.2f}x"
                ),
                facade_ratio=(
                    "n/a"
                    if facade_ratio is None
                    else f"{facade_ratio:.2f}x"
                ),
            )
        )
    lines.extend(
        [
            "",
            "## Gate summary",
            "",
            f"- Minimum paired speedup: `{decision['minimum_speedup']:.2f}x`",
            "- Signed-int64 target cases: "
            f"`{decision['exact_target_count']}/{decision['exact_case_count']}`",
            "- Generic near-parity cases: "
            f"`{decision['generic_target_count']}/{decision['generic_case_count']}`",
        ]
    )
    for name, passed in decision["checks"].items():
        lines.append(f"- {name}: `{'PASS' if passed else 'FAIL'}`")
    lines.extend(
        [
            "",
            "These measurements are synthetic local evidence, not universal",
            "performance guarantees or evidence of external demand. Passing",
            "does not expose an API or authorize a package publication.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_csv(value, allowed, converter=str):
    selected = tuple(converter(item) for item in value.split(",") if item)
    invalid = [item for item in selected if item not in allowed]
    if invalid:
        raise argparse.ArgumentTypeError(f"unsupported values: {invalid}")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=1_000_000)
    parser.add_argument("--blocks", type=int, default=9)
    parser.add_argument("--memory-samples", type=int, default=5)
    parser.add_argument("--implementation-commit", default="unrecorded")
    parser.add_argument("--domains", default=",".join(DOMAINS))
    parser.add_argument("--k-values", default=",".join(map(str, K_VALUES)))
    parser.add_argument("--directions", default=",".join(DIRECTIONS))
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-report", type=Path)
    parser.add_argument(
        "--memory-worker",
        nargs=3,
        metavar=("ALGORITHM", "DOMAIN", "K"),
    )
    args = parser.parse_args()

    if args.memory_worker:
        algorithm, domain, k_text = args.memory_worker
        memory_worker(algorithm, args.size, domain, int(k_text))
        return
    if args.size <= 0 or args.blocks <= 0 or args.memory_samples <= 0:
        parser.error("size, blocks, and memory-samples must be positive")

    domains = parse_csv(args.domains, DOMAINS)
    k_values = parse_csv(args.k_values, K_VALUES, int)
    directions = parse_csv(args.directions, DIRECTIONS)
    canonical = (
        args.size == 1_000_000
        and args.blocks == 9
        and args.memory_samples == 5
        and domains == DOMAINS
        and k_values == K_VALUES
        and directions == DIRECTIONS
        and not args.skip_memory
    )

    semantic_probes = run_semantic_probes()
    timing = run_timing_matrix(
        args.size,
        args.blocks,
        domains,
        k_values,
        directions,
    )
    memory = []
    if not args.skip_memory:
        memory = run_memory_matrix(
            Path(__file__).resolve(),
            args.size,
            args.memory_samples,
            tuple(domain for domain in domains if domain in MEMORY_DOMAINS),
            k_values,
        )
    decision = evaluate_gates(
        timing,
        memory,
        semantic_probes,
        canonical,
    )
    payload = {
        "schema_version": 1,
        "protocol_commit": PROTOCOL_COMMIT,
        "implementation_commit": args.implementation_commit,
        "configuration": {
            "size": args.size,
            "blocks": args.blocks,
            "memory_samples": args.memory_samples,
            "domains": domains,
            "k_values": k_values,
            "directions": directions,
        },
        "environment": environment_metadata(),
        "semantic_probes": semantic_probes,
        "timing": timing,
        "memory": memory,
        "decision": decision,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    report = render_report(payload)
    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(report, encoding="utf-8")
    print("\n" + report)
    if canonical and not decision["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
