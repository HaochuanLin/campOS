import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos.field_validation import (  # noqa: E402
    assess_holdout, load_heads, load_observations, validate_acceptance_thresholds,
)
from campos.field_observations import validate_file  # noqa: E402
from campos.field_report import build_report  # noqa: E402
from campos.observation_errors import evaluate  # noqa: E402


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def observation(can_id: str, run_id: str, split: str, **overrides) -> dict[str, object]:
    row = {
        "site_id": "site-a",
        "run_id": run_id,
        "can_id": can_id,
        "x_m": "1.0",
        "y_m": "2.0",
        "collection_duration_s": "600",
        "measured_depth_mm": "4.0",
        "collected_volume_ml": "",
        "container_opening_area_cm2": "",
        "validity_flag": "valid",
        "split": split,
        "zone": "inside",
    }
    row.update(overrides)
    return row


OBS_COLUMNS = list(observation("can-1", "run-1", "holdout").keys())
HEAD_COLUMNS = ["x_m", "y_m", "radius_m", "start_angle_deg", "arc_width_deg", "flow_lpm"]


def test_load_heads_rejects_nonfinite_geometry(tmp_path):
    path = write_csv(
        tmp_path / "heads.csv",
        HEAD_COLUMNS,
        [{"x_m": "nan", "y_m": "0", "radius_m": "5", "start_angle_deg": "0",
          "arc_width_deg": "360", "flow_lpm": "10"}],
    )
    with pytest.raises(ValueError, match="must be finite"):
        load_heads(path)


def test_load_heads_requires_positive_radius_and_flow(tmp_path):
    bad_radius = write_csv(
        tmp_path / "bad-radius.csv",
        HEAD_COLUMNS,
        [{"x_m": "0", "y_m": "0", "radius_m": "0", "start_angle_deg": "0",
          "arc_width_deg": "360", "flow_lpm": "10"}],
    )
    with pytest.raises(ValueError, match="radius_m must be > 0"):
        load_heads(bad_radius)

    bad_flow = write_csv(
        tmp_path / "bad-flow.csv",
        HEAD_COLUMNS,
        [{"x_m": "0", "y_m": "0", "radius_m": "5", "start_angle_deg": "0",
          "arc_width_deg": "360", "flow_lpm": "-1"}],
    )
    with pytest.raises(ValueError, match="flow_lpm must be > 0"):
        load_heads(bad_flow)


def test_load_observations_requires_at_least_two_valid_holdout_rows(tmp_path):
    path = write_csv(
        tmp_path / "observations.csv",
        OBS_COLUMNS,
        [
            observation("can-1", "cal-1", "calibration"),
            observation("can-2", "holdout-1", "holdout"),
        ],
    )
    with pytest.raises(ValueError, match="at least 2 valid holdout observations"):
        load_observations(path)


def test_load_observations_rejects_run_level_calibration_holdout_leakage(tmp_path):
    path = write_csv(
        tmp_path / "observations.csv",
        OBS_COLUMNS,
        [
            observation("can-1", "same-run", "calibration"),
            observation("can-2", "same-run", "holdout"),
            observation("can-3", "holdout-2", "holdout"),
        ],
    )
    with pytest.raises(ValueError, match="mixes calibration and holdout"):
        load_observations(path)


def test_load_observations_derives_depth_from_volume_and_area(tmp_path):
    path = write_csv(
        tmp_path / "observations.csv",
        OBS_COLUMNS,
        [
            observation("can-1", "holdout-1", "holdout", measured_depth_mm="",
                        collected_volume_ml="20", container_opening_area_cm2="10"),
            observation("can-2", "holdout-2", "holdout", measured_depth_mm="",
                        collected_volume_ml="30", container_opening_area_cm2="10"),
        ],
    )
    parsed = load_observations(path)
    assert [row["measured_mm"] for row in parsed] == [20.0, 30.0]



def field_record(can_id: str, validity_flag: str) -> dict[str, str]:
    return {
        "site_id": "site-a",
        "run_id": "run-1",
        "can_id": can_id,
        "x_m": "1",
        "y_m": "2",
        "zone": "inside",
        "collection_duration_s": "600",
        "collected_volume_ml": "",
        "measured_depth_mm": "",
        "container_opening_area_cm2": "",
        "validity_flag": validity_flag,
        "split": "calibration",
    }


