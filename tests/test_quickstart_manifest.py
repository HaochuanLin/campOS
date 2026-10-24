import hashlib
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
QUICKSTART_PATH = ROOT / "src" / "campos" / "quickstart.py"
SPEC = importlib.util.spec_from_file_location("campos_quickstart_manifest", QUICKSTART_PATH)
assert SPEC is not None and SPEC.loader is not None
quickstart = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quickstart)


def test_artifact_checksums_are_stable_and_exclude_self_referential_files(tmp_path):
    csv_file = tmp_path / "results.csv"
    csv_file.write_bytes(b"site,score\nA,0.5\n")
    (tmp_path / "index.html").write_text("report", encoding="utf-8")
    (tmp_path / "quickstart_manifest.json").write_text("{}", encoding="utf-8")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("external", encoding="utf-8")
    (tmp_path / "linked.txt").symlink_to(outside)

    first = quickstart.artifact_checksums(tmp_path)
    second = quickstart.artifact_checksums(tmp_path)

    assert first == second
    assert list(first) == ["results.csv"]
    assert first["results.csv"]["size_bytes"] == csv_file.stat().st_size
    assert first["results.csv"]["sha256"] == hashlib.sha256(csv_file.read_bytes()).hexdigest()


def test_quickstart_records_and_forwards_reproducibility_settings(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(quickstart.shutil, "which", lambda _name: "/fake/campos-sim")

    def fake_run(command, check):
        assert check is True
        outdir = Path(command[command.index("--outdir") + 1])
        mode = command[command.index("--mode") + 1]
        assert command[command.index("--seed") + 1] == "19"
        assert command[command.index("--cell-size") + 1] == "0.25"
        (outdir / "run_metadata.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")
        (outdir / f"results_{mode}.csv").write_text(
            "site,baseline_AR,optimized_AR\nA,2,1.5\n", encoding="utf-8"
        )

    monkeypatch.setattr(quickstart.subprocess, "run", fake_run)
    assert quickstart.main([
        "--outdir", str(tmp_path), "--seed", "19", "--cell-size", "0.25"
    ]) == 0

    manifest = json.loads((tmp_path / "quickstart_manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 19
    assert manifest["cell_size_m"] == 0.25
    assert all("--seed" in command and "--cell-size" in command for command in manifest["commands"])
    assert "results_fixed.csv" in manifest["artifact_checksums"]
    assert "results_movable.csv" in manifest["artifact_checksums"]
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Seed:" in page and "19" in page
    assert "Grid:" in page and "0.25 m" in page


def test_quickstart_rejects_invalid_seed_and_grid_size(capsys):
    with pytest.raises(SystemExit) as seed_error:
        quickstart.main(["--seed", "-1"])
    assert seed_error.value.code == 2
    assert "--seed must be a non-negative integer" in capsys.readouterr().err

    for invalid_cell_size in ("0", "-0.5", "nan", "inf"):
        with pytest.raises(SystemExit) as cell_error:
            quickstart.main(["--cell-size", invalid_cell_size])
        assert cell_error.value.code == 2
        assert "--cell-size must be finite and greater than zero" in capsys.readouterr().err


def test_quickstart_excludes_stale_outputs_from_report_and_manifest(tmp_path, monkeypatch):
    import json

    stale_movable = tmp_path / "results_movable.csv"
    stale_movable.write_text("site,baseline_AR,optimized_AR\nOLD,9,8\n", encoding="utf-8")
    stale_plot = tmp_path / "old_plot.png"
    stale_plot.write_bytes(b"stale plot")
    monkeypatch.setattr(quickstart.shutil, "which", lambda _name: "/fake/campos-sim")

    def fake_run(command, check):
        outdir = Path(command[command.index("--outdir") + 1])
        (outdir / "run_metadata.json").write_text('{"mode":"fixed"}', encoding="utf-8")
        (outdir / "results_fixed.csv").write_text(
            "site,baseline_AR,optimized_AR\nA,2,1.5\n", encoding="utf-8"
        )

    monkeypatch.setattr(quickstart.subprocess, "run", fake_run)
    assert quickstart.main(["--mode", "fixed", "--outdir", str(tmp_path)]) == 0

    manifest = json.loads((tmp_path / "quickstart_manifest.json").read_text(encoding="utf-8"))
    assert "results_fixed.csv" in manifest["artifact_checksums"]
    assert "results_movable.csv" not in manifest["artifact_checksums"]
    assert "old_plot.png" not in manifest["artifact_checksums"]
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "results_fixed.csv" in page
    assert "results_movable.csv" not in page
    assert "old_plot.png" not in page
