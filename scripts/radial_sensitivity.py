#!/usr/bin/env python3
"""Run reproducible radial-distribution sensitivity scenarios for site A.

This is a scenario comparison, not empirical validation. The three slopes are
deliberately illustrative assumptions; none is claimed to describe a real head.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = (-0.5, 0.0, 1.0)
METRICS = (
    "baseline_AR",
    "optimized_AR",
    "baseline_overspray_pct_of_own_water",
    "optimized_overspray_pct_of_own_water",
    "baseline_CU",
    "optimized_CU",
    "baseline_dry_area_pct",
    "optimized_dry_area_pct",
    "AR_metric_improvement_pct",
)


def scenario_name(slope: float) -> str:
    value = f"{slope:g}".replace("-", "m").replace(".", "p")
    return f"slope_{value}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="out/radial-sensitivity")
    args = parser.parse_args()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for slope in SCENARIOS:
        name = scenario_name(slope)
        scenario_dir = outdir / name
        command = [
            sys.executable,
            str(ROOT / "campos_sim.py"),
            "--mode", "movable",
            "--quick",
            "--sites", "A", "B", "C", "D", "E",
            "--radial-slope", str(slope),
            "--outdir", str(scenario_dir),
        ]
        print(f"\n=== Running {name} (radial slope {slope:g}) ===", flush=True)
        completed = subprocess.run(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False,
        )
        (scenario_dir / "console.log").parent.mkdir(parents=True, exist_ok=True)
        (scenario_dir / "console.log").write_text(completed.stdout, encoding="utf-8")
        print(completed.stdout, end="", flush=True)
        if completed.returncode:
            raise SystemExit(
                f"Scenario {name} failed with exit code {completed.returncode}; "
                f"see {scenario_dir / 'console.log'}"
            )

        result_path = scenario_dir / "results_movable.csv"
        with result_path.open(newline="", encoding="utf-8-sig") as fh:
            candidates = list(csv.DictReader(fh))
        if not candidates:
            raise SystemExit(f"No simulation rows found in {result_path}")

        metadata_path = scenario_dir / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        recorded_slope = metadata.get("radial_distribution", {}).get("radial_slope")
        if recorded_slope is None or abs(float(recorded_slope) - slope) > 1e-12:
            raise SystemExit(f"Run metadata does not match requested slope {slope:g}")

        for result in candidates:
            row = {
                "scenario": name,
                "radial_slope": f"{slope:g}",
                "site": result["site"],
                "sprinkler_count": result["sprinkler_count"],
                "status": "completed",
                "interpretation": "illustrative assumption; not calibrated to field data",
            }
            row.update({metric: result.get(metric, "") for metric in METRICS})
            rows.append(row)

    summary_path = outdir / "sensitivity_summary.csv"
    columns = [
        "scenario", "radial_slope", "site", "sprinkler_count", "status",
        *METRICS, "interpretation",
    ]
    with summary_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    report = [
        "# campOS radial-distribution sensitivity run",
        "",
        "All three radial scenarios were run automatically in CI across synthetic sites A–E.",
        "These are model-to-model scenario comparisons across five synthetic lawn geometries, not field validation.",
        "The slopes are illustrative; no scenario is claimed to match a real sprinkler.",
        "Metrics describe the current model and its objective function only.",
        "",
        "| Site | Slope | Baseline AR | Optimized AR | Baseline CU | Optimized CU | Baseline overspray % | Optimized overspray % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report.append(
            f"| {row['site']} | {row['radial_slope']} | {row['baseline_AR']} | "
            f"{row['optimized_AR']} | {row['baseline_CU']} | {row['optimized_CU']} | "
            f"{row['baseline_overspray_pct_of_own_water']} | "
            f"{row['optimized_overspray_pct_of_own_water']} |"
        )
    ar_improved = sum(float(row["AR_metric_improvement_pct"]) > 0 for row in rows)
    overspray_increased = sum(
        float(row["optimized_overspray_pct_of_own_water"])
        > float(row["baseline_overspray_pct_of_own_water"])
        for row in rows
    )
    report += [
        "",
        f"Across these {len(rows)} scenario/site combinations, the legacy AR metric improved in {ar_improved};",
        f"the reported overspray share increased in {overspray_increased}. These metrics can trade off.",
        "The single-objective movable run minimizes legacy AR; it does not independently minimize overspray.",
        "For an explicit overspray-versus-deficit tradeoff, use the project's Pareto mode and inspect its front.",
        "Do not interpret these outputs as measured irrigation savings. Water savings, cost savings, and payback remain unestimated.",
        "Each scenario's full CSV, PNGs, metadata, and console log are stored in its subdirectory.",
    ]
    (outdir / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\nSensitivity summary: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
