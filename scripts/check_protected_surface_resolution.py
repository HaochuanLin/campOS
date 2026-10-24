#!/usr/bin/env python3
"""Check protected-surface polygon area error across simulation grid resolutions.

This is a geometry/rasterization diagnostic, not a water-distribution or
field-validation test. It reports how cell-centre inclusion approximates the
surveyed polygon's exact area at each requested grid size.
"""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos.campos_sim import CFG, load_heads_csv, load_polygon_csv, polygons_overlap  # noqa: E402
from campos.model import Site  # noqa: E402


def polygon_area(polygon):
    """Return absolute shoelace area in square metres."""
    x, y = polygon.T
    return abs(0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))


def parse_cell_sizes(value):
    try:
        sizes = [float(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("cell sizes must be comma-separated numbers") from exc
    if not sizes or any(not (size > 0 and size < float("inf")) for size in sizes):
        raise argparse.ArgumentTypeError("cell sizes must be finite positive numbers")
    if len(set(sizes)) != len(sizes):
        raise argparse.ArgumentTypeError("cell sizes must not contain duplicates")
    return sizes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polygon-csv", required=True, help="surveyed lawn polygon CSV (x_m,y_m)")
    parser.add_argument("--protected-surface-csv", required=True,
                        help="surveyed road/sidewalk polygon CSV (x_m,y_m)")
    parser.add_argument("--heads-csv", default=None,
                        help="optional fixed sprinkler layout; if supplied, compare protected-water share across grids")
    parser.add_argument("--cell-sizes", type=parse_cell_sizes, default=parse_cell_sizes("2,1,0.5,0.25"),
                        help="comma-separated cell sizes in metres (default: 2,1,0.5,0.25)")
    parser.add_argument("--margin", type=float, default=CFG["margin"],
                        help="simulation margin around both polygons in metres")
    parser.add_argument("--out", default="protected_surface_resolution.csv",
                        help="output CSV path")
    parser.add_argument("--max-relative-error", type=float, default=None,
                        help="optional maximum relative area error required at the finest requested cell size (0..1)")
    args = parser.parse_args(argv)
    if args.margin < 0 or not (args.margin < float("inf")):
        parser.error("--margin must be finite and non-negative")
    if args.max_relative_error is not None and not (0 <= args.max_relative_error <= 1):
        parser.error("--max-relative-error must be in [0,1]")

    lawn = load_polygon_csv(args.polygon_csv)
    protected = load_polygon_csv(args.protected_surface_csv)
    if polygons_overlap(lawn, protected):
        parser.error("protected-surface polygon overlaps the lawn interior")
    exact_area = polygon_area(protected)
    if exact_area <= 0:
        parser.error("protected-surface polygon must have positive area")

    rows = []
    for cell in sorted(args.cell_sizes, reverse=True):
        cfg = dict(CFG, cell=cell, margin=args.margin, protected_polygon=protected)
        try:
            site = Site(lawn, cfg)
        except ValueError as exc:
            parser.error(f"cell size {cell:g} m cannot rasterize the protected surface: {exc}")
        raster_area = int(site.protected_mask.sum()) * cell * cell
        abs_error = abs(raster_area - exact_area)
        rel_error = abs_error / exact_area
        water_metrics = {
            "protected_water_integral_m2_relative_depth": "",
            "total_water_integral_m2_relative_depth": "",
            "protected_water_pct_of_total_water": "",
        }
        if args.heads_csv:
            heads = load_heads_csv(args.heads_csv, lawn, cfg)
            total = site.total(heads)
            total_integral = float(total.sum()) * cell * cell
            protected_integral = float(total[site.protected_mask].sum()) * cell * cell
            if total_integral <= 0:
                parser.error("supplied sprinkler layout produces zero total modelled water")
            water_metrics = {
                "protected_water_integral_m2_relative_depth": f"{protected_integral:.6f}",
                "total_water_integral_m2_relative_depth": f"{total_integral:.6f}",
                "protected_water_pct_of_total_water": f"{100 * protected_integral / total_integral:.3f}",
            }
        rows.append({
            "cell_size_m": f"{cell:g}",
            "exact_protected_area_m2": f"{exact_area:.6f}",
            "rasterized_protected_area_m2": f"{raster_area:.6f}",
            "absolute_area_error_m2": f"{abs_error:.6f}",
            "relative_area_error_pct": f"{rel_error * 100:.3f}",
            "grid_cells_in_protected_surface": int(site.protected_mask.sum()),
            **water_metrics,
        })

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exact surveyed protected area: {exact_area:.3f} m^2")
    for row in rows:
        line = (f"cell={row['cell_size_m']} m  raster={row['rasterized_protected_area_m2']} m^2  "
                f"relative area error={row['relative_area_error_pct']}%  "
                f"cells={row['grid_cells_in_protected_surface']}")
        if row["protected_water_pct_of_total_water"]:
            line += f"  protected water share={row['protected_water_pct_of_total_water']}%"
        print(line)
    print(f"CSV written to {output}")
    finest = min(rows, key=lambda row: float(row["cell_size_m"]))
    if (args.max_relative_error is not None
            and float(finest["relative_area_error_pct"]) / 100 > args.max_relative_error):
        print(f"FAIL: finest grid exceeds requested {args.max_relative_error * 100:.3f}% area-error limit")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
