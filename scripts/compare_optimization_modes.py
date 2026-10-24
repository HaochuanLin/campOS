#!/usr/bin/env python3
"""Matched legacy-AR versus Pareto benchmark on the same synthetic sites."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODES = ("movable", "fixed", "pareto-movable", "pareto-fixed")


def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="out/optimization-benchmark")
    parser.add_argument("--sites", nargs="+", choices=list("ABCDE"), default=list("ABCDE"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--cell-size", type=float, default=0.5)
    parser.add_argument("--radial-slope", type=float, default=0.0)
    parser.add_argument("--dry-fraction-limit", type=float, default=0.02)
    parser.add_argument("--target-factor", type=float, default=1.0)
    parser.add_argument("--cu-drop-budget", type=float, default=0.03)
    parser.add_argument("--max-overspray-increase", type=float, default=0.0,
                        help="maximum allowed increase in Pareto f1 over baseline (0..1; default 0)")
    parser.add_argument("--pareto-weights", default="0,0.25,0.5,0.75,1")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    out = Path(args.outdir).resolve()
    raw = out / "simulation"
    raw.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(ROOT / "campos_sim.py"), "--mode", *MODES,
        "--sites", *args.sites, "--seed", str(args.seed),
        "--cell-size", str(args.cell_size), "--radial-slope", str(args.radial_slope),
        "--dry-fraction-limit", str(args.dry_fraction_limit),
        "--target-factor", str(args.target_factor),
        "--cu-drop-budget", str(args.cu_drop_budget),
        "--max-overspray-increase", str(args.max_overspray_increase),
        "--pareto-weights", args.pareto_weights, "--outdir", str(raw),
    ]
    if args.quick:
        command.append("--quick")
    result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False)
    (out / "console.log").write_text(result.stdout, encoding="utf-8")
    print(result.stdout, end="")
    if result.returncode:
        raise SystemExit(f"Simulation failed; inspect {out / 'console.log'}")

    metadata = json.loads((raw / "run_metadata.json").read_text(encoding="utf-8"))
    if set(metadata["selected_modes"]) != set(MODES):
        raise SystemExit("Metadata does not match the requested four modes")
    cfg = metadata["config"]
    if int(cfg["seed"]) != args.seed or abs(float(cfg["cell"]) - args.cell_size) > 1e-12:
        raise SystemExit("Recorded seed or cell size differs from requested settings")
    if abs(float(cfg["max_overspray_increase"]) - args.max_overspray_increase) > 1e-12:
        raise SystemExit("Recorded overspray-increase tolerance differs from requested setting")
    if abs(float(cfg["radial_slope"]) - args.radial_slope) > 1e-12:
        raise SystemExit("Recorded radial slope differs from requested setting")

    single = {m: load_csv(raw / f"results_{m}.csv") for m in ("movable", "fixed")}
    pareto = {
        "pareto-movable": load_csv(raw / "pareto_movable.csv"),
        "pareto-fixed": load_csv(raw / "pareto_fixed.csv"),
    }
    # The dry-area CSV column encodes the configured constraint in its name.
    pareto_dry_column = next(
        (key for key in pareto["pareto-movable"][0] if key.startswith("dry_area_pct_constraint_le_")),
        None,
    ) if pareto["pareto-movable"] else None
    if pareto_dry_column is None:
        raise SystemExit("Pareto CSV is missing its dry-area constraint column")
    columns = [
        "site", "mode", "objective_family", "seed", "cell_size_m", "radial_slope", "max_overspray_increase",
        "sprinkler_count", "baseline_AR", "result_AR",
        "baseline_overspray_pct_of_own_water", "result_overspray_pct_of_own_water",
        "baseline_CU", "result_CU", "baseline_dry_area_pct_legacy_definition",
        "result_dry_area_pct", "pareto_f1_pct_of_baseline_total_water",
        "pareto_f2_pct_mean_relative_target_shortfall", "pareto_total_water_relative",
        "pareto_front_points", "selected_tradeoff",
        "guardrail_cu_rejected_candidates", "guardrail_overspray_rejected_candidates",
        "guardrail_interior_deficit_rejected_candidates", "guardrail_dry_area_rejected_candidates",
        "selection_failure_reasons", "status",
    ]
    rows = []
    for mode in MODES:
        base_mode = "fixed" if mode in ("fixed", "pareto-fixed") else "movable"
        for site_id in args.sites:
            base = next((r for r in single[base_mode] if r["site"].split()[0] == site_id), None)
            if base is None:
                raise SystemExit(f"Missing result for site {site_id} in {base_mode}")
            row = {
                "site": base["site"], "mode": mode,
                "objective_family": "Pareto overspray/deficit" if mode.startswith("pareto-") else "legacy AR",
                "seed": args.seed, "cell_size_m": args.cell_size, "radial_slope": args.radial_slope,
                "max_overspray_increase": args.max_overspray_increase,
                "sprinkler_count": base["sprinkler_count"], "baseline_AR": base["baseline_AR"],
                "result_AR": base["optimized_AR"] if not mode.startswith("pareto-") else "",
                "baseline_overspray_pct_of_own_water": base["baseline_overspray_pct_of_own_water"],
                "result_overspray_pct_of_own_water": base["optimized_overspray_pct_of_own_water"] if not mode.startswith("pareto-") else "",
                "baseline_CU": base["baseline_CU"],
                "result_CU": base["optimized_CU"] if not mode.startswith("pareto-") else "",
                "baseline_dry_area_pct_legacy_definition": base["baseline_dry_area_pct"],
                "result_dry_area_pct": base["optimized_dry_area_pct"] if not mode.startswith("pareto-") else "",
                "pareto_f1_pct_of_baseline_total_water": "",
                "pareto_f2_pct_mean_relative_target_shortfall": "",
                "pareto_total_water_relative": "", "pareto_front_points": 0,
                "selected_tradeoff": "",
                "guardrail_cu_rejected_candidates": 0,
                "guardrail_overspray_rejected_candidates": 0,
                "guardrail_interior_deficit_rejected_candidates": 0,
                "guardrail_dry_area_rejected_candidates": 0,
                "selection_failure_reasons": "", "status": "completed",
            }
            if mode.startswith("pareto-"):
                candidates = [r for r in pareto[mode]
                              if r["site"].split()[0] == site_id and r["point_type"] == "PARETO"]
                selected = next((r for r in candidates if r["selected_tradeoff"].upper() == "YES"), None)
                row["pareto_front_points"] = len(candidates)
                diagnostic_fields = {
                    "guardrail_cu_pass": "guardrail_cu_rejected_candidates",
                    "guardrail_overspray_pass": "guardrail_overspray_rejected_candidates",
                    "guardrail_interior_deficit_pass": "guardrail_interior_deficit_rejected_candidates",
                    "guardrail_dry_area_pass": "guardrail_dry_area_rejected_candidates",
                }
                for check_field, count_field in diagnostic_fields.items():
                    row[count_field] = sum(candidate.get(check_field, "").lower() == "false"
                                            for candidate in candidates)
                if not selected:
                    failed = [label for field, label in (
                        ("guardrail_cu_pass", "CU"),
                        ("guardrail_overspray_pass", "overspray"),
                        ("guardrail_interior_deficit_pass", "interior_deficit"),
                        ("guardrail_dry_area_pass", "dry_area"),
                    ) if any(candidate.get(field, "").lower() == "false" for candidate in candidates)]
                    row["selection_failure_reasons"] = ";".join(failed) or "no_candidates"
                if selected:
                    row.update({
                        "selected_tradeoff": "YES", "result_AR": selected["AR_legacy"],
                        "result_overspray_pct_of_own_water": selected["overspray_pct_of_own_water"],
                        "result_CU": selected["CU"], "result_dry_area_pct": selected[pareto_dry_column],
                        "pareto_f1_pct_of_baseline_total_water": selected[
                            next(key for key in selected if key.endswith("_f1"))
                        ],
                        "pareto_f2_pct_mean_relative_target_shortfall": selected["interior_deficit_pct_f2"],
                        "pareto_total_water_relative": selected["total_water_relative_to_baseline"],
                    })
                else:
                    row["status"] = "no_selected_feasible_tradeoff"
            rows.append(row)

    with (out / "benchmark_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    report = [
        "# Matched campOS optimization benchmark", "",
        f"- Synthetic sites: {', '.join(args.sites)}.",
        f"- Shared seed: {args.seed}; cell size: {args.cell_size:g} m; radial slope: {args.radial_slope:g}.",
        f"- Dry-area limit: {args.dry_fraction_limit:g}; target factor: {args.target_factor:g}; CU-drop budget: {args.cu_drop_budget:g}; max overspray increase: {args.max_overspray_increase:g}.",
        f"- Pareto weights: {args.pareto_weights}; quick mode: {args.quick}.",
        "- All four modes ran in one invocation and share site geometry, baseline layouts, and model configuration.",
        "- Legacy AR and Pareto objectives differ. A Pareto point is selected only if it stays within the baseline-relative CU-loss budget and configured overspray-increase tolerance.",
        "", "| Site | Mode | Heads | AR | Own-water overspray % | CU | Dry area % | Pareto f1 % | Pareto f2 % | Front points | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        val = lambda k: r[k] if r[k] not in ("", None) else "—"
        report.append(
            f"| {r['site']} | {r['mode']} | {r['sprinkler_count']} | {val('result_AR')} | "
            f"{val('result_overspray_pct_of_own_water')} | {val('result_CU')} | "
            f"{val('result_dry_area_pct')} | {val('pareto_f1_pct_of_baseline_total_water')} | "
            f"{val('pareto_f2_pct_mean_relative_target_shortfall')} | {r['pareto_front_points']} | {r['status']} |"
        )
    report += [
        "", "## Interpretation limits",
        "- Pareto f1 divides outside water by baseline total modelled water; legacy overspray share divides by each layout's own total. These percentages have different denominators.",
        "- Pareto f2 is mean relative shortfall below the configured target. Pareto and legacy dry-area metrics use different thresholds.",
        "- The Pareto front is a stochastic finite-search approximation, not a guaranteed global optimum.",
        "- Synthetic sites and the default radial field are not field-calibrated. AR improvement is not a water-savings estimate; water, cost, and payback savings are not estimated.",
        "", "Raw CSVs, plots, metadata, and console log are in the simulation subdirectory.",
    ]
    (out / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Benchmark summary: {out / 'benchmark_summary.csv'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
