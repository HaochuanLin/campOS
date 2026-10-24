#!/usr/bin/env python3
"""Validate and normalize raw campOS catch-can observations.

This checks data completeness and units only. It does not compare observations
with model predictions and must not be described as field validation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

REQUIRED_COLUMNS = {
    "site_id", "run_id", "can_id", "x_m", "y_m", "zone",
    "collection_duration_s", "collected_volume_ml", "measured_depth_mm",
    "container_opening_area_cm2", "validity_flag", "split",
}
ALLOWED_ZONES = {"inside", "outside", "boundary", "unknown"}
ALLOWED_FLAGS = {"valid", "exclude", "unknown"}


def number(value: str, field: str, row_number: int, *, required: bool = False) -> float | None:
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"row {row_number}: {field} is required")
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"row {row_number}: {field} must be finite")
    return parsed


def validate_file(input_path: Path, output_csv: Path, output_json: Path) -> dict:
    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)

    if not rows:
        raise ValueError("input contains no observation rows; fill the empty template first")

    normalized = []
    seen = set()
    run_splits = {}
    issues = []
    zone_counts = Counter()
    valid_count = 0

    for row_number, row in enumerate(rows, start=2):
        site_id = (row.get("site_id") or "").strip()
        run_id = (row.get("run_id") or "").strip()
        can_id = (row.get("can_id") or "").strip()
        if not site_id or not run_id or not can_id:
            raise ValueError(f"row {row_number}: site_id, run_id, and can_id are required")
        key = (site_id, run_id, can_id)
        if key in seen:
            raise ValueError(f"row {row_number}: duplicate site_id/run_id/can_id {key}")
        seen.add(key)

        x = number(row.get("x_m", ""), "x_m", row_number, required=True)
        y = number(row.get("y_m", ""), "y_m", row_number, required=True)
        duration = number(row.get("collection_duration_s", ""), "collection_duration_s", row_number, required=True)
        volume = number(row.get("collected_volume_ml", ""), "collected_volume_ml", row_number)
        depth = number(row.get("measured_depth_mm", ""), "measured_depth_mm", row_number)
        area = number(row.get("container_opening_area_cm2", ""), "container_opening_area_cm2", row_number)
        if duration <= 0:
            raise ValueError(f"row {row_number}: collection_duration_s must be > 0")
        if volume is not None and volume < 0:
            raise ValueError(f"row {row_number}: collected_volume_ml must be >= 0")
        if depth is not None and depth < 0:
            raise ValueError(f"row {row_number}: measured_depth_mm must be >= 0")
        if area is not None and area <= 0:
            raise ValueError(f"row {row_number}: container_opening_area_cm2 must be > 0")
        if depth is None:
            if volume is None or area is None:
                raise ValueError(
                    f"row {row_number}: provide measured_depth_mm or both "
                    "collected_volume_ml and container_opening_area_cm2"
                )
            # 1 ml / cm^2 equals 10 mm of water depth.
            depth = volume / area * 10.0
        elif volume is not None and area is not None:
            derived = volume / area * 10.0
            if not math.isclose(depth, derived, rel_tol=0.1, abs_tol=0.5):
                issues.append(
                    f"row {row_number}: recorded depth differs from volume/area-derived "
                    f"depth ({depth:.3f} mm vs {derived:.3f} mm); verify units/instrument notes"
                )

        zone = (row.get("zone") or "unknown").strip().lower()
        if zone not in ALLOWED_ZONES:
            raise ValueError(f"row {row_number}: zone must be one of {sorted(ALLOWED_ZONES)}")
        split = (row.get("split") or "").strip().lower()
        if split not in {"calibration", "holdout"}:
            raise ValueError(f"row {row_number}: split must be calibration or holdout")
        run_key = (site_id, run_id)
        if run_key in run_splits and run_splits[run_key] != split:
            raise ValueError(f"row {row_number}: run {run_key} mixes calibration and holdout")
        run_splits[run_key] = split

        flag = (row.get("validity_flag") or "unknown").strip().lower()
        if flag not in ALLOWED_FLAGS:
            raise ValueError(f"row {row_number}: validity_flag must be one of {sorted(ALLOWED_FLAGS)}")
        if flag == "valid":
            valid_count += 1
        zone_counts[zone] += 1
        normalized.append({
            "site_id": site_id, "run_id": run_id, "can_id": can_id,
            "x_m": x, "y_m": y, "zone": zone,
            "collection_duration_s": duration,
            "collected_volume_ml": "" if volume is None else volume,
            "measured_depth_mm_normalized": depth,
            "container_opening_area_cm2": "" if area is None else area,
            "validity_flag": flag,
            "split": split,
            "exclusion_reason": (row.get("exclusion_reason") or "").strip(),
            "observation_datetime": (row.get("observation_datetime") or "").strip(),
            "notes": (row.get("notes") or "").strip(),
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    fields = list(normalized[0].keys())
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(normalized)
    summary = {
        "input_file": str(input_path),
        "row_count": len(normalized),
        "valid_flag_count": valid_count,
        "excluded_flag_count": sum(r["validity_flag"] == "exclude" for r in normalized),
        "unknown_flag_count": sum(r["validity_flag"] == "unknown" for r in normalized),
        "zone_counts": dict(sorted(zone_counts.items())),
        "quality_warnings": issues,
        "derived_depth_unit": "mm",
        "status": "schema_and_unit_checks_passed_with_warnings" if issues else "schema_and_unit_checks_passed",
        "scope_note": "Data QC only; no model comparison, calibration, or field validation performed.",
    }
    output_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Raw catch-can observation CSV")
    parser.add_argument("--outdir", type=Path, default=Path("out/field-data-qc"))
    args = parser.parse_args()
    try:
        summary = validate_file(
            args.input,
            args.outdir / "field_observation_qc.csv",
            args.outdir / "field_observation_qc.json",
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))
    print(f"Normalized observations: {args.outdir / 'field_observation_qc.csv'}")
    print(f"QC summary: {args.outdir / 'field_observation_qc.json'}")


if __name__ == "__main__":
    main()
