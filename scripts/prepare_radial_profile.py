#!/usr/bin/env python3
"""Convert raw catch-can readings into campOS radial-profile CSV format.

Input columns: radius_fraction,depth_mm,run_minutes. Multiple cans / radial
transects at the same normalized radius are averaged as application rates.
This conversion is not a substitute for documenting the test conditions.
"""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


def convert(input_path: Path, output_path: Path) -> int:
    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"radius_fraction", "depth_mm", "run_minutes"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(
                "input CSV must contain radius_fraction,depth_mm,run_minutes columns"
            )
        groups = defaultdict(list)
        for line_number, row in enumerate(reader, start=2):
            try:
                radius = float(row["radius_fraction"])
                depth = float(row["depth_mm"])
                minutes = float(row["run_minutes"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_number}: values must be numeric") from exc
            if not all(math.isfinite(v) for v in (radius, depth, minutes)):
                raise ValueError(f"line {line_number}: values must be finite")
            if not 0.0 <= radius <= 1.0:
                raise ValueError(f"line {line_number}: radius_fraction must be in [0, 1]")
            if depth <= 0.0 or minutes <= 0.0:
                raise ValueError(f"line {line_number}: depth_mm and run_minutes must be positive")
            groups[radius].append(depth * 60.0 / minutes)

    radii = sorted(groups)
    if len(radii) < 3:
        raise ValueError("measurements must contain at least three distinct radii")
    if not math.isclose(radii[0], 0.0, abs_tol=1e-9) or not math.isclose(
        radii[-1], 1.0, abs_tol=1e-9
    ):
        raise ValueError("radius_fraction must cover both 0 and 1")
    mean_rates = [sum(groups[r]) / len(groups[r]) for r in radii]
    overall_mean = sum(mean_rates) / len(mean_rates)
    if not math.isfinite(overall_mean) or overall_mean <= 0:
        raise ValueError("mean catch-can application rate must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["radius_fraction", "relative_rate"])
        for radius, rate in zip(radii, mean_rates):
            writer.writerow([f"{radius:.8g}", f"{rate / overall_mean:.8g}"])
    return len(radii)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path, help="raw catch-can observations CSV")
    parser.add_argument("output_csv", type=Path, help="campOS profile CSV to create")
    args = parser.parse_args()
    try:
        count = convert(args.input_csv, args.output_csv)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Wrote {count} radial bins to {args.output_csv}")
    print("The simulator area-normalizes the relative profile when loading it.")
    print("Record nozzle, pressure, wind, test duration, and source separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
