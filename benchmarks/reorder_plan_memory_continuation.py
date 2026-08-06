"""Evaluate the pre-registered reorder-plan memory continuation.

This keeps the original complete-flow protocol and adds focused nearly
ordered memory and timing gates from
``docs/reorder-plan-memory-continuation.md``.
"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks import reorder_plan_candidate as base


FOCUSED_MEDIAN_MEMORY_MAXIMUM = 1.05
FOCUSED_PAIRED_MEMORY_MAXIMUM = 1.10
FOCUSED_PAIRED_MEMORY_REQUIRED = 2
FOCUSED_TIME_MINIMUM = 0.90


def paired_memory_ratios(row):
    python_samples = row["raw"][base.PYTHON]
    candidate_samples = row["raw"][base.CANDIDATE]
    python_by_seed = {sample["seed"]: sample for sample in python_samples}
    candidate_by_seed = {
        sample["seed"]: sample for sample in candidate_samples
    }
    if python_by_seed.keys() != candidate_by_seed.keys():
        raise ValueError("candidate and Python memory seeds do not match")
    ratios = []
    for seed in sorted(python_by_seed):
        denominator = python_by_seed[seed]["incremental_peak_bytes"]
        numerator = candidate_by_seed[seed]["incremental_peak_bytes"]
        ratios.append(None if denominator == 0 else numerator / denominator)
    return ratios


def evaluate_focused_gates(time_rows, memory_rows):
    time_by_case = {
        (row["workload"], row["size"]): row
        for row in time_rows
    }
    nearly_time_ratios = {
        str(size): time_by_case[(base.EVENT_NEARLY, size)][
            "candidate_speedup_over"
        ][base.PYTHON]
        for size in (100_000, 1_000_000)
    }
    time_passed = all(
        ratio >= FOCUSED_TIME_MINIMUM
        for ratio in nearly_time_ratios.values()
    )

    memory_row = next(
        row
        for row in memory_rows
        if row["workload"] == base.EVENT_NEARLY
        and row["size"] == 1_000_000
    )
    median_ratio = memory_row["candidate_memory_ratio_to"][base.PYTHON]
    paired_ratios = paired_memory_ratios(memory_row)
    paired_pass_count = sum(
        ratio is not None and ratio <= FOCUSED_PAIRED_MEMORY_MAXIMUM
        for ratio in paired_ratios
    )
    candidate_samples = memory_row["raw"][base.CANDIDATE]
    compact_payload_passed = all(
        sample["permutation"]["readonly"]
        and sample["permutation"]["itemsize"] == 4
        and sample["permutation"]["payload_bytes"] == 4_000_000
        for sample in candidate_samples
    )
    median_memory_passed = (
        median_ratio is not None
        and median_ratio <= FOCUSED_MEDIAN_MEMORY_MAXIMUM
    )
    paired_memory_passed = (
        paired_pass_count >= FOCUSED_PAIRED_MEMORY_REQUIRED
    )
    return {
        "passed": (
            time_passed
            and median_memory_passed
            and paired_memory_passed
            and compact_payload_passed
        ),
        "nearly_ordered_time": {
            "passed": time_passed,
            "minimum_speedup": FOCUSED_TIME_MINIMUM,
            "candidate_speedup_over_python": nearly_time_ratios,
        },
        "nearly_ordered_memory": {
            "passed": median_memory_passed and paired_memory_passed,
            "median_ratio": median_ratio,
            "median_maximum": FOCUSED_MEDIAN_MEMORY_MAXIMUM,
            "paired_ratios": paired_ratios,
            "paired_maximum": FOCUSED_PAIRED_MEMORY_MAXIMUM,
            "paired_pass_count": paired_pass_count,
            "paired_required": FOCUSED_PAIRED_MEMORY_REQUIRED,
        },
        "compact_payload_passed": compact_payload_passed,
    }


def render_markdown(payload, json_name, markdown_name):
    report = base.render_markdown(payload, json_name)
    report = report.replace(
        "# Reusable reorder-plan canonical result — 2026-08-06",
        "# Reorder-plan memory continuation — 2026-08-06",
        1,
    )
    report = report.replace(
        "python benchmarks/reorder_plan_candidate.py --canonical",
        "python benchmarks/reorder_plan_memory_continuation.py --canonical",
        1,
    )
    report = report.replace(
        "benchmarks/results/2026-08-06-reorder-plan-canonical.md",
        f"benchmarks/results/{markdown_name}",
        1,
    )
    focused = payload["decision"]["focused"]
    memory = focused["nearly_ordered_memory"]
    time_gate = focused["nearly_ordered_time"]
    ratios = ", ".join(
        "n/a" if ratio is None else f"{ratio:.4f}x"
        for ratio in memory["paired_ratios"]
    )
    section = "\n".join(
        [
            "## Focused continuation gates",
            "",
            "The valid earlier failed result remains preserved and is not",
            "replaced by this continuation.",
            "",
            "- Focused continuation: "
            f"**{'pass' if focused['passed'] else 'fail'}**.",
            "- Nearly ordered median RSS ratio: "
            f"`{memory['median_ratio']:.4f}x` "
            f"(maximum `{memory['median_maximum']:.2f}x`).",
            f"- Same-seed RSS ratios: `{ratios}`; "
            f"{memory['paired_pass_count']} of "
            f"{len(memory['paired_ratios'])} pairs passed; at least "
            f"{memory['paired_required']} were required.",
            "- Nearly ordered time ratios at 100,000 and 1,000,000: "
            + ", ".join(
                f"`{size}: {ratio:.2f}x`"
                for size, ratio in time_gate[
                    "candidate_speedup_over_python"
                ].items()
            )
            + f" (minimum `{time_gate['minimum_speedup']:.2f}x`).",
            "- Compact four-byte payload: "
            f"**{'pass' if focused['compact_payload_passed'] else 'fail'}**.",
            "",
        ]
    )
    return report.replace("## Reproduction", section + "\n## Reproduction", 1)


def validate_canonical(arguments):
    if tuple(arguments.sizes) != base.CANONICAL_SIZES:
        raise SystemExit("canonical sizes do not match the frozen continuation")
    if tuple(arguments.workloads) != base.WORKLOADS:
        raise SystemExit(
            "canonical workloads do not match the frozen continuation"
        )
    if arguments.repetitions != base.CANONICAL_REPETITIONS:
        raise SystemExit(
            "canonical timing repetitions do not match the frozen continuation"
        )
    if arguments.memory_repetitions != base.CANONICAL_MEMORY_REPETITIONS:
        raise SystemExit(
            "canonical memory repetitions do not match the frozen continuation"
        )
    if arguments.skip_memory or arguments.without_optional:
        raise SystemExit("canonical continuation requires every baseline")
    if arguments.json_output is None or arguments.markdown_output is None:
        raise SystemExit("canonical continuation requires JSON and Markdown")
    for output in (arguments.json_output, arguments.markdown_output):
        if output.exists():
            raise SystemExit(f"canonical output already exists: {output}")
    state = base.git_state()
    if state["dirty"]:
        raise SystemExit(
            "canonical continuation requires a clean committed worktree"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--sizes",
        nargs="+",
        type=int,
        default=list(base.CANONICAL_SIZES),
    )
    parser.add_argument(
        "-r",
        "--repetitions",
        type=int,
        default=base.CANONICAL_REPETITIONS,
    )
    parser.add_argument(
        "--memory-repetitions",
        type=int,
        default=base.CANONICAL_MEMORY_REPETITIONS,
    )
    parser.add_argument(
        "--workloads",
        nargs="+",
        choices=base.WORKLOADS,
        default=list(base.WORKLOADS),
    )
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--without-optional", action="store_true")
    parser.add_argument("--canonical", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    arguments = parser.parse_args()

    if arguments.markdown_output is not None and arguments.json_output is None:
        raise SystemExit("Markdown output requires JSON output")
    if arguments.canonical:
        validate_canonical(arguments)
    algorithms = base.selected_algorithms(not arguments.without_optional)
    git = base.git_state()
    time_rows = base.run_time_matrix(
        arguments.sizes,
        arguments.repetitions,
        arguments.workloads,
        algorithms,
    )
    memory_rows = []
    if not arguments.skip_memory:
        memory_rows = base.run_memory_matrix(
            max(arguments.sizes),
            arguments.memory_repetitions,
            arguments.workloads,
            algorithms,
        )

    decision = None
    complete_shape = (
        not arguments.without_optional
        and tuple(arguments.sizes) == base.CANONICAL_SIZES
        and tuple(arguments.workloads) == base.WORKLOADS
        and arguments.repetitions == base.CANONICAL_REPETITIONS
        and arguments.memory_repetitions == base.CANONICAL_MEMORY_REPETITIONS
        and not arguments.skip_memory
    )
    if complete_shape:
        time_gate = base.evaluate_time_gates(time_rows)
        memory_gate = base.evaluate_memory_gates(memory_rows)
        focused_gate = evaluate_focused_gates(time_rows, memory_rows)
        passed = (
            time_gate["passed"]
            and memory_gate["passed"]
            and focused_gate["passed"]
        )
        decision = {
            "time": time_gate,
            "memory": memory_gate,
            "focused": focused_gate,
            "local_performance_passed": passed,
            "note": (
                "A pass preserves the earlier failed result and authorizes "
                "only local reconsideration and later portability/API review."
            ),
        }
        print(
            "\nFROZEN MEMORY CONTINUATION GATE: "
            + ("PASS" if passed else "FAIL")
        )

    payload = {
        "schema_version": 1,
        "protocol": "reorder-plan-nearly-ordered-memory-continuation",
        "git": git,
        "environment": base.environment_metadata(),
        "configuration": {
            "sizes": arguments.sizes,
            "workloads": arguments.workloads,
            "timing_repetitions": arguments.repetitions,
            "memory_repetitions": arguments.memory_repetitions,
            "algorithms": algorithms,
            "base_seed": base.BASE_SEED,
        },
        "time_rows": time_rows,
        "memory_rows": memory_rows,
        "decision": decision,
    }
    if arguments.json_output is not None:
        arguments.json_output.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    if arguments.markdown_output is not None:
        if decision is None:
            raise SystemExit(
                "Markdown output requires the complete continuation shape"
            )
        arguments.markdown_output.write_text(
            render_markdown(
                payload,
                arguments.json_output.name,
                arguments.markdown_output.name,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
