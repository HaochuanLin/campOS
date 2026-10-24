#!/usr/bin/env python3
"""Validate sprinkler-model predictions against independent catch-can observations.

Observation CSV columns: x_m,y_m,observed_depth_mm,split where split is
calibration or holdout. A single non-negative multiplicative scale is fitted
on calibration rows only; holdout rows are never used to fit it. If --flow-lpm
is supplied, raw model predictions are in mm/h and are converted using the
measured collection duration. Otherwise the raw model output is relative and
only the calibration-scaled depth predictions are physically comparable.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos import campos_sim as sim  # noqa: E402
from campos.model import head_field, load_radial_profile_csv  # noqa: E402


def read_heads(path):
    required = {"x_m", "y_m", "radius_m", "start_angle_deg", "arc_width_deg"}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("heads CSV must contain x_m,y_m,radius_m,start_angle_deg,arc_width_deg columns")
        rows = list(reader)
    if not rows:
        raise ValueError("heads CSV must contain at least one sprinkler")
    try:
        heads = np.asarray([[float(row[key]) for key in (
            "x_m", "y_m", "radius_m", "start_angle_deg", "arc_width_deg"
        )] for row in rows], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("sprinkler layout values must be numeric") from exc
    if not np.all(np.isfinite(heads)):
        raise ValueError("sprinkler layout values must be finite")
    if np.any(heads[:, 2] <= 0):
        raise ValueError("sprinkler radius_m values must be positive")
    if np.any(heads[:, 4] <= 0) or np.any(heads[:, 4] > 360):
        raise ValueError("arc_width_deg values must be in (0, 360]")
    heads[:, 3] %= 360.0
    # Unlike optimizer-input validation, measured heads may legitimately sit
    # outside the lawn boundary, so do not enforce optimizer radius bounds or
    # lawn containment here.
    return heads


def read_observations(path):
    required = {"x_m", "y_m", "observed_depth_mm", "split"}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("observations CSV must contain x_m,y_m,observed_depth_mm,split columns")
        rows = list(reader)
    if len(rows) < 4:
        raise ValueError("at least four observations are required to keep calibration and holdout separate")
    parsed = []
    for index, row in enumerate(rows, start=1):
        try:
            x, y, depth = float(row["x_m"]), float(row["y_m"]), float(row["observed_depth_mm"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"observation row {index} has non-numeric coordinates or depth") from exc
        split = row["split"].strip().lower()
        if not all(math.isfinite(v) for v in (x, y, depth)) or depth < 0:
            raise ValueError(f"observation row {index} values must be finite and depth non-negative")
        if split not in {"calibration", "holdout"}:
            raise ValueError(f"observation row {index} split must be calibration or holdout")
        parsed.append({"observation_id": row.get("observation_id", "").strip() or str(index),
                       "x_m": x, "y_m": y, "observed_depth_mm": depth, "split": split})
    ids = [row["observation_id"] for row in parsed]
    if len(set(ids)) != len(ids):
        raise ValueError("observation_id values must be unique")
    if not any(row["split"] == "calibration" for row in parsed):
        raise ValueError("at least one calibration observation is required")
    if not any(row["split"] == "holdout" for row in parsed):
        raise ValueError("at least one independent holdout observation is required")
    return parsed


def metrics(observed, predicted):
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    residual = predicted - observed
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    mae = float(np.mean(np.abs(residual)))
    bias = float(np.mean(residual))
    denom = float(np.sum((observed - observed.mean()) ** 2))
    r2 = float(1.0 - np.sum(residual ** 2) / denom) if denom > 1e-12 else None
    return {"n": int(len(observed)), "rmse_mm": rmse, "mae_mm": mae,
            "bias_mm_prediction_minus_observed": bias, "r_squared": r2}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polygon-csv", required=True, help="surveyed lawn polygon CSV")
    parser.add_argument("--heads-csv", required=True, help="measured sprinkler layout CSV")
    parser.add_argument("--observations-csv", required=True, help="catch-can observations with explicit calibration/holdout split")
    parser.add_argument("--profile-csv", default=None, help="measured radial profile: radius_fraction,relative_rate")
    parser.add_argument("--radial-slope", type=float, default=sim.CFG["radial_slope"])
    parser.add_argument("--flow-lpm", type=float, default=None, help="measured flow per sprinkler in L/min; if omitted, predictions are relative")
    parser.add_argument("--duration-minutes", type=float, required=True, help="duration of catch-can collection in minutes")
    parser.add_argument("--cell-size", type=float, default=sim.CFG["cell"], help="recorded for provenance; point predictions are evaluated directly, not raster-interpolated")
    parser.add_argument("--out", default="out/catch-can-predictions.csv")
    parser.add_argument("--summary-json", default="out/catch-can-validation-summary.json")
    args = parser.parse_args(argv)

    if not math.isfinite(args.duration_minutes) or args.duration_minutes <= 0:
        parser.error("--duration-minutes must be finite and greater than zero")
    if not math.isfinite(args.cell_size) or args.cell_size <= 0:
        parser.error("--cell-size must be finite and greater than zero")
    if args.flow_lpm is not None and (not math.isfinite(args.flow_lpm) or args.flow_lpm <= 0):
        parser.error("--flow-lpm must be finite and greater than zero")
    if not math.isfinite(args.radial_slope) or args.radial_slope <= -1:
        parser.error("--radial-slope must be finite and greater than -1")

    try:
        polygon = sim.load_polygon_csv(args.polygon_csv)
        heads = read_heads(args.heads_csv)
        observations = read_observations(args.observations_csv)
        profile = load_radial_profile_csv(args.profile_csv) if args.profile_csv else None
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    from matplotlib.path import Path as PolygonPath
    lawn_path = PolygonPath(polygon)
    points = np.asarray([[row["x_m"], row["y_m"]] for row in observations], dtype=float)
    inside = lawn_path.contains_points(points, radius=1e-9)
    if not np.all(inside):
        outside_ids = [observations[i]["observation_id"] for i, is_inside in enumerate(inside) if not is_inside]
        parser.error("all catch-can points must lie inside the surveyed lawn polygon; outside IDs: " + ",".join(outside_ids))

    # Evaluate each observation at its actual coordinates; avoid raster interpolation.
    raw = np.zeros(len(observations), dtype=float)
    for head in heads:
        raw += head_field(points[:, 0], points[:, 1], head, profile, args.flow_lpm, args.radial_slope)
    if args.flow_lpm is not None:
        raw *= args.duration_minutes / 60.0

    calibration_idx = np.asarray([i for i, row in enumerate(observations) if row["split"] == "calibration"], dtype=int)
    holdout_idx = np.asarray([i for i, row in enumerate(observations) if row["split"] == "holdout"], dtype=int)
    observed = np.asarray([row["observed_depth_mm"] for row in observations], dtype=float)
    denom = float(np.dot(raw[calibration_idx], raw[calibration_idx]))
    if denom <= 1e-15:
        parser.error("model predicts zero at all calibration points; cannot fit a scale factor")
    scale = max(0.0, float(np.dot(raw[calibration_idx], observed[calibration_idx]) / denom))
    scaled = raw * scale

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "observation_id", "split", "x_m", "y_m", "observed_depth_mm",
            "raw_model_value", "raw_model_unit", "calibration_scale_factor",
            "predicted_depth_mm_after_calibration", "residual_mm_prediction_minus_observed",
        ])
        writer.writeheader()
        for i, row in enumerate(observations):
            writer.writerow({
                **row,
                "raw_model_value": f"{raw[i]:.8f}",
                "raw_model_unit": "mm_depth_for_duration" if args.flow_lpm is not None else "relative_model_units",
                "calibration_scale_factor": f"{scale:.8f}",
                "predicted_depth_mm_after_calibration": f"{scaled[i]:.8f}",
                "residual_mm_prediction_minus_observed": f"{scaled[i] - observed[i]:.8f}",
            })

    summary = {
        "schema_version": 1,
        "observations_csv": str(Path(args.observations_csv)),
        "polygon_csv": str(Path(args.polygon_csv)),
        "heads_csv": str(Path(args.heads_csv)),
        "profile_csv": str(Path(args.profile_csv)) if args.profile_csv else None,
        "duration_minutes": args.duration_minutes,
        "cell_size_m_recorded_not_used_for_point_interpolation": args.cell_size,
        "sprinkler_count": int(len(heads)),
        "flow_lpm_per_head": args.flow_lpm,
        "raw_prediction_unit": "mm_depth_for_duration" if args.flow_lpm is not None else "relative_model_units",
        "calibration_scale_factor_fit_on_calibration_rows_only": scale,
        "split_policy": "explicit CSV split column; holdout rows never used to fit scale",
        "calibration_metrics_after_scale_fit": metrics(observed[calibration_idx], scaled[calibration_idx]),
        "holdout_metrics_after_scale_fit": metrics(observed[holdout_idx], scaled[holdout_idx]),
        "raw_physical_input_calibration_metrics": (
            metrics(observed[calibration_idx], raw[calibration_idx]) if args.flow_lpm is not None else None
        ),
        "raw_physical_input_holdout_metrics": (
            metrics(observed[holdout_idx], raw[holdout_idx]) if args.flow_lpm is not None else None
        ),
        "warning": "This validates pointwise agreement only for this observed run. A fitted scale factor does not calibrate wind, drift, pressure variation, or future operating conditions and does not establish water savings.",
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote predictions: {output}")
    print(f"Wrote validation summary: {summary_path}")
    print(f"Calibration scale factor (fit on calibration rows only): {scale:.6g}")
    print("Calibration metrics: " + json.dumps(summary["calibration_metrics_after_scale_fit"]))
    print("Independent holdout metrics: " + json.dumps(summary["holdout_metrics_after_scale_fit"]))
    print("NOTE: a good fit on calibration rows is not evidence of generalization; judge the independent holdout metrics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
