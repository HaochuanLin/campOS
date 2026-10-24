#!/usr/bin/env python3
"""Descriptive error metrics for paired measured and predicted depths.

Metrics do not certify a model or prove that a user-supplied holdout split is independent.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def load_pairs(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"measured_mm", "predicted_mm", "split"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must contain measured_mm,predicted_mm,split columns")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV must contain at least one paired observation")
    parsed = []
    for line, row in enumerate(rows, start=2):
        try:
            measured, predicted = float(row["measured_mm"]), float(row["predicted_mm"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"line {line}: measured_mm and predicted_mm must be numeric") from exc
        split = str(row["split"]).strip().lower()
        if split not in {"calibration", "holdout"}:
            raise ValueError(f"line {line}: split must be calibration or holdout")
        if not np.isfinite(measured) or not np.isfinite(predicted):
            raise ValueError(f"line {line}: measurements and predictions must be finite")
        if measured < 0 or predicted < 0:
            raise ValueError(f"line {line}: depths must be non-negative")
        parsed.append({"measured_mm": measured, "predicted_mm": predicted, "split": split})
    return parsed


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    measured = np.asarray([row["measured_mm"] for row in rows], dtype=float)
    predicted = np.asarray([row["predicted_mm"] for row in rows], dtype=float)
    residual = predicted - measured
    result: dict[str, object] = {
        "n": int(len(rows)),
        "mean_measured_mm": float(np.mean(measured)),
        "mean_predicted_mm": float(np.mean(predicted)),
        "bias_mm_predicted_minus_measured": float(np.mean(residual)),
        "mae_mm": float(np.mean(np.abs(residual))),
        "rmse_mm": float(np.sqrt(np.mean(residual ** 2))),
        "max_absolute_error_mm": float(np.max(np.abs(residual))),
    }
    if len(rows) >= 2 and np.var(measured) > 0:
        result["r_squared_vs_mean_baseline"] = float(
            1.0 - np.sum(residual ** 2) / np.sum((measured - np.mean(measured)) ** 2)
        )
    else:
        result["r_squared_vs_mean_baseline"] = None
    result["interpretation"] = (
        "descriptive paired-error metrics only; not a pass/fail certification"
    )
    return result


def evaluate(rows: list[dict[str, object]], minimum_holdout: int = 2) -> dict[str, object]:
    calibration = [row for row in rows if row["split"] == "calibration"]
    holdout = [row for row in rows if row["split"] == "holdout"]
    if len(holdout) < minimum_holdout:
        raise ValueError(
            f"at least {minimum_holdout} independent holdout rows are required; found {len(holdout)}"
        )
    return {
        "schema_version": 1,
        "units": "mm",
        "row_count": len(rows),
        "split_counts": {"calibration": len(calibration), "holdout": len(holdout)},
        "metrics": {
            "all": summarize(rows),
            "calibration": summarize(calibration) if calibration else None,
            "holdout": summarize(holdout),
        },
        "limitations": [
            "The input predictions must be generated before inspecting holdout observations.",
            "A split label is user-supplied and does not prove independence or prevent leakage.",
            "These metrics do not calibrate the model or establish field validity.",
            "No acceptance threshold is imposed; thresholds must be defined before evaluating holdout data.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="paired observation CSV")
    parser.add_argument("--out", required=True, type=Path, help="JSON metrics output")
    parser.add_argument("--minimum-holdout", type=int, default=2)
    args = parser.parse_args()
    if args.minimum_holdout < 2:
        parser.error("--minimum-holdout must be at least 2")
    report = evaluate(load_pairs(args.input), args.minimum_holdout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}; holdout n={report['split_counts']['holdout']}, "
          f"holdout RMSE={report['metrics']['holdout']['rmse_mm']:.4g} mm")


if __name__ == "__main__":
    main()