def test_qc_preserves_excluded_observation_without_measurement(tmp_path):
    input_path = write_csv(
        tmp_path / "raw.csv",
        list(field_record("can-1", "exclude").keys()),
        [field_record("can-1", "exclude")],
    )
    output_csv = tmp_path / "out" / "normalized.csv"
    output_json = tmp_path / "out" / "summary.json"

    summary = validate_file(input_path, output_csv, output_json)

    assert summary["excluded_flag_count"] == 1
    with output_csv.open(newline="", encoding="utf-8") as handle:
        normalized = next(csv.DictReader(handle))
    assert normalized["measured_depth_mm_normalized"] == ""


def test_qc_still_requires_measurement_for_valid_observation(tmp_path):
    input_path = write_csv(
        tmp_path / "raw.csv",
        list(field_record("can-1", "valid").keys()),
        [field_record("can-1", "valid")],
    )
    with pytest.raises(ValueError, match="for valid observations"):
        validate_file(input_path, tmp_path / "normalized.csv", tmp_path / "summary.json")



def test_acceptance_thresholds_require_explicit_finite_nonnegative_limits():
    assert validate_acceptance_thresholds({"max_holdout_mae_mm": "2.5"}) == {
        "max_holdout_mae_mm": 2.5
    }
    for invalid in (
        {},
        {"max_holdout_mae_mm": -1},
        {"max_holdout_rmse_mm": float("nan")},
        {"universal_pass_score": 0.1},
    ):
        with pytest.raises(ValueError):
            validate_acceptance_thresholds(invalid)


def test_holdout_assessment_uses_user_limits_and_absolute_bias():
    metrics = {
        "holdout": {
            "mae_mm": 1.2,
            "rmse_mm": 1.8,
            "bias_mm_predicted_minus_measured": -0.4,
        }
    }
    thresholds = validate_acceptance_thresholds({
        "max_holdout_mae_mm": 1.5,
        "max_holdout_rmse_mm": 2.0,
        "max_absolute_bias_mm": 0.5,
    })
    assessment = assess_holdout(metrics, thresholds)
    assert assessment["status"] == "pass"
    assert all(check["passed"] for check in assessment["checks"])

    strict = validate_acceptance_thresholds({"max_absolute_bias_mm": 0.3})
    assert assess_holdout(metrics, strict)["status"] == "fail"



def test_acceptance_assessment_integrates_with_evaluation_metrics():
    evaluated = evaluate([
        {"measured_mm": 5.0, "predicted_mm": 5.5, "split": "holdout"},
        {"measured_mm": 4.0, "predicted_mm": 4.2, "split": "holdout"},
    ])
    thresholds = validate_acceptance_thresholds({"max_holdout_mae_mm": 1.0})
    assessment = assess_holdout(evaluated["metrics"], thresholds)
    assert assessment["status"] == "pass"
    assert assessment["checks"][0]["observed"] == pytest.approx(0.35)



def test_field_report_displays_optional_acceptance_assessment(tmp_path):
    report_path = tmp_path / "metrics.json"
    report_path.write_text(json.dumps({
        "status": "paired_spatial_predictions_and_descriptive_errors_generated",
        "metrics": {"metrics": {
            "all": {"n": 2, "bias_mm_predicted_minus_measured": 0.1,
                    "mae_mm": 0.2, "rmse_mm": 0.25, "max_absolute_error_mm": 0.3},
            "calibration": None,
            "holdout": {"n": 2, "bias_mm_predicted_minus_measured": 0.1,
                         "mae_mm": 0.2, "rmse_mm": 0.25, "max_absolute_error_mm": 0.3},
        }},
        "metrics_by_zone": {},
        "limitations": [],
        "acceptance_assessment": {
            "status": "pass",
            "note": "User-defined limits only.",
            "checks": [{"metric": "mae_mm", "observed": 0.2, "limit": 0.5, "passed": True}],
        },
    }), encoding="utf-8")

    markdown, html_report = build_report(report_path)

    assert "Pre-registered holdout acceptance assessment" in markdown
    assert "mae_mm" in markdown
    assert "Pre-registered holdout acceptance assessment" in html_report
    assert "User-defined limits only." in html_report
