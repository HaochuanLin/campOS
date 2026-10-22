#!/usr/bin/env python3
"""Compare a spacing-based precipitation estimate with a published chart.

The bundled reference data are Rain Bird 5000 Series standard-angle, 1.5 nozzle
values. Chart precipitation rates assume half-circle operation and square or
triangular spacing at 50% of throw diameter (spacing = throw radius). This is
a manufacturer-chart consistency check, not independent field validation.
"""
import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from campos.model import spacing_precipitation_mm_h  # noqa: E402

DEFAULT_DATA = ROOT / "data" / "benchmarks" / "rainbird_5000_standard_1_5.csv"


def run(path, max_error_tolerance=1.0):
    errors = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("benchmark CSV has no data rows")
    required = {"pressure_kpa", "flow_lpm", "throw_m", "square_precip_mm_h", "triangular_precip_mm_h"}
    if not required.issubset(rows[0]):
        raise ValueError(f"benchmark CSV missing columns: {sorted(required - set(rows[0]))}")
    print("pressure_kpa,arrangement,predicted_mm_h,chart_mm_h,absolute_error_mm_h")
    for row in rows:
        flow = float(row["flow_lpm"])
        # Manufacturer chart spacing is 50% of throw diameter, i.e. spacing = radius.
        spacing = float(row["throw_m"])
        for arrangement, key in (
            ("square", "square_precip_mm_h"),
            ("triangular", "triangular_precip_mm_h"),
        ):
            predicted = spacing_precipitation_mm_h(flow, spacing, arrangement, arc_fraction=0.5)
            observed = float(row[key])
            error = abs(predicted - observed)
            errors.append(error)
            print(f"{float(row['pressure_kpa']):.0f},{arrangement},{predicted:.3f},{observed:.3f},{error:.3f}")
    mae = sum(errors) / len(errors)
    maximum = max(errors)
    print(f"rows={len(rows)} comparisons={len(errors)} MAE_mm_h={mae:.3f} max_abs_error_mm_h={maximum:.3f}")
    if maximum > max_error_tolerance:
        raise SystemExit(
            f"FAIL: maximum error {maximum:.3f} exceeds tolerance {max_error_tolerance:.3f} mm/h"
        )
    print("PASS: all chart comparisons are within the rounding tolerance.")
    return mae, maximum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_DATA, help="published performance table CSV")
    parser.add_argument("--max-error-tolerance", type=float, default=1.0, help="maximum allowed absolute error in mm/h")
    args = parser.parse_args()
    run(args.csv, args.max_error_tolerance)


if __name__ == "__main__":
    main()
