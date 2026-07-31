"""Consolidate BielSort workload-validation JSON files into Markdown."""

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _require(mapping, key, source):
    if key not in mapping:
        raise ValueError(f"{source}: missing {key!r}")
    return mapping[key]


def load_report(path):
    """Load and minimally validate one workload report."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: invalid JSON: {error}") from error

    if not isinstance(report, dict):
        raise ValueError(f"{path}: report root must be an object")
    if report.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema version")

    environment = _require(report, "environment", path)
    configuration = _require(report, "configuration", path)
    results = _require(report, "results", path)
    if not isinstance(environment, dict) or not isinstance(configuration, dict):
        raise ValueError(f"{path}: invalid environment or configuration")
    if not isinstance(results, list) or not results:
        raise ValueError(f"{path}: results must be a non-empty list")

    for result in results:
        if not isinstance(result, dict):
            raise ValueError(f"{path}: each result must be an object")
        for key in (
            "case",
            "size",
            "strategy",
            "native_fast_path",
            "median_seconds",
            "bielsort_speedup_vs_sorted",
            "winner",
        ):
            _require(result, key, path)
        timings = result["median_seconds"]
        if not isinstance(timings, dict):
            raise ValueError(f"{path}: median_seconds must be an object")
        _require(timings, "sorted", path)
        _require(timings, "bielsort", path)

    return report


def discover_reports(root):
    """Return validated `(context, path, report)` tuples."""
    paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
    if not paths:
        raise ValueError(f"{root}: no JSON reports found")

    loaded = []
    contexts = set()
    for path in paths:
        report = load_report(path)
        context = report["configuration"].get("context") or path.stem
        if context in contexts:
            raise ValueError(f"duplicate report context: {context}")
        contexts.add(context)
        loaded.append((context, path, report))
    return sorted(loaded, key=lambda item: item[0].casefold())


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def _seconds(value):
    return f"{value:.6f}"


def _ratio(value):
    return "—" if value is None else f"{value:.2f}×"


def build_markdown(loaded):
    """Build a human-readable cross-environment report."""
    lines = [
        "# GitHub-hosted workload validation",
        "",
        (
            "This report consolidates deterministic synthetic workloads run "
            "against a BielSort wheel installed from PyPI."
        ),
        "",
        "> [!IMPORTANT]",
        (
            "> GitHub-hosted runners are shared, ephemeral machines. These "
            "results validate installation, correctness, strategy consistency, "
            "and broad performance behavior; they are not stable hardware "
            "benchmarks or evidence of user demand."
        ),
        "",
        f"Reports: **{len(loaded)}**  ",
        f"Consolidated: **{datetime.now(timezone.utc).isoformat()}**",
        "",
        "## Environments",
        "",
        "| Context | Platform | Machine | Python | BielSort | NumPy |",
        "|---|---|---|---:|---:|---:|",
    ]

    for context, _, report in loaded:
        environment = report["environment"]
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    context,
                    environment.get("platform", "unknown"),
                    environment.get("machine", "unknown"),
                    environment.get("python", "unknown"),
                    environment.get("bielsort", "unknown"),
                    environment.get("numpy") or "not installed",
                )
            )
            + " |"
        )

    grouped = defaultdict(list)
    for context, _, report in loaded:
        for result in report["results"]:
            grouped[(result["size"], result["case"])].append(
                (context, result)
            )

    lines.extend(
        [
            "",
            "## Consistency summary",
            "",
            (
                "Median speedups combine dimensionless ratios, not absolute "
                "times from different machines."
            ),
            "",
            (
                "| n | Workload | Reports | Native path | BielSort fastest | "
                "Median vs `sorted()` | Median vs NumPy E2E |"
            ),
            "|---:|---|---:|---:|---:|---:|---:|",
        ]
    )

    for (size, case), entries in sorted(grouped.items()):
        sorted_ratios = [
            result["bielsort_speedup_vs_sorted"]
            for _, result in entries
        ]
        numpy_ratios = [
            result.get("bielsort_speedup_vs_numpy_e2e")
            for _, result in entries
            if result.get("bielsort_speedup_vs_numpy_e2e") is not None
        ]
        native_count = sum(
            bool(result["native_fast_path"])
            for _, result in entries
        )
        fastest_count = sum(
            result["winner"] == "bielsort"
            for _, result in entries
        )
        lines.append(
            f"| {size:,} | {_cell(case)} | {len(entries)} | "
            f"{native_count}/{len(entries)} | "
            f"{fastest_count}/{len(entries)} | "
            f"{_ratio(statistics.median(sorted_ratios))} | "
            f"{_ratio(statistics.median(numpy_ratios) if numpy_ratios else None)} |"
        )

    lines.extend(
        [
            "",
            "## Complete results",
            "",
            (
                "| Context | n | Workload | Strategy | Native | `sorted()` "
                "(s) | BielSort (s) | NumPy E2E (s) | vs `sorted()` | "
                "vs NumPy | Winner |"
            ),
            "|---|---:|---|---|:---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for context, _, report in loaded:
        for result in sorted(
            report["results"],
            key=lambda item: (item["size"], item["case"]),
        ):
            timings = result["median_seconds"]
            numpy_time = timings.get("numpy-e2e")
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(context),
                        f"{result['size']:,}",
                        _cell(result["case"]),
                        _cell(result["strategy"]),
                        "yes" if result["native_fast_path"] else "no",
                        _seconds(timings["sorted"]),
                        _seconds(timings["bielsort"]),
                        _seconds(numpy_time) if numpy_time is not None else "—",
                        _ratio(result["bielsort_speedup_vs_sorted"]),
                        _ratio(result.get("bielsort_speedup_vs_numpy_e2e")),
                        _cell(result["winner"]),
                    )
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Interpretation rules",
            "",
            "- Compare ratios within each runner, never absolute times across runners.",
            "- Treat the mostly ordered proxy as a Timsort compatibility control.",
            "- Re-run noisy or contradictory results before changing heuristics.",
            "- Require application-level and memory measurements before adoption.",
            "- Do not describe synthetic runner results as real user workloads.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    loaded = discover_reports(arguments.reports)
    markdown = build_markdown(loaded)
    arguments.output.write_text(markdown, encoding="utf-8")
    print(f"Wrote {arguments.output} from {len(loaded)} reports")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from error
