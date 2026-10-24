#!/usr/bin/env python3
"""Predict catch-can depths at exact observation coordinates and score holdout data.

This is a model-to-observation workflow, not a claim that the model is valid.
Measured flow can be supplied per head in the layout CSV, with a command-line
fallback for heads without a value. Predictions assume the selected radial
profile, steady operation, and no wind/drift/pressure loss.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np

from .campos_sim import load_polygon_csv, load_radial_profile_csv
from .model import head_field
from .observation_errors import evaluate, summarize


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


def load_heads(path: Path) -> tuple[np.ndarray, list[float | None]]:
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
    flows: list[float | None] = []
    for line, row in enumerate(rows, start=2):
        raw_flow = str(row.get("flow_lpm", "")).strip()
        flow = None if not raw_flow else finite_float(raw_flow, "flow_lpm", line)
        if flow is not None and flow <= 0:
            raise ValueError(f"row {line}: flow_lpm must be > 0 when supplied")
        flows.append(flow)
    return heads, flows


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
        zone = str(row.get("zone", "unknown")).strip().lower() or "unknown"
        if zone not in {"inside", "outside", "boundary", "unknown"}:
            raise ValueError(f"row {line}: zone must be inside, outside, boundary, or unknown")
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
            "zone": zone,
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
    flow_lpm: float | None,
    head_flows: list[float | None],
    radial_slope: float,
    radial_profile: np.ndarray | None,
) -> list[dict[str, object]]:
    if flow_lpm is not None and (not math.isfinite(flow_lpm) or flow_lpm <= 0):
        raise ValueError("flow_lpm must be finite and > 0 when supplied")
    effective_flows = [measured if measured is not None else flow_lpm for measured in head_flows]
    if any(value is None for value in effective_flows):
        raise ValueError(
            "every head needs a positive measured flow_lpm in heads CSV or the --flow-lpm fallback"
        )
    if any(not math.isfinite(float(value)) or float(value) <= 0 for value in effective_flows):
        raise ValueError("each per-head flow must be finite and > 0")
    if not math.isfinite(radial_slope) or radial_slope <= -1:
        raise ValueError("radial_slope must be finite and > -1")
    from matplotlib.path import Path as PolygonPath
    inside = PolygonPath(polygon)
    output = []
    for obs in observations:
        x, y = float(obs["x_m"]), float(obs["y_m"])
        predicted_rate = 0.0
        for head, head_flow in zip(heads, effective_flows):
            predicted_rate += float(head_field(
                np.asarray([[x]]), np.asarray([[y]]), head,
                radial_profile=radial_profile, flow_lpm=float(head_flow),
                radial_slope=radial_slope,
            )[0, 0])
        predicted_depth = predicted_rate * float(obs["duration_s"]) / 3600.0
        measured = float(obs["measured_mm"])
        inside_site = bool(inside.contains_point((x, y)))
        zone = str(obs["zone"])
        zone_mismatch = (zone == "inside" and not inside_site) or (zone == "outside" and inside_site)
        output.append({
            "site_id": obs["site_id"], "run_id": obs["run_id"], "can_id": obs["can_id"],
            "x_m": x, "y_m": y, "zone": obs["zone"],
            "point_inside_polygon": inside_site,
            "zone_geometry_mismatch": zone_mismatch,
            "collection_duration_s": obs["duration_s"],
            "measured_mm": measured, "predicted_mm": predicted_depth,
            "residual_predicted_minus_measured_mm": predicted_depth - measured,
            "absolute_error_mm": abs(predicted_depth - measured),
            "split": obs["split"],
        })
    return output


def validate_acceptance_thresholds(
    thresholds: dict[str, object],
) -> dict[str, float]:
    """Validate explicit, pre-registered holdout acceptance limits.

    Supported keys are max_holdout_mae_mm, max_holdout_rmse_mm, and
    max_absolute_bias_mm. Values must be finite and non-negative.
    """
    allowed = {
        "max_holdout_mae_mm",
        "max_holdout_rmse_mm",
        "max_absolute_bias_mm",
    }
    unknown = set(thresholds) - allowed
    if unknown:
        raise ValueError("unknown acceptance threshold(s): " + ", ".join(sorted(unknown)))
    normalized: dict[str, float] = {}
    for key, raw_value in thresholds.items():
        if isinstance(raw_value, bool):
            raise ValueError(f"{key} must be a finite non-negative number, not a boolean")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a finite non-negative number") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be a finite non-negative number")
        normalized[key] = value
    if not normalized:
        raise ValueError("at least one pre-registered acceptance threshold is required")
    return normalized


def assess_holdout(metrics: dict[str, object], thresholds: dict[str, float]) -> dict[str, object]:
    """Compare holdout metrics with user-defined limits without inventing defaults."""
    holdout = metrics.get("holdout")
    if not isinstance(holdout, dict):
        raise ValueError("holdout metrics are required to assess acceptance")
    metric_map = {
        "max_holdout_mae_mm": "mae_mm",
        "max_holdout_rmse_mm": "rmse_mm",
        "max_absolute_bias_mm": "bias_mm_predicted_minus_measured",
    }
    checks = []
    for threshold_key, metric_key in metric_map.items():
        if threshold_key not in thresholds:
            continue
        raw = holdout.get(metric_key)
        if raw is None:
            raise ValueError(f"holdout metric {metric_key} is unavailable")
        try:
            observed = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"holdout metric {metric_key} is not numeric") from exc
        if not math.isfinite(observed):
            raise ValueError(f"holdout metric {metric_key} must be finite")
        limit = thresholds[threshold_key]
        value = abs(observed) if threshold_key == "max_absolute_bias_mm" else observed
        checks.append({
            "metric": metric_key,
            "observed": value,
            "limit": limit,
            "passed": value <= limit,
        })
    return {
        "status": "pass" if all(item["passed"] for item in checks) else "fail",
        "checks": checks,
        "note": "User-defined limits only; this result is not a certification of model validity.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polygon-csv", required=True, type=Path, help="surveyed polygon x_m,y_m")
    parser.add_argument("--heads-csv", required=True, type=Path, help="actual sprinkler layout CSV")
    parser.add_argument("--observations", required=True, type=Path, help="filled field catch-can CSV")
    parser.add_argument("--flow-lpm", type=float, default=None,
                        help="fallback measured flow per head; overridden by heads CSV flow_lpm values")
    parser.add_argument("--radial-slope", type=float, default=0.0,
                        help="illustrative radial profile parameter; default 0 is uniform")
    parser.add_argument("--profile-csv", type=Path, default=None,
                        help="optional measured relative radial profile (takes precedence over slope)")
    parser.add_argument("--acceptance-thresholds-json", type=Path, default=None,
                        help="optional pre-registered JSON limits: max_holdout_mae_mm, max_holdout_rmse_mm, max_absolute_bias_mm")
    parser.add_argument(
        "--fail-on-zone-geometry-mismatch",
        action="store_true",
        help="return a nonzero exit code if inside/outside observation labels contradict the lawn polygon",
    )
    parser.add_argument("--outdir", type=Path, default=Path("out/field-evaluation"))
    args = parser.parse_args()
    acceptance_assessment = None

    try:
        polygon = load_polygon_csv(args.polygon_csv)
        heads, head_flows = load_heads(args.heads_csv)
        observations = load_observations(args.observations)
        profile = load_radial_profile_csv(args.profile_csv) if args.profile_csv else None
        predictions = predict(polygon, heads, observations, args.flow_lpm, head_flows, args.radial_slope, profile)
        metric_input = [
            {"measured_mm": row["measured_mm"], "predicted_mm": row["predicted_mm"], "split": row["split"]}
            for row in predictions
        ]
        metrics = evaluate(metric_input)
        metrics_by_zone = {}
        for zone in sorted({str(row["zone"]) for row in predictions}):
            zone_rows = [
                {"measured_mm": row["measured_mm"], "predicted_mm": row["predicted_mm"], "split": row["split"]}
                for row in predictions if str(row["zone"]) == zone
            ]
            zone_holdout = [row for row in zone_rows if row["split"] == "holdout"]
            metrics_by_zone[zone] = {
                "n": len(zone_rows),
                "holdout_n": len(zone_holdout),
                "all": summarize(zone_rows) if zone_rows else None,
                "holdout": summarize(zone_holdout) if zone_holdout else None,
            }
        if args.acceptance_thresholds_json is not None:
            raw_thresholds = json.loads(args.acceptance_thresholds_json.read_text(encoding="utf-8"))
            if not isinstance(raw_thresholds, dict):
                raise ValueError("acceptance thresholds JSON must be an object")
            thresholds = validate_acceptance_thresholds(raw_thresholds)
            acceptance_assessment = assess_holdout(metrics["metrics"], thresholds)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.outdir.mkdir(parents=True, exist_ok=True)
    prediction_path = args.outdir / "paired_predictions.csv"
    with prediction_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0].keys()))
        writer.writeheader()
        writer.writerows(predictions)

    report = {
        "schema_version": 1,
        "status": (
            "acceptance_thresholds_failed"
            if acceptance_assessment is not None and acceptance_assessment["status"] == "fail"
            else "zone_geometry_gate_failed"
            if args.fail_on_zone_geometry_mismatch and any(row["zone_geometry_mismatch"] for row in predictions)
            else "acceptance_thresholds_passed"
            if acceptance_assessment is not None
            else "paired_spatial_predictions_and_descriptive_errors_generated"
        ),
        "zone_geometry_gate": {
            "enabled": args.fail_on_zone_geometry_mismatch,
            "mismatch_count": sum(bool(row["zone_geometry_mismatch"]) for row in predictions),
            "passed": (
                not any(row["zone_geometry_mismatch"] for row in predictions)
                if args.fail_on_zone_geometry_mismatch else None
            ),
        },
        "scope": "model-to-catch-can comparison at exact supplied coordinates",
        "n_sprinkler_heads": int(len(heads)),
        "n_valid_observations": len(predictions),
        "zone_geometry_mismatch_count": sum(bool(row["zone_geometry_mismatch"]) for row in predictions),
        "zone_geometry_mismatch_can_ids": [row["can_id"] for row in predictions if row["zone_geometry_mismatch"]],
        "flow_lpm_per_head": [measured if measured is not None else args.flow_lpm for measured in head_flows],
        "flow_source": "per-head heads CSV values with CLI fallback where blank",
        "radial_slope": args.radial_slope if profile is None else None,
        "radial_profile_csv_sha256": sha256(args.profile_csv) if args.profile_csv else None,
        "input_sha256": {
            "polygon_csv": sha256(args.polygon_csv),
            "heads_csv": sha256(args.heads_csv),
            "observations_csv": sha256(args.observations),
        },
        "software": {
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "source_sha256": {
                "field_validation.py": sha256(Path(__file__)),
                "model.py": sha256(Path(__file__).with_name("model.py")),
                "observation_errors.py": sha256(Path(__file__).with_name("observation_errors.py")),
            },
        },
        "metrics": metrics,
        "metrics_by_zone": metrics_by_zone,
        "acceptance_thresholds_json_sha256": (
            sha256(args.acceptance_thresholds_json)
            if args.acceptance_thresholds_json is not None else None
        ),
        "acceptance_assessment": acceptance_assessment,
        "limitations": [
            "Each head uses its supplied flow_lpm, or the CLI fallback if the per-head value is blank; flows must be measured at documented operating conditions.",
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
        "warning": (
            "pre-registered acceptance thresholds failed; inspect the written metrics and predictions"
            if acceptance_assessment is not None and acceptance_assessment["status"] == "fail"
            else "zone/polygon labels conflict and the strict geometry gate failed; inspect the written metrics and predictions"
            if args.fail_on_zone_geometry_mismatch and any(row["zone_geometry_mismatch"] for row in predictions)
            else "descriptive evaluation only; thresholds are user-defined and do not certify physical validity"
        ),
    }, indent=2))
    # Preserve outputs for audit, but make a failed pre-registered gate fail CI/shell automation.
    acceptance_failed = acceptance_assessment is not None and acceptance_assessment["status"] == "fail"
    zone_gate_failed = args.fail_on_zone_geometry_mismatch and any(
        row["zone_geometry_mismatch"] for row in predictions
    )
    return 2 if acceptance_failed or zone_gate_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
