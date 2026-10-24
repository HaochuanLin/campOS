import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "campos" / "field_observations.py"
SPEC = importlib.util.spec_from_file_location("field_observations_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
observations = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observations)


FIELDS = sorted(observations.REQUIRED_COLUMNS) + [
    "pressure_kpa", "wind_speed_m_s", "wind_direction_deg",
    "air_temperature_c", "exclusion_reason", "observation_datetime", "notes",
]


def row(**overrides):
    values = {
        "site_id": "site-1",
        "run_id": "run-1",
        "can_id": "can-1",
        "x_m": "1.5",
        "y_m": "2.5",
        "zone": "inside",
        "collection_duration_s": "60",
        "collected_volume_ml": "20",
        "measured_depth_mm": "",
        "container_opening_area_cm2": "4",
        "validity_flag": "valid",
        "split": "calibration",
    }
    values.update(overrides)
    return values


def write_csv(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_valid_observation_derives_depth_and_writes_summary(tmp_path):
    source = write_csv(tmp_path / "raw.csv", [row()])
    out_csv = tmp_path / "out" / "normalized.csv"
    out_json = tmp_path / "out" / "summary.json"

    summary = observations.validate_file(source, out_csv, out_json)

    with out_csv.open(newline="", encoding="utf-8") as handle:
        normalized = next(csv.DictReader(handle))
    assert float(normalized["measured_depth_mm_normalized"]) == pytest.approx(50.0)
    assert summary["row_count"] == 1
    assert summary["valid_flag_count"] == 1
    assert out_json.is_file()


def test_duplicate_observation_key_is_rejected(tmp_path):
    source = write_csv(tmp_path / "raw.csv", [row(), row(x_m="9")])
    with pytest.raises(ValueError, match="duplicate site_id/run_id/can_id"):
        observations.validate_file(source, tmp_path / "normalized.csv", tmp_path / "summary.json")


def test_same_run_cannot_mix_calibration_and_holdout(tmp_path):
    source = write_csv(
        tmp_path / "raw.csv",
        [row(can_id="can-1", split="calibration"), row(can_id="can-2", split="holdout")],
    )
    with pytest.raises(ValueError, match="mixes calibration and holdout"):
        observations.validate_file(source, tmp_path / "normalized.csv", tmp_path / "summary.json")


def test_raw_input_cannot_be_overwritten_by_output(tmp_path):
    source = write_csv(tmp_path / "raw.csv", [row()])
    with pytest.raises(ValueError, match="distinct paths"):
        observations.validate_file(source, source, tmp_path / "summary.json")


def test_nonpositive_collection_duration_is_rejected(tmp_path):
    source = write_csv(tmp_path / "raw.csv", [row(collection_duration_s="0")])
    with pytest.raises(ValueError, match="collection_duration_s must be > 0"):
        observations.validate_file(source, tmp_path / "normalized.csv", tmp_path / "summary.json")

def test_nonfinite_coordinate_is_rejected(tmp_path):
    source = write_csv(tmp_path / "raw.csv", [row(x_m="nan")])
    with pytest.raises(ValueError, match="x_m must be finite"):
        observations.validate_file(source, tmp_path / "normalized.csv", tmp_path / "summary.json")


def test_invalid_zone_label_is_rejected(tmp_path):
    source = write_csv(tmp_path / "raw.csv", [row(zone="road-ish")])
    with pytest.raises(ValueError, match="zone must be one of"):
        observations.validate_file(source, tmp_path / "normalized.csv", tmp_path / "summary.json")


def test_disagreement_between_measured_and_derived_depth_is_flagged(tmp_path):
    source = write_csv(
        tmp_path / "raw.csv",
        [row(measured_depth_mm="10", collected_volume_ml="20", container_opening_area_cm2="4")],
    )
    summary = observations.validate_file(source, tmp_path / "normalized.csv", tmp_path / "summary.json")
    assert summary["quality_warnings"]
    assert "differs from volume/area-derived depth" in summary["quality_warnings"][0]
