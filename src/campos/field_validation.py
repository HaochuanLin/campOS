#!/usr/bin/env python3
"""Predict catch-can depths at exact observation coordinates and score holdout data.

This is a model-to-observation workflow, not a claim that the model is valid.
All heads use the same supplied measured flow rate. Predictions assume the
selected radial profile, steady operation, and no wind/drift/pressure loss.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .campos_sim import load_polygon_csv, load_radial_profile_csv
from .model import head_field
from .observation_errors import evaluate


HEAD_COLUMNS = ("x_m", "y_m", "radius_m", "start_angle_deg", "arc_width_deg")
OBS_COLUMNS = {
    "site_id", "run_id", "can_id", "x_m", "y_m", "collection_duration_s",
    "validity_flag", "split",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite_float(value: str, name: str, line: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {line}: {name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"row {line}: {name} must be finite")
    return result


def load_heads(path: Path) -> np.ndarray:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(HEAD_COLUMNS).issubset(reader.fieldnames):
            raise ValueError("heads CSV must contain " + ",".join(HEAD_COLUMNS))
        rows = list(reader)
    if not rows:
        raise ValueError("heads CSV must contain at least one sprinkler")
    heads = np.asarray([
        [finite_float(row[column], column, line) for column in HEAD_COLUMNS]
        for line, row in enumerate(rows, start=2)
    ], dtype=float)
    if not np.all(np.isfinite(heads)):
        raise ValueError("head values must be finite")
    if np.any(heads[:, 2] <= 0):
        raise ValueError("radius_m must be > 0")
    if np.any(heads[:, 4] <= 0) or np.any(heads[:, 4] > 360):
        raise ValueError("arc_width_deg must be in (0, 360]")
    heads[:, 3] %= 360.0
    return heads


def load_observations(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not OBS_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(
                "observations CSV must include site_id,run_id,can_id,x_m,y_m,"
                "collection_duration_s,validity_flag,split; fill the field template first"
            )
        rows = list(reader)
    if not rows:
        raise ValueError("observations CSV has no rows")
    parsed = []
    seen = set()
    run_splits = {}
    for line, row in enumerate(rows, start=2):
        site_id, run_id, can_id = (str(row.get(k, "")).strip() for k in ("site_id", "run_id", "can_id"))
        if not site_id or not run_id or not can_id:
            raise ValueError(f"row {line}: site_id, run_id, and can_id are required")
        key = (site_id, run_id, can_id)
        if key in seen:
            raise ValueError(f"row {line}: duplicate site_id/run_id/can_id {key}")
        seen.add(key)
        split = str(row.get("split", "")).strip().lower()
        if split not in {"calibration", "holdout"}:
            raise ValueError(f"row {line}: split must be calibration or holdout")
        run_key = (site_id, run_id)
        if run_key in run_splits and run_splits[run_key] != split:
            raise ValueError(
                f"row {line}: run {run_key} mixes calibration and holdout; keep an entire run in one split"
            )
        run_splits[run_key] = split
        flag = str(row.get("validity_flag", "")).strip().lower()
        if flag not in {"valid", "exclude", "unknown"}:
            raise ValueError(f"row {line}: validity_flag must be valid, exclude, or unknown")
        if flag != "valid":
            continue
        x = finite_float(row.get("x_m", ""), "x_m", line)
        y = finite_float(row.get("y_m", ""), "y_m", line)
        duration = finite_float(row.get("collection_duration_s", ""), "collection_duration_s", line)
        if duration <= 0:
            raise ValueError(f"row {line}: collection_duration_s must be > 0")
        measured_raw = str(row.get("measured_depth_mm", "")).strip()
        if measured_raw:
            measured = finite_float(measured_raw, "measured_depth_mm", line)
        else:
            volume_raw = str(row.get("collected_volume_ml", "")).strip()
            area_raw = str(row.get("container_opening_area_cm2", "")).strip()
            if not volume_raw or not area_raw:
                raise ValueError(
                    f"row {line}: valid rows need measured_depth_mm or both "
                    "collected_volume_ml and container_opening_area_cm2"
                )
            volume = finite_float(volume_raw, "collected_volume_ml", line)
            area = finite_float(area_raw, "container_opening_area_cm2", line)
            if volume < 0 or area <= 0:
                raise ValueError(f"row {line}: volume must be >= 0 and opening area > 0")
            measured = volume / area * 10.0
        if measured < 0:
            raise ValueError(f"row {line}: measured depth must be >= 0")
        parsed.append({
            "site_id": site_id, "run_id": run_id, "can_id": can_id,
            "x_m": x, "y_m": y, "duration_s": duration,
            "measured_mm": measured, "split": split,
            "zone": str(row.get("zone", "unknown")).strip().lower() or "unknown",
        })
    if not parsed:
        raise ValueError("no rows with validity_flag=valid; mark usable measurements as valid")
    holdout_n = sum(row["split"] == "holdout" for row in parsed)
    if holdout_n < 2:
        raise ValueError(f"at least 2 valid holdout observations are required; found {holdout_n}")
    return parsed


def predict(
    polygon: np.ndarray,
    heads: np.ndarray,
    observations: list[dict[str, object]],
    flow_lpm: float,
    radial_slope: float,
    radial_profile: np.ndarray | None,
) -> list[dict[str, object]]:
    if not math.isfinite(flow_lpm) or flow_lpm <= 0:
        raise ValueError("flow_lpm must be finite and > 0; use a measured operating flow")
    if not math.isfinite(radial_slope) or radial_slope <= -1:
        raise ValueError("radial_slope must be finite and > -1")
    from matplotlib.path import Path as PolygonPath
    inside = PolygonPath(polygon)
    output = []
    for obs in observations:
        x, y = float(obs["x_m"]), float(obs["y_m"])
        predicted_rate = 0.0
        for head in heads:
            predicted_rate += float(head_field(
                np.asarray([[x]]), np.asarray([[y]]), head,
                radial_profile=radial_profile, flow_lpm=flow_lpm,
                radial_slope=radial_slope,
            )[0, 0])
        predicted_depth = predicted_rate * float(obs["duration_s"]) / 3600.0
        measured = float(obs["measured_mm"])
        output.append({
            "site_id": obs["site_id"], "run_id": obs["run_id"], "can_id": obs["can_id"],
            "x_m": x, "y_m": y, "zone": obs["zone"],
            "point_inside_polygon": bool(inside.contains_point((x, y))),
            "collection_duration_s": obs["duration_s"],
            "measured_mm": measured, "predicted_mm": predicted_depth,
            "residual_predicted_minus_measured_mm": predicted_depth - measured,
            "absolute_error_mm": abs(predicted_depth - measured),
            "split": obs["split"],
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polygon-csv", required=True, type=Path, help="surveyed polygon x_m,y_m")
    parser.add_argument("--heads-csv", required=True, type=Path, help="actual sprinkler layout CSV")
    parser.add_argument("--observations", required=True, type=Path, help="filled field catch-can CSV")
    parser.add_argument("--flow-lpm", required=True, type=float,
                        help="measured flow per head at the documented operating condition")
    parser.add_argument("--radial-slope", type=float, default=0.0,
                        help="illustrative radial profile parameter; default 0 is uniform")
    parser.add_argument("--profile-csv", type=Path, default=None,
                        help="optional measured relative radial profile (takes precedence over slope)")
    parser.add_argument("--outdir", type=Path, default=Path("out/field-evaluation"))
    args = parser.parse_args()

    try:
        polygon = load_polygon_csv(args.polygon_csv)
        heads = load_heads(args.heads_csv)
        observations = load_observations(args.observations)
        profile = load_radial_profile_csv(args.profile_csv) if args.profile_csv else None
        predictions = predict(polygon, heads, observations, args.flow_lpm, args.radial_slope, profile)
        metric_input = [
            {"measured_mm": row["measured_mm"], "predicted_mm": row["predicted_mm"], "split": row["split"]}
            for row in predictions
        ]
        metrics = evaluate(metric_input)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    args.outdir.mkdir(parents=True, exist_ok=True)
    prediction_path = args.outdir / "paired_predictions.csv"
    with prediction_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0].keys()))
        writer.writeheader()
        writer.writerows(predictions)

    report = {
        "schema_version": 1,
        "status": "paired_spatial_predictions_and_descriptive_errors_generated",
        "scope": "model-to-catch-can comparison at exact supplied coordinates",
        "n_sprinkler_heads": int(len(heads)),
        "n_valid_observations": len(predictions),
        "flow_lpm_per_head": args.flow_lpm,
        "radial_slope": args.radial_slope if profile is None else None,
        "radial_profile_csv_sha256": sha256(args.profile_csv) if args.profile_csv else None,
        "input_sha256": {
            "polygon_csv": sha256(args.polygon_csv),
            "heads_csv": sha256(args.heads_csv),
            "observations_csv": sha256(args.observations),
        },
        "metrics": metrics,
        "limitations": [
            "Flow is assumed identical for all heads and must be measured at the documented operating condition.",
            "Predictions assume steady operation and omit wind, drift, evaporation, pressure loss, and network hydraulics.",
            "The default uniform radial profile is a null-model assumption, not calibrated sprinkler physics.",
            "Holdout independence depends on the field-study design; this tool enforces run-level split consistency but cannot prove independence.",
            "No universal pass threshold is imposed; pre-register a justified threshold before inspecting holdout errors.",
            "These results do not establish water savings, plant health, or general validity beyond the tested equipment and conditions.",
        ],
        "prediction_csv": prediction_path.name,
    }
    metrics_path = args.outdir / "field_evaluation_metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "predictions_csv": str(prediction_path),
        "metrics_json": str(metrics_path),
        "n": len(predictions),
        "holdout_n": metrics["split_counts"]["holdout"],
        "holdout_mae_mm": metrics["metrics"]["holdout"]["mae_mm"],
        "holdout_rmse_mm": metrics["metrics"]["holdout"]["rmse_mm"],
        "warning": "descriptive evaluation only; no pass/fail certification",
    }, indent=2))


if __name__ == "__main__":
    main()
