#!/usr/bin/env python3
"""Run a reproducible multi-seed/grid/radial-slope robustness study.

This is numerical sensitivity analysis on synthetic sites, not empirical
validation, uncertainty quantification, or evidence of real-world savings.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
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


def slug(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="out/parameter-sensitivity")
    parser.add_argument("--sites", nargs="+", choices=list("ABCDE"), default=list("ABCDE"))
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 41])
    parser.add_argument("--cell-sizes", nargs="+", type=float, default=[0.5, 1.0])
    parser.add_argument("--slopes", nargs="+", type=float, default=[-0.5, 0.0, 1.0])
    parser.add_argument("--quick", action="store_true", help="use the simulator's reduced iteration budget")
    args = parser.parse_args()
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds must contain unique integer values")
    if not args.cell_sizes or any(not math.isfinite(x) or x <= 0 for x in args.cell_sizes):
        parser.error("--cell-sizes must contain finite positive values")
    if not args.slopes or any(not math.isfinite(x) or x <= -1 for x in args.slopes):
        parser.error("--slopes must contain finite values greater than -1")
    if len(set(args.cell_sizes)) != len(args.cell_sizes):
        parser.error("--cell-sizes must not contain duplicates")
    if len(set(args.slopes)) != len(args.slopes):
        parser.error("--slopes must not contain duplicates")
    return args


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    total_runs = len(args.sites) * len(args.seeds) * len(args.cell_sizes) * len(args.slopes)
    run_number = 0
    for site_id in args.sites:
        for seed in args.seeds:
            for cell_size in args.cell_sizes:
                for slope in args.slopes:
                    run_number += 1
                    scenario = f"site_{site_id}_seed_{seed}_cell_{slug(cell_size)}_slope_{slug(slope)}"
                    run_dir = outdir / scenario
                    command = [
                        sys.executable, str(ROOT / "campos_sim.py"),
                        "--mode", "movable", "--sites", site_id,
                        "--seed", str(seed), "--cell-size", str(cell_size),
                        "--radial-slope", str(slope), "--outdir", str(run_dir),
                    ]
                    if args.quick:
                        command.append("--quick")
                    print(f"[{run_number}/{total_runs}] {scenario}", flush=True)
                    completed = subprocess.run(
                        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, check=False,
                    )
                    (run_dir / "console.log").write_text(completed.stdout, encoding="utf-8")
                    if completed.returncode:
                        print(completed.stdout, end="")
                        raise SystemExit(f"Simulation failed for {scenario}; see {run_dir / 'console.log'}")

                    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
                    cfg = metadata.get("config", {})
                    actual_seed = int(cfg.get("seed", -999999))
                    actual_cell = float(cfg.get("cell", float("nan")))
                    actual_slope = float(metadata.get("radial_distribution", {}).get("radial_slope", float("nan")))
                    if actual_seed != seed or not math.isclose(actual_cell, cell_size, rel_tol=0, abs_tol=1e-12) or not math.isclose(actual_slope, slope, rel_tol=0, abs_tol=1e-12):
                        raise SystemExit(f"Recorded configuration mismatch for {scenario}")

                    with (run_dir / "results_movable.csv").open(newline="", encoding="utf-8-sig") as handle:
                        results = list(csv.DictReader(handle))
                    matching = [r for r in results if r["site"].split()[0] == site_id]
                    if len(matching) != 1:
                        raise SystemExit(f"Expected exactly one result for site {site_id} in {scenario}, got {len(matching)}")
                    result = matching[0]
                    row = {
                        "scenario": scenario, "site_id": site_id, "seed": str(seed),
                        "cell_size_m": f"{cell_size:g}", "radial_slope": f"{slope:g}",
                        "sprinkler_count": result["sprinkler_count"], "status": "completed",
                        "interpretation": "synthetic numerical sensitivity only; not field validation",
                    }
                    row.update({metric: result.get(metric, "") for metric in METRICS})
                    rows.append(row)

    columns = [
        "scenario", "site_id", "seed", "cell_size_m", "radial_slope",
        "sprinkler_count", "status", *METRICS, "interpretation",
    ]
    summary_path = outdir / "sensitivity_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    improvements = [float(r["AR_metric_improvement_pct"]) for r in rows if r["AR_metric_improvement_pct"]]
    over_changes = [
        float(r["optimized_overspray_pct_of_own_water"]) - float(r["baseline_overspray_pct_of_own_water"])
        for r in rows if r["optimized_overspray_pct_of_own_water"] and r["baseline_overspray_pct_of_own_water"]
    ]
    report = [
        "# campOS parameter sensitivity and numerical robustness",
        "",
        f"- Completed runs: {len(rows)} of {total_runs}.",
        f"- Synthetic sites: {', '.join(args.sites)}.",
        f"- Seeds: {', '.join(map(str, args.seeds))}; grid sizes (m): {', '.join(f'{x:g}' for x in args.cell_sizes)}.",
        f"- Radial slopes: {', '.join(f'{x:g}' for x in args.slopes)}; quick mode: {args.quick}.",
        "- Every run records the requested seed, grid size, and radial slope; the script fails on configuration mismatch.",
        "- This is a sensitivity/algorithmic repeatability check for a simplified synthetic model. It is not field validation, a probabilistic uncertainty estimate, or a measured water-savings study.",
        "- Different grid sizes change the raster approximation; different seeds expose stochastic optimizer variability; slopes are illustrative shape assumptions, not calibrated sprinkler physics.",
        "",
        f"- Legacy AR metric improved in {sum(x > 0 for x in improvements)} / {len(improvements)} runs.",
        f"- Legacy AR metric improvement range: {min(improvements):.4g}% to {max(improvements):.4g}%." if improvements else "- No AR improvement values available.",
        f"- Own-water overspray share increased in {sum(x > 0 for x in over_changes)} / {len(over_changes)} runs." if over_changes else "- No overspray comparisons available.",
        "- AR metric improvement is not water savings. Results can vary with seed, raster resolution, and radial assumption; do not select a production default from this sweep alone.",
        "",
        "Full per-run values and configuration are in sensitivity_summary.csv; each scenario folder contains raw outputs, plots, metadata, and console log.",
        "Independent validation requires measured site geometry and held-out catch-can/field observations collected under documented conditions.",
    ]
    (outdir / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Sensitivity summary: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
