import csv
from pathlib import Path
import json
import re
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "campos" / "campos_sim.py"
sys.path.insert(0, str(SRC.parent.parent))
from campos import campos_sim as sim  # noqa: E402


def test_fixed_position_optimizer_preserves_xy_coordinates():
    cfg = dict(sim.CFG)
    cfg["sa_iters"] = 8  # Test-only reduction; production defaults remain unchanged.
    cfg["restarts"] = 1
    site, heads0 = sim.get_site_and_baseline("test-fixed-regression", sim.site_rect(), cfg)
    heads1 = sim.optimize(site, heads0, cfg, cfg["seed"], fixed_xy=True)
    assert np.array_equal(heads1[:, :2], heads0[:, :2])


def test_baseline_cache_respects_geometry_and_configuration(monkeypatch):
    sim._SITE_CACHE.clear()
    monkeypatch.setattr(sim, "baseline_layout", lambda site, cfg: np.zeros((1, 5)))
    polygon = sim.site_rect()
    cfg_coarse = dict(sim.CFG, cell=1.0)
    cfg_fine = dict(sim.CFG, cell=2.0)

    try:
        site_coarse, _ = sim.get_site_and_baseline("test-cache-key", polygon, cfg_coarse)
        site_fine, _ = sim.get_site_and_baseline("test-cache-key", polygon, cfg_fine)
        assert site_coarse is not site_fine
        assert site_coarse.X.shape != site_fine.X.shape
    finally:
        sim._SITE_CACHE.clear()


def test_legacy_dry_metric_uses_configured_threshold():
    cfg = dict(sim.CFG, cell=2.0, margin=2.0)
    site = sim.Site(sim.site_rect(), cfg)
    total = np.zeros_like(site.X)
    lawn_values = np.where(np.arange(site.idx.size) % 2 == 0, 0.2, 1.0)
    total.ravel()[site.idx] = lawn_values

    cfg_low = dict(cfg, dry_thresh_frac=0.3)
    cfg_high = dict(cfg, dry_thresh_frac=0.5)
    _, low_threshold_metrics = sim.score(site, total, cfg_low)
    _, high_threshold_metrics = sim.score(site, total, cfg_high)

    assert low_threshold_metrics["dry"] == 0.0
    assert 0.4 < high_threshold_metrics["dry"] < 0.6


def test_dimensionless_metrics_are_invariant_to_positive_field_scaling():
    cfg = dict(sim.CFG, cell=1.0, margin=2.0)
    site = sim.Site(sim.site_rect(), cfg)
    rng = np.random.default_rng(1234)
    field = rng.uniform(0.05, 2.0, size=site.X.shape)
    _, metrics = sim.score(site, field, cfg)
    _, scaled_metrics = sim.score(site, field * 7.25, cfg)

    for key in ("AR", "overspray", "CU", "dry"):
        assert np.isclose(metrics[key], scaled_metrics[key], rtol=1e-12, atol=1e-12), key


def test_sprinkler_field_radial_profile_and_sector_mask():
    X = np.array([[0.0, 0.0, 0.0, 0.0]])
    Y = np.array([[0.0, 1.0, 2.0, -1.0]])
    # A 180-degree sector points upward from the positive x-axis.
    field = sim.head_field(X, Y, (0.0, 0.0, 2.0, 0.0, 180.0))

    assert field[0, 0] == 1.5
    assert np.isclose(field[0, 1], 1.125)
    assert np.isclose(field[0, 2], 0.75)
    assert field[0, 3] == 0.0


def test_pareto_archive_keeps_nondominated_points_and_removes_dominated_points():
    archive = sim.ParetoArchive(eps=0.0)
    heads = np.zeros((1, 5))
    archive.add(0.4, 0.3, heads)
    archive.add(0.3, 0.4, heads)
    assert len(archive.h) == 2

    archive.add(0.2, 0.2, heads)
    assert len(archive.h) == 1
    np.testing.assert_allclose(archive.f[0], [0.2, 0.2])


def test_movable_quick_mode_writes_outputs_and_run_metadata(tmp_path):
    outdir = tmp_path / "movable-output"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "campos_sim.py"),
            "--mode",
            "movable",
            "--quick",
            "--sites",
            "A",
            "--seed",
            "19",
            "--cell-size",
            "1.0",
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert (outdir / "results_movable.csv").is_file()
    assert (outdir / "layouts_movable.png").is_file()
    assert (outdir / "ranking_movable.png").is_file()

    metadata = json.loads((outdir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["config"]["seed"] == 19
    assert metadata["config"]["cell"] == 1.0
    assert metadata["arguments"]["seed"] == 19
    assert metadata["arguments"]["cell_size"] == 1.0
    assert metadata["arguments"]["quick"] is True
    assert metadata["selected_modes"] == ["movable"]
    assert metadata["selected_sites"] == ["A Rectangle"]
    assert metadata["python_version"]
    assert metadata["platform"]
    assert metadata["numpy_version"]
    assert metadata["matplotlib_version"]
    assert re.fullmatch(r"[0-9a-f]{64}", metadata["source_sha256"])

    with (outdir / "results_movable.csv").open(encoding="utf-8-sig", newline="") as fh:
        header = fh.readline()
    assert "AR_metric_improvement_pct" in header
    assert not re.search(r"[\u3400-\u9fff]", header)

    with (outdir / "results_movable.csv").open(encoding="utf-8-sig", newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["annual_water_saving_m3_not_estimated"] == ""
    assert row["annual_cost_saving_CNY_not_estimated"] == ""
    assert row["payback_years_not_estimated"] == ""
    assert row["retrofit_cost_CNY_placeholder"] != ""


def test_ar_improvement_does_not_generate_unjustified_economic_estimates():
    cfg = dict(sim.CFG, cell=2.0, margin=2.0, sa_iters=4, restarts=1)
    result = sim.run_site("test-economic-units", sim.site_rect(), cfg, fixed_xy=True)

    assert np.isfinite(result["water_saving"])
    assert np.isnan(result["annual_m3"])
    assert np.isnan(result["annual_cny"])
    assert np.isnan(result["payback"])
    assert np.isfinite(result["cost"])


def test_markdown_documentation_is_english_only():
    markdown_files = list(ROOT.rglob("*.md"))
    assert markdown_files
    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"[\u3400-\u9fff]", content), f"Non-English text found in {path.relative_to(ROOT)}"


def test_readme_relative_links_resolve():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme):
        if target.startswith(("https://", "http://", "#")):
            continue
        relative_path = target.split("#", 1)[0]
        if relative_path:
            assert (ROOT / relative_path).exists(), f"Broken README link: {target}"


def test_cli_rejects_unknown_site_id(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "campos_sim.py"),
            "--sites",
            "Z",
            "--quick",
            "--outdir",
            str(tmp_path / "invalid-site"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "unknown site ID" in completed.stderr
    assert not (tmp_path / "invalid-site" / "run_metadata.json").exists()


def test_cli_rejects_nonpositive_grid_cell_size(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "campos_sim.py"),
            "--cell-size",
            "0",
            "--quick",
            "--outdir",
            str(tmp_path / "invalid-cell"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "--cell-size must be a finite number greater than zero" in completed.stderr
    assert not (tmp_path / "invalid-cell" / "run_metadata.json").exists()


def test_installed_console_script_help():
    completed = subprocess.run(
        ["campos-sim", "--help"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert "--mode" in completed.stdout
    assert "--outdir" in completed.stdout
