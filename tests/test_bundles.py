from pathlib import Path
from zipfile import ZipFile
import io

import pytest

from campos.bundles import read_template_payloads, zip_bytes


EXPECTED_TEMPLATES = {
    "site_polygon_template.csv",
    "sprinkler_layout_template.csv",
    "protected_surface_template.csv",
    "field_catch_can_template.csv",
    "catch_can_profile_template.csv",
    "sprinkler_performance_template.csv",
}


def test_result_zip_contains_nonempty_named_artifacts():
    payload = zip_bytes({
        "run_metadata.json": b'{"seed":7}',
        "results_movable.csv": b"site,score\nA,0.5\n",
    })
    with ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {"run_metadata.json", "results_movable.csv"}
        assert all(archive.getinfo(name).file_size > 0 for name in archive.namelist())
        assert archive.testzip() is None
        assert archive.read("run_metadata.json") == b'{"seed":7}'


def test_starter_template_zip_contains_all_six_nonempty_csvs():
    template_dir = Path(__file__).resolve().parents[1] / "data" / "templates"
    payloads, missing = read_template_payloads(template_dir, sorted(EXPECTED_TEMPLATES)
    assert missing == []
    assert set(payloads) == EXPECTED_TEMPLATES
    assert all(payload.strip() for payload in payloads.values())

    with ZipFile(io.BytesIO(zip_bytes(payloads))) as archive:
        assert set(archive.namelist()) == EXPECTED_TEMPLATES
        assert archive.testzip() is None
        assert all(archive.read(name).strip() for name in EXPECTED_TEMPLATES)


def test_missing_template_is_reported_and_never_silently_invented(tmp_path):
    (tmp_path / "present.csv").write_text("x\n1\n", encoding="utf-8")
    payloads, missing = read_template_payloads(tmp_path, ["present.csv", "missing.csv"])
    assert list(payloads) == ["present.csv"]
    assert missing == ["missing.csv"]
    with ZipFile(io.BytesIO(zip_bytes(payloads))) as archive:
        assert archive.namelist() == ["present.csv"]
        assert "missing.csv" not in archive.namelist()


@pytest.mark.parametrize("unsafe", ["../escape.csv", "/tmp/escape.csv", "nested/file.csv", r"nested\\file.csv"])
def test_zip_rejects_unsafe_archive_names(unsafe):
    with pytest.raises(ValueError, match="unsafe ZIP artifact name"):
        zip_bytes({unsafe: b"nope"})
