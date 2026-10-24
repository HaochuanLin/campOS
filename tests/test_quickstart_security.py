import hashlib
import subprocess
import sys
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUICKSTART_PATH = ROOT / "src" / "campos" / "quickstart.py"
SPEC = importlib.util.spec_from_file_location("campos_quickstart", QUICKSTART_PATH)
assert SPEC is not None and SPEC.loader is not None
quickstart = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quickstart)


def test_quickstart_report_escapes_artifact_names_and_csv_cells(tmp_path):
    outdir = tmp_path / "report"
    outdir.mkdir()
    hostile_name = '<img src=x onerror="alert(1)">.csv'
    (outdir / hostile_name).write_text("fixture", encoding="utf-8")
    (outdir / "results_movable.csv").write_text(
        'site,area_m2,sprinkler_count,baseline_AR,optimized_AR,'
        'baseline_CU,optimized_CU,baseline_overspray_pct_of_own_water,'
        'optimized_overspray_pct_of_own_water,baseline_dry_area_pct,'
        'optimized_dry_area_pct\n'
        '"<script>alert(1)</script>",100,4,1.0,0.9,80,85,2,1,5,3\n',
        encoding="utf-8",
    )

    report = quickstart.build_index(
        outdir,
        {
            "finished_at_utc": "2026-10-24T00:00:00+00:00",
            "mode": "synthetic",
            "sites": ["A"],
            "quick": True,
        },
    )

    html = report.read_text(encoding="utf-8")
    assert '<img src=x onerror="alert(1)">.csv' not in html
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;.csv' in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_quickstart_report_omits_stale_files_not_in_manifest(tmp_path):
    outdir = tmp_path / "report"
    outdir.mkdir()
    (outdir / "fresh.csv").write_text("fresh output", encoding="utf-8")
    (outdir / "stale-private-results.csv").write_text("stale output", encoding="utf-8")
    (outdir / "results_movable.csv").write_text(
        "site,optimized_AR\nold-site,999\n", encoding="utf-8"
    )

    report = quickstart.build_index(
        outdir,
        {
            "finished_at_utc": "2026-10-24T00:00:00+00:00",
            "mode": "movable",
            "sites": ["A"],
            "quick": True,
            "artifact_checksums": {
                "fresh.csv": {"size_bytes": 12, "sha256": "0" * 64},
            },
        },
    )

    html = report.read_text(encoding="utf-8")
    assert "fresh.csv" in html
    assert "stale-private-results.csv" not in html
    assert "old-site" not in html
    assert "999" not in html



def test_quickstart_report_never_links_symlinked_artifacts(tmp_path):
    outdir = tmp_path / "report"
    outdir.mkdir()
    outside = tmp_path / "outside-secret.csv"
    outside.write_text("private fixture", encoding="utf-8")
    (outdir / "linked.csv").symlink_to(outside)
    report = quickstart.build_index(
        outdir,
        {
            "finished_at_utc": "2026-10-24T00:00:00+00:00",
            "mode": "movable",
            "sites": ["A"],
            "quick": True,
            "artifact_checksums": {
                "linked.csv": {"size_bytes": outside.stat().st_size, "sha256": "0" * 64},
            },
        },
    )

    html = report.read_text(encoding="utf-8")
    assert "linked.csv" not in html
    assert "private fixture" not in html



def test_artifact_checksums_include_only_regular_generated_files(tmp_path):
    (tmp_path / "results.csv").write_bytes(b"site,score\nA,1\n")
    (tmp_path / "index.html").write_text("report", encoding="utf-8")
    (tmp_path / "quickstart_manifest.json").write_text("{}", encoding="utf-8")
    outside = tmp_path.parent / "outside-checksum.csv"
    outside.write_bytes(b"outside")
    (tmp_path / "linked.csv").symlink_to(outside)

    checksums = quickstart.artifact_checksums(tmp_path)

    assert list(checksums) == ["results.csv"]
    assert checksums["results.csv"]["size_bytes"] == len(b"site,score\nA,1\n")
    assert checksums["results.csv"]["sha256"] == hashlib.sha256(b"site,score\nA,1\n").hexdigest()



def test_failed_quickstart_cannot_leave_old_success_markers(tmp_path, monkeypatch):
    outdir = tmp_path / "failed-run"
    outdir.mkdir()
    (outdir / "index.html").write_text("old successful report", encoding="utf-8")
    (outdir / "quickstart_manifest.json").write_text('{"status":"old"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["campos-start", "--outdir", str(outdir)])
    monkeypatch.setattr(quickstart.shutil, "which", lambda _: "/fake/campos-sim")

    def fail_simulation(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(quickstart.subprocess, "run", fail_simulation)

    exit_code = quickstart.main()

    assert exit_code == 2
    assert not (outdir / "index.html").exists()
    assert not (outdir / "quickstart_manifest.json").exists()
