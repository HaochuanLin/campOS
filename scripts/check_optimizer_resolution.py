#!/usr/bin/env python3
"""Check whether Pareto-selected sprinkler layouts are stable across grid sizes.

This is a numerical sensitivity diagnostic, not field validation. It reruns the
optimizer independently at every grid resolution with identical site inputs,
seed, and search settings, then compares the selected solutions to the finest
grid. A missing feasible selection is reported, never silently substituted.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from campos import campos_sim as sim  # noqa: E402


def parse_cell_sizes(value):
    try:
        sizes = [float(part) for part in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("cell sizes must be comma-separated numbers") from exc
    if not sizes or any(not (size > 0 and size < float("inf")) for size in sizes):
        raise argparse.ArgumentTypeError("cell sizes must be finite and greater than zero")
    if len(set(sizes)) != len(sizes):
        raise argparse.ArgumentTypeError("cell sizes must not contain duplicates")
    if len(sizes) < 2:
        raise argparse.ArgumentTypeError("at least two cell sizes are required")
    return sorted(sizes, reverse=True)


def circular_delta_deg(a, b):
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def compare_layouts(layout, reference):
    if layout.shape != reference.shape:
        return {"head_count_match": False, "position_rms_from_finest_m": "", "radius_mae_from_finest_m": "",
                "start_angle_mae_from_finest_deg": "", "arc_width_mae_from_finest_deg": ""}
    delta_xy = layout[:, :2] - reference[:, :2]
    return {
        "head_count_match": True,
        "position_rms_from_finest_m": f"{(float((delta_xy ** 2).sum(axis=1).mean()) ** 0.5):.6f}",
        "radius_mae_from_finest_m": f"{float(abs(layout[:, 2] - reference[:, 2]).mean()):.6f}",
        "start_angle_mae_from_finest_deg": f"{float(sum(circular_delta_deg(a, b) for a, b in zip(layout[:, 3], reference[:, 3])) / len(layout)):.6f}",
        "arc_width_mae_from_finest_deg": f"{float(abs(layout[:, 4] - reference[:, 4]).mean()):.6f}",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polygon-csv", required=True, help="surveyed lawn polygon CSV")
    parser.add_argument("--heads-csv", required=True, help="initial measured sprinkler layout CSV")
    parser.add_argument("--protected-surface-csv", required=True, help="surveyed road/sidewalk polygon CSV")
    parser.add_argument("--cell-sizes", type=parse_cell_sizes, default=parse_cell_sizes("2,1,0.5"))
    parser.add_argument("--mode", choices=("fixed", "movable"), default="fixed",
                        help="fixed preserves head coordinates; movable permits relocation")
    parser.add_argument("--seed", type=int, default=sim.CFG["seed"])
    parser.add_argument("--dry-fraction-limit", type=float, default=sim.CFG["dry_frac_limit"])
    parser.add_argument("--target-factor", type=float, default=sim.CFG["target_factor"])
    parser.add_argument("--cu-drop-budget", type=float, default=sim.CFG["cu_drop_budget"])
    parser.add_argument("--max-overspray-increase", type=float, default=sim.CFG["max_overspray_increase"])
    parser.add_argument("--pareto-weights", default=",".join(str(x) for x in sim.CFG["pareto_weights"]))
    parser.add_argument("--quick", action="store_true", help="use smoke-test optimizer iteration counts")
    parser.add_argument("--max-f1-spread", type=float, default=None,
                        help="optional max-minus-min selected f1 spread across grids (fraction of baseline total water)")
    parser.add_argument("--max-f2-spread", type=float, default=None,
                        help="optional max-minus-min selected f2 spread across grids (fractional deficit)")
    parser.add_argument("--max-position-rms", type=float, default=None,
                        help="optional maximum selected-layout position RMS from the finest-grid solution, metres")
    parser.add_argument("--out", default="out/optimizer-resolution.csv")
    args = parser.parse_args(argv)

    for name, value in (("--dry-fraction-limit", args.dry_fraction_limit),
                        ("--target-factor", args.target_factor),
                        ("--cu-drop-budget", args.cu_drop_budget),
                        ("--max-overspray-increase", args.max_overspray_increase)):
        if not (value >= 0 and value < float("inf")):
            parser.error(f"{name} must be finite and non-negative")
    if args.dry_fraction_limit > 1 or args.cu_drop_budget > 1 or args.max_overspray_increase > 1:
        parser.error("dry limit, CU budget, and overspray tolerance must be in [0,1]")
    if args.target_factor <= 0:
        parser.error("--target-factor must be greater than zero")
    if args.max_f1_spread is not None and not (0 <= args.max_f1_spread <= 1):
        parser.error("--max-f1-spread must be in [0,1]")
    if args.max_f2_spread is not None and not (0 <= args.max_f2_spread <= 1):
        parser.error("--max-f2-spread must be in [0,1]")
    if args.max_position_rms is not None and args.max_position_rms < 0:
        parser.error("--max-position-rms must be non-negative")
    try:
        polygon = sim.load_polygon_csv(args.polygon_csv)
        protected = sim.load_polygon_csv(args.protected_surface_csv)
        if sim.polygons_overlap(polygon, protected):
            parser.error("lawn and protected-surface polygons overlap")
        cfg0 = dict(sim.CFG)
        heads = sim.load_heads_csv(args.heads_csv, polygon, cfg0)
        weights = tuple(float(part) for part in args.pareto_weights.split(","))
        if not weights or any(not (0 <= w <= 1) for w in weights):
            raise ValueError("Pareto weights must be comma-separated numbers in [0,1]")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    results = []
    layouts = {}
    for cell in args.cell_sizes:
        cfg = dict(sim.CFG)
        cfg.update(
            cell=cell, seed=args.seed, dry_frac_limit=args.dry_fraction_limit,
            target_factor=args.target_factor, cu_drop_budget=args.cu_drop_budget,
            max_overspray_increase=args.max_overspray_increase,
            pareto_weights=weights, initial_heads=heads.copy(),
            protected_polygon=protected,
        )
        if args.quick:
            cfg.update(sa_iters=2500, restarts=1, pareto_iters=1200)
        fixed_xy = args.mode == "fixed"
        sim._SITE_CACHE.clear()
        try:
            site, h0 = sim.get_site_and_baseline("resolution-check", polygon, cfg)
            refs = sim.reference_levels(site, h0, cfg)
            warm = sim.optimize(site, h0, cfg, cfg["seed"], fixed_xy=fixed_xy)
            candidates = sim.pareto_search(site, h0, cfg, fixed_xy, cfg["seed"] + 5, refs, warm=warm)
            if fixed_xy and any(not (candidate[:, :2] == h0[:, :2]).all() for candidate in candidates):
                raise RuntimeError("fixed-position optimizer unexpectedly moved a sprinkler")
            indexed = sorted(enumerate(candidates),
                             key=lambda item: sim.bi_eval(site, site.total(item[1]), refs, cfg)[0])
            if len(indexed) > cfg["pareto_max_points"]:
                picks = set(np.unique(np.round(np.linspace(
                    0, len(indexed) - 1, cfg["pareto_max_points"])).astype(int)).tolist())
                indexed = [item for i, item in enumerate(indexed) if i in picks]
            evaluated = [(sim.bi_report(site, layout, refs, cfg), layout) for _, layout in indexed]
            evaluated.sort(key=lambda item: item[0]["f1"])
            front = [item[0] for item in evaluated]
            front_layouts = [item[1] for item in evaluated]
            baseline = sim.bi_report(site, h0, refs, cfg)
            selected = sim.select_tradeoff(front, cfg["cu_drop_budget"], baseline=baseline,
                                           max_overspray_increase=cfg["max_overspray_increase"],
                                           dry_limit=cfg["dry_frac_limit"])
            chosen = front_layouts[selected] if selected is not None else None
            selected_report = front[selected] if selected is not None else None
            layouts[cell] = chosen
            results.append({
                "cell_size_m": cell, "grid_cells_lawn": int(site.mask.sum()),
                "grid_cells_protected_surface": int(site.protected_mask.sum()),
                "pareto_front_points": len(front), "feasible_selection": selected is not None,
                "selected_f1_pct_baseline_total_water": "" if selected_report is None else f"{100*selected_report['f1']:.6f}",
                "selected_f2_pct_mean_relative_deficit": "" if selected_report is None else f"{100*selected_report['f2']:.6f}",
                "selected_CU": "" if selected_report is None else f"{selected_report['CU']:.6f}",
                "selected_dry_area_pct": "" if selected_report is None else f"{100*selected_report['dry']:.6f}",
                "selected_protected_water_share_pct": "" if selected_report is None else f"{100*selected_report['protected_surface_water'] / max(selected_report['water_rel'], 1e-12):.6f}",
                "layout_reference_cell_m": "", "position_rms_from_finest_m": "",
                "radius_mae_from_finest_m": "", "start_angle_mae_from_finest_deg": "",
                "arc_width_mae_from_finest_deg": "", "head_count_match": "", "error": "",
            })
        except ValueError as exc:
            results.append({
                "cell_size_m": cell, "grid_cells_lawn": "", "grid_cells_protected_surface": "",
                "pareto_front_points": 0, "feasible_selection": False,
                "selected_f1_pct_baseline_total_water": "", "selected_f2_pct_mean_relative_deficit": "",
                "selected_CU": "", "selected_dry_area_pct": "", "selected_protected_water_share_pct": "",
                "layout_reference_cell_m": "", "position_rms_from_finest_m": "",
                "radius_mae_from_finest_m": "", "start_angle_mae_from_finest_deg": "",
                "arc_width_mae_from_finest_deg": "", "head_count_match": "", "error": str(exc),
            })

    valid = [r for r in results if r["feasible_selection"]]
    if valid:
        f1 = [float(r["selected_f1_pct_baseline_total_water"]) / 100 for r in valid]
        f2 = [float(r["selected_f2_pct_mean_relative_deficit"]) / 100 for r in valid]
        f1_spread, f2_spread = max(f1) - min(f1), max(f2) - min(f2)
    else:
        f1_spread = f2_spread = None
    finest = min(args.cell_sizes)
    reference_layout = layouts.get(finest)
    for row in results:
        row["layout_reference_cell_m"] = finest
        layout = layouts.get(float(row["cell_size_m"]))
        if reference_layout is not None and layout is not None:
            row.update(compare_layouts(layout, reference_layout))
        elif reference_layout is None:
            row["error"] = (row["error"] + "; " if row["error"] else "") + "finest grid has no feasible selected layout"

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(key for row in results for key in row))
    with output.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {output}")
    print(f"Mode={args.mode}; seed={args.seed}; grid sizes={','.join(f'{c:g}' for c in args.cell_sizes)} m")
    print(f"Feasible selections={sum(bool(r['feasible_selection']) for r in results)}/{len(results)}")
    if f1_spread is not None:
        print(f"Selected f1 spread across feasible grids: {100*f1_spread:.3f} percentage points of baseline total water")
        print(f"Selected f2 spread across feasible grids: {100*f2_spread:.3f} percentage points of mean relative deficit")
    else:
        print("No grid produced a feasible selected layout; no stability claim is possible")
    position_values = [float(r["position_rms_from_finest_m"]) for r in results
                       if r["position_rms_from_finest_m"] != ""]
    max_position = max(position_values) if position_values else None
    failures = []
    threshold_requested = any(value is not None for value in (
        args.max_f1_spread, args.max_f2_spread, args.max_position_rms
    ))
    if len(valid) != len(results) and threshold_requested:
        failures.append("one or more grid sizes had no feasible selected layout")
    if args.max_f1_spread is not None and (f1_spread is None or f1_spread > args.max_f1_spread):
        failures.append(f"f1 spread exceeds {args.max_f1_spread:g}")
    if args.max_f2_spread is not None and (f2_spread is None or f2_spread > args.max_f2_spread):
        failures.append(f"f2 spread exceeds {args.max_f2_spread:g}")
    layout_mismatch = any(row["head_count_match"] is False for row in results)
    if args.max_position_rms is not None and (
            max_position is None or max_position > args.max_position_rms or layout_mismatch):
        failures.append(f"layout position RMS exceeds {args.max_position_rms:g} m, is unavailable, or head counts differ")
    if failures:
        print("FAIL: " + "; ".join(failures))
        return 2
    if len(valid) != len(results):
        print("REPORT ONLY: at least one grid has no feasible selected layout; no stability conclusion for that grid")
    elif threshold_requested:
        print("PASS: all requested grid-sensitivity checks passed")
    else:
        print("REPORT ONLY: no acceptance thresholds requested; review metric and layout variation before relying on results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
