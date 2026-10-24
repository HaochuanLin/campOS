import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos.field_validation import load_heads, load_observations  # noqa: E402


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
