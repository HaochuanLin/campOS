#!/usr/bin/env python3
"""Experimental Gaussian-process residual correction for campOS field predictions.

Input is paired_predictions.csv from campos-field-evaluate. The Gaussian
process is trained only on calibration residuals (measured_mm - predicted_mm)
using spatial coordinates. Holdout measurements are used only for final
evaluation, never for fitting or kernel selection. This is an optional,
data-driven correction experiment, not a substitute for the physical model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
except ImportError as exc:  # pragma: no cover - environment-dependent
    raise SystemExit(
        "AI residual correction requires scikit-learn. Install with: "
        "python -m pip install -e '.[ai]'"
    ) from exc


def load_predictions(path: Path) -> list[dict[str, object]]:
    required = {"x_m", "y_m", "measured_mm", "predicted_mm", "split"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(
                "input CSV must be campos-field-evaluate paired_predictions.csv "
                "with x_m,y_m,measured_mm,predicted_mm,split columns"
            )
        rows = list(reader)
    parsed = []
    for line, row in enumerate(rows, start=2):
        try:
            x, y = float(row["x_m"]), float(row["y_m"])
            measured, predicted = float(row["measured_mm"]), float(row["predicted_mm"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"row {line}: coordinates and depths must be numeric") from exc
        split = row["split"].strip().lower()
        if not all(math.isfinite(v) for v in (x, y, measured, predicted)):
            raise ValueError(f"row {line}: all numeric values must be finite")
        if measured < 0 or predicted < 0:
            raise ValueError(f"row {line}: measured and predicted depths must be non-negative")
        if split not in {"calibration", "holdout"}:
            raise ValueError(f"row {line}: split must be calibration or holdout")
        parsed.append({
            **row,
            "x_m": x, "y_m": y,
            "measured_mm": measured, "predicted_mm": predicted, "split": split,
        })
    if not parsed:
        raise ValueError("input prediction CSV contains no rows")
    calibration = [r for r in parsed if r["split"] == "calibration"]
    holdout = [r for r in parsed if r["split"] == "holdout"]
    if len(calibration) < 8:
        raise ValueError(f"AI correction requires at least 8 calibration points; found {len(calibration)}")
    if len(holdout) < 3:
        raise ValueError(f"AI evaluation requires at least 3 independent holdout points; found {len(holdout)}")
    calibration_coords = {(r["x_m"], r["y_m"]) for r in calibration}
    holdout_coords = {(r["x_m"], r["y_m"]) for r in holdout}
    if len(calibration_coords) < 5:
        raise ValueError("AI correction requires at least 5 unique calibration coordinates")
    if len(holdout_coords) < 3:
        raise ValueError("AI evaluation requires at least 3 unique holdout coordinates")
    if not all(str(r.get("run_id", "")).strip() for r in parsed):
        raise ValueError("input CSV must include a non-empty run_id for run-level split validation")
    run_splits = {}
    for row in parsed:
        run_id = str(row["run_id"]).strip()
        previous = run_splits.setdefault(run_id, row["split"])
        if previous != row["split"]:
            raise ValueError(
                f"run_id {run_id!r} appears in both calibration and holdout; "
                "keep each complete run in one split"
            )
    return parsed


def regression_metrics(rows: list[dict[str, object]], prediction_key: str) -> dict[str, object]:
    observed = np.asarray([float(r["measured_mm"]) for r in rows])
    predicted = np.asarray([float(r[prediction_key]) for r in rows])
    residual = predicted - observed
    return {
        "n": int(len(rows)),
        "rmse_mm": float(np.sqrt(np.mean(residual ** 2))),
        "mae_mm": float(np.mean(np.abs(residual))),
        "bias_mm_predicted_minus_measured": float(np.mean(residual)),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions-csv", required=True, type=Path,
                        help="paired_predictions.csv from campos-field-evaluate")
    parser.add_argument("--outdir", type=Path, default=Path("out/ai-residual-correction"))
    parser.add_argument("--length-scale-m", type=float, default=5.0,
                        help="initial spatial correlation length in metres; tuned on calibration data only")
    parser.add_argument("--noise-level-mm", type=float, default=0.25,
                        help="initial observation-noise variance in mm^2")
    parser.add_argument(
        "--max-holdout-rmse-increase-mm", type=float, default=None,
        help="optional predeclared acceptance gate; fail if AI holdout RMSE exceeds baseline by more than this amount",
    )
    args = parser.parse_args(argv)
    if not math.isfinite(args.length_scale_m) or args.length_scale_m <= 0:
        parser.error("--length-scale-m must be finite and positive")
    if not math.isfinite(args.noise_level_mm) or args.noise_level_mm <= 0:
        parser.error("--noise-level-mm must be finite and positive")
    if args.max_holdout_rmse_increase_mm is not None and (
        not math.isfinite(args.max_holdout_rmse_increase_mm)
        or args.max_holdout_rmse_increase_mm < 0
    ):
        parser.error("--max-holdout-rmse-increase-mm must be finite and non-negative")

    try:
        rows = load_predictions(args.predictions_csv)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    calibration = [r for r in rows if r["split"] == "calibration"]
    holdout = [r for r in rows if r["split"] == "holdout"]
    x_train = np.asarray([[r["x_m"], r["y_m"]] for r in calibration], dtype=float)
    residual_train = np.asarray([
        float(r["measured_mm"]) - float(r["predicted_mm"]) for r in calibration
    ], dtype=float)
    x_all = np.asarray([[r["x_m"], r["y_m"]] for r in rows], dtype=float)

    kernel = (
        ConstantKernel(1.0, (1e-3, 1e3))
        * RBF(length_scale=args.length_scale_m, length_scale_bounds=(0.25, 100.0))
        + WhiteKernel(noise_level=args.noise_level_mm, noise_level_bounds=(1e-4, 100.0))
    )
    model = GaussianProcessRegressor(
        kernel=kernel, normalize_y=True, n_restarts_optimizer=0, random_state=0
    )
    model.fit(x_train, residual_train)
    residual_mean, residual_std = model.predict(x_all, return_std=True)

    for i, row in enumerate(rows):
        row["baseline_predicted_mm"] = float(row["predicted_mm"])
        row["ai_residual_correction_mm"] = float(residual_mean[i])
        row["ai_residual_std_mm"] = float(residual_std[i])
        row["ai_corrected_predicted_mm"] = max(
            0.0, float(row["predicted_mm"]) + float(residual_mean[i])
        )
        row["ai_corrected_95pct_lower_mm"] = max(
            0.0, float(row["predicted_mm"]) + float(residual_mean[i]) - 1.96 * float(residual_std[i])
        )
        row["ai_corrected_95pct_upper_mm"] = max(
            0.0, float(row["predicted_mm"]) + float(residual_mean[i]) + 1.96 * float(residual_std[i])
        )

    args.outdir.mkdir(parents=True, exist_ok=True)
    output_csv = args.outdir / "ai_corrected_predictions.csv"
    fields = list(rows[0].keys()) + [
        "baseline_predicted_mm", "ai_residual_correction_mm", "ai_residual_std_mm",
        "ai_corrected_predicted_mm", "ai_corrected_95pct_lower_mm", "ai_corrected_95pct_upper_mm",
    ]
    # Avoid duplicate headers if the input already contains any AI output fields.
    fields = list(dict.fromkeys(fields))
    with output_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    holdout_baseline = regression_metrics(holdout, "baseline_predicted_mm")
    holdout_corrected = regression_metrics(holdout, "ai_corrected_predicted_mm")
    holdout_interval_covered = [
        float(row["ai_corrected_95pct_lower_mm"])
        <= float(row["measured_mm"])
        <= float(row["ai_corrected_95pct_upper_mm"])
        for row in holdout
    ]
    holdout_interval_coverage = float(np.mean(holdout_interval_covered))
    holdout_mean_interval_width = float(np.mean([
        float(row["ai_corrected_95pct_upper_mm"])
        - float(row["ai_corrected_95pct_lower_mm"])
        for row in holdout
    ]))
    rmse_change = holdout_corrected["rmse_mm"] - holdout_baseline["rmse_mm"]
    gate_passed = (
        None if args.max_holdout_rmse_increase_mm is None
        else rmse_change <= args.max_holdout_rmse_increase_mm
    )
    summary = {
        "schema_version": 1,
        "method": "GaussianProcessRegressor with spatial RBF kernel and white-noise term",
        "training_features": ["x_m", "y_m"],
        "training_target": "measured_mm - physical_model_predicted_mm",
        "calibration_count": len(calibration),
        "holdout_count": len(holdout),
        "holdout_rows_used_for_training_or_kernel_selection": False,
        "kernel_after_calibration_fit": str(model.kernel_),
        "holdout_baseline_metrics": holdout_baseline,
        "holdout_ai_corrected_metrics": holdout_corrected,
        "holdout_ai_95pct_interval_empirical_coverage": holdout_interval_coverage,
        "holdout_ai_mean_95pct_interval_width_mm": holdout_mean_interval_width,
        "holdout_rmse_change_mm_corrected_minus_baseline": rmse_change,
        "predeclared_rmse_gate_threshold_mm": args.max_holdout_rmse_increase_mm,
        "predeclared_rmse_gate_passed": gate_passed,
        "input_predictions_csv_sha256": sha256(args.predictions_csv),
        "limitations": [
            "This is a spatial residual-correction experiment, not a learned sprinkler-physics model.",
            "The GP is fitted only on calibration rows; holdout metrics are reported for evaluation and must not be used repeatedly to tune settings.",
            "Spatially nearby observations may be correlated; a location holdout does not prove generalization to another run, day, sprinkler model, pressure, or weather condition.",
            "Prediction intervals are model-based uncertainty estimates, not guaranteed coverage intervals.",
            "Do not use corrected outputs for installation decisions until evaluated on a separately collected external dataset and compared against the uncorrected physical model.",
        ],
    }
    summary_path = args.outdir / "ai_residual_correction_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "predictions_csv": str(output_csv),
        "summary_json": str(summary_path),
        "calibration_n": len(calibration),
        "holdout_n": len(holdout),
        "holdout_baseline_rmse_mm": holdout_baseline["rmse_mm"],
        "holdout_ai_corrected_rmse_mm": holdout_corrected["rmse_mm"],
        "holdout_ai_95pct_interval_empirical_coverage": holdout_interval_coverage,
        "holdout_ai_mean_95pct_interval_width_mm": holdout_mean_interval_width,
        "holdout_rmse_change_mm_corrected_minus_baseline": summary["holdout_rmse_change_mm_corrected_minus_baseline"],
        "predeclared_rmse_gate_passed": gate_passed,
        "note": "AI correction is experimental; compare on independent data and do not tune against this holdout set.",
    }, indent=2))
    return 2 if gate_passed is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
