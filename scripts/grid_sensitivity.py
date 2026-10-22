#!/usr/bin/env python3
"""Measure raster-grid sensitivity of the baseline layout on a synthetic site.

This is a diagnostic, not physical validation. Each grid resolution gets its
own rasterized geometry and baseline search, so changes include both sampling
effects and any baseline-layout changes caused by the score.
"""
import argparse
import csv
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos.campos_sim import CFG, baseline_layout  # noqa: E402
from campos.model import SITES, Site, score  # noqa: E402


def polygon_area(poly):
    """Exact area of a simple polygon using the shoelace formula."""
    x = poly[:, 0]
    y = poly[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def analyze_site(name, poly, cell_sizes):
    exact_area = polygon_area(poly)
    rows = []
    for cell in cell_sizes:
        cfg = dict(CFG, cell=cell)
        site = Site(poly, cfg)
        heads = baseline_layout(site, cfg)
        total = site.total(heads)
        objective, metrics = score(site, total, cfg)
        rows.append(
            {
                "site": name,
                "cell_size_m": cell,
                "polygon_area_m2": exact_area,
                "raster_area_m2": float(site.area),
                "area_error_pct": 100.0 * (site.area - exact_area) / exact_area,
                "lawn_cells": int(site.idx.size),
                "baseline_heads": int(len(heads)),
                "objective": float(objective),
                "AR": float(metrics["AR"]),
                "overspray_share": float(metrics["overspray"]),
                "CU": float(metrics["CU"]),
                "dry_area_fraction": float(metrics["dry"]),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", choices=sorted(SITES), default="A Rectangle")
    parser.add_argument(
        "--cell-sizes",
        default="2,1,0.5",
        help="Comma-separated positive grid cell sizes in metres (default: 2,1,0.5)",
    )
    parser.add_argument("--out", type=Path, default=Path("grid_sensitivity.csv"))
    args = parser.parse_args()

    try:
        cell_sizes = [float(part.strip()) for part in args.cell_sizes.split(",")]
    except ValueError as exc:
        parser.error(f"invalid --cell-sizes value: {exc}")
    if not cell_sizes or any(not np.isfinite(c) or c <= 0 for c in cell_sizes):
        parser.error("--cell-sizes must contain finite positive numbers")

    rows = analyze_site(args.site, SITES[args.site](), cell_sizes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exact polygon area: {rows[0]['polygon_area_m2']:.3f} m^2")
    print("cell (m) | raster area (m^2) | area error (%) | AR | overspray | CU | dry")
    for row in rows:
        print(
            f"{row['cell_size_m']:8.3f} | {row['raster_area_m2']:17.3f} | "
            f"{row['area_error_pct']:14.4f} | {row['AR']:.5f} | "
            f"{row['overspray_share']:.5f} | {row['CU']:.5f} | "
            f"{row['dry_area_fraction']:.5f}"
        )
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
