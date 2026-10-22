from pathlib import Path
import json
import re
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "campos" / "campos_sim.py"
sys.path.insert(0, str(SRC.parent))
import campos_sim as sim  # noqa: E402


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
    assert metadata["config"]["seed"] == 7
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
    assert "AR_based_saving_metric_pct" in header
    assert not re.search(r"[\u3400-\u9fff]", header)


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
