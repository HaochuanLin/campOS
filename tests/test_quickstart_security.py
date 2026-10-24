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
