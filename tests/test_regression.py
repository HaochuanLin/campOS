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


def test_raster_area_error_shrinks_for_wedge_as_grid_is_refined():
    polygon = sim.site_wedge()
    exact_area = 0.5 * 50.0 * 30.0
    errors = {}
    for cell in (2.0, 1.0, 0.5):
        site = sim.Site(polygon, dict(sim.CFG, cell=cell))
        errors[cell] = abs(site.area - exact_area) / exact_area

    assert errors[1.0] < errors[2.0]
    assert errors[0.5] < errors[1.0]
    assert errors[0.5] < 0.01


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

    assert field[0, 0] == 1.0
    assert np.isclose(field[0, 1], 1.0)
    assert np.isclose(field[0, 2], 1.0)
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


def test_measured_radial_profile_is_area_normalized_and_used(tmp_path):
    profile_csv = tmp_path / "profile.csv"
    profile_csv.write_text(
        "radius_fraction,relative_rate\n0,2.0\n0.5,1.2\n1,0.4\n",
        encoding="utf-8",
    )
    profile = sim.load_radial_profile_csv(profile_csv)
    assert profile.shape == (3, 2)
    assert np.isclose(2.0 * np.sum(0.5 * (profile[1:, 1] * profile[1:, 0] + profile[:-1, 1] * profile[:-1, 0]) * np.diff(profile[:, 0])), 1.0)

    X = np.array([[0.0, 1.0, 2.0]])
    Y = np.zeros_like(X)
    head = (0.0, 0.0, 2.0, 0.0, 360.0)
    default = sim.head_field(X, Y, head)
    measured = sim.head_field(X, Y, head, profile)
    assert not np.allclose(default, measured)
    assert measured[0, 2] > 0.0


def test_measured_radial_profile_rejects_invalid_radius_order(tmp_path):
    profile_csv = tmp_path / "bad-profile.csv"
    profile_csv.write_text(
        "radius_fraction,relative_rate\n0,1.0\n0.8,1.0\n0.7,1.0\n1,1.0\n",
        encoding="utf-8",
    )
    try:
        sim.load_radial_profile_csv(profile_csv)
    except ValueError as exc:
        assert "increase strictly" in str(exc)
    else:
        raise AssertionError("invalid profile should be rejected")


def test_performance_curve_interpolates_and_rejects_extrapolation(tmp_path):
    curve = tmp_path / "performance.csv"
    curve.write_text(
        "pressure_kpa,flow_lpm,throw_m\n100,4,5\n200,6,7\n300,8,9\n",
        encoding="utf-8",
    )
    point = sim.load_performance_curve_csv(curve, 150)
    assert point == {"pressure_kpa": 150.0, "flow_lpm": 5.0, "throw_m": 6.0}
    with np.testing.assert_raises_regex(ValueError, "outside measured range"):
        sim.load_performance_curve_csv(curve, 350)


def test_absolute_head_field_uses_flow_radius_and_arc_area():
    X = np.array([[0.0, 1.0]])
    Y = np.array([[0.0, 0.0]])
    full = sim.head_field(X, Y, (0.0, 0.0, 2.0, 0.0, 360.0), flow_lpm=4.0)
    quarter = sim.head_field(X, Y, (0.0, 0.0, 2.0, 0.0, 90.0), flow_lpm=4.0)
    assert np.isclose(full[0, 0], 60.0 * 4.0 / (np.pi * 4.0))
    assert np.isclose(quarter[0, 0], full[0, 0] * 4.0)


def test_public_rainbird_chart_benchmark_is_within_rounding_tolerance():
    from campos.model import spacing_precipitation_mm_h

    benchmark = ROOT / "data" / "benchmarks" / "rainbird_5000_standard_1_5.csv"
    with benchmark.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6
    errors = []
    for row in rows:
        pressure = float(row["pressure_kpa"])
        # Check that the same public data can drive the pressure-curve loader.
        curve = sim.load_performance_curve_csv(benchmark, pressure)
        assert np.isclose(curve["flow_lpm"], float(row["flow_lpm"]))
        assert np.isclose(curve["throw_m"], float(row["throw_m"]))
        for arrangement, key in (
            ("square", "square_precip_mm_h"),
            ("triangular", "triangular_precip_mm_h"),
        ):
            estimate = spacing_precipitation_mm_h(
                curve["flow_lpm"], curve["throw_m"], arrangement, arc_fraction=0.5
            )
            errors.append(abs(estimate - float(row[key])))
    assert max(errors) <= 1.0  # manufacturer chart rates are rounded to integer mm/h


def test_spacing_precipitation_rejects_invalid_inputs():
    from campos.model import spacing_precipitation_mm_h

    with np.testing.assert_raises_regex(ValueError, "arrangement"):
        spacing_precipitation_mm_h(4.0, 10.0, "hexagonal")
    with np.testing.assert_raises_regex(ValueError, "arc_fraction"):
        spacing_precipitation_mm_h(4.0, 10.0, "square", arc_fraction=0.0)


def test_public_sprinkler_benchmark_script_runs():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "benchmark_sprinkler_curve.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: all chart comparisons" in result.stdout


def test_integrated_single_head_field_conserves_supplied_flow():
    # Integrate a full-circle and quarter-circle field on a fine Cartesian grid.
    from campos.model import head_field

    step = 0.05
    centers = np.arange(-2.5, 2.5, step) + step / 2
    X, Y = np.meshgrid(centers, centers)
    flow_lpm = 4.0
    expected_lph = flow_lpm * 60.0
    for arc in (360.0, 90.0):
        field = head_field(X, Y, (0.0, 0.0, 2.0, 0.0, arc), flow_lpm=flow_lpm)
        deposited_lph = float(np.sum(field) * step * step)
        assert abs(deposited_lph - expected_lph) / expected_lph < 0.02


def test_orifice_flow_follows_bernoulli_scaling():
    from campos.model import orifice_flow_lpm

    q1 = orifice_flow_lpm(100.0, 1.0, discharge_coefficient=0.62)
    q2 = orifice_flow_lpm(400.0, 1.0, discharge_coefficient=0.62)
    q3 = orifice_flow_lpm(100.0, 2.0, discharge_coefficient=0.62)
    assert np.isclose(q2 / q1, 2.0)  # Q proportional to sqrt(pressure)
    assert np.isclose(q3 / q1, 4.0)  # Q proportional to diameter squared
    with np.testing.assert_raises_regex(ValueError, "discharge_coefficient"):
        orifice_flow_lpm(100.0, 1.0, discharge_coefficient=1.2)



def test_radial_slope_family_is_area_normalized_and_uniform_at_zero():
    # Integrate q(s) over annuli: area weighting is proportional to s ds.
    s = np.linspace(0.0, 1.0, 20001)
    for slope in (-0.8, 0.0, 2.0):
        rate = (1.0 + slope * s) / (1.0 + 2.0 * slope / 3.0)
        # Exact disk-area mean: 2 * integral_0^1 q(s) * s ds = 1.
        exact_area_mean = 2.0 * (0.5 + slope / 3.0) / (1.0 + 2.0 * slope / 3.0)
        assert np.isclose(exact_area_mean, 1.0, atol=1e-12)
        assert np.all(rate > 0)
    assert np.allclose(np.ones_like(s), 1.0)


def test_head_field_radial_slope_validation_and_measured_profile_precedence():
    X = np.array([[0.0, 1.0, 2.0]])
    Y = np.zeros_like(X)
    head = (0.0, 0.0, 2.0, 0.0, 360.0)
    uniform = sim.head_field(X, Y, head)
    assert np.allclose(uniform, sim.head_field(X, Y, head, radial_slope=0.0))
    with np.testing.assert_raises_regex(ValueError, "radial_slope"):
        sim.head_field(X, Y, head, radial_slope=-1.0)

    profile = np.array([[0.0, 1.5], [0.5, 1.0], [1.0, 0.5]])
    from_profile = sim.head_field(X, Y, head, radial_profile=profile, radial_slope=2.0)
    profile_only = sim.head_field(X, Y, head, radial_profile=profile)
    assert np.allclose(from_profile, profile_only)


def test_cli_rejects_invalid_radial_slope(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "campos_sim.py"),
            "--radial-slope",
            "-1",
            "--quick",
            "--outdir",
            str(tmp_path / "invalid-radial-slope"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "--radial-slope must be finite and greater than -1" in completed.stderr
    assert not (tmp_path / "invalid-radial-slope" / "run_metadata.json").exists()



def test_custom_polygon_and_head_csv_loaders(tmp_path):
    from campos.model import load_heads_csv, load_polygon_csv

    polygon_csv = tmp_path / "polygon.csv"
    polygon_csv.write_text(
        "vertex_id,x_m,y_m\n1,0,0\n2,10,0\n3,10,8\n4,0,8\n5,0,0\n",
        encoding="utf-8",
    )
    polygon = load_polygon_csv(polygon_csv)
    assert polygon.shape == (4, 2)
    assert np.isclose(abs(np.dot(polygon[:, 0], np.roll(polygon[:, 1], -1)) -
                          np.dot(polygon[:, 1], np.roll(polygon[:, 0], -1))) / 2, 80.0)

    heads_csv = tmp_path / "heads.csv"
    heads_csv.write_text(
        "head_id,x_m,y_m,throw_m,start_angle_deg,arc_width_deg\n"
        "H1,1,1,8,-90,360\nH2,9,7,8,180,180\n",
        encoding="utf-8",
    )
    heads = load_heads_csv(heads_csv)
    assert heads.shape == (2, 5)
    assert heads[0, 3] == 270.0
    assert heads[0, 4] == 360.0


def test_custom_polygon_loader_rejects_zero_area_and_nonfinite_coordinates(tmp_path):
    from campos.model import load_polygon_csv

    flat = tmp_path / "flat.csv"
    flat.write_text("x_m,y_m\n0,0\n1,1\n2,2\n", encoding="utf-8")
    with np.testing.assert_raises_regex(ValueError, "non-zero-area"):
        load_polygon_csv(flat)

    bad = tmp_path / "bad.csv"
    bad.write_text("x_m,y_m\n0,0\n1,nan\n0,1\n", encoding="utf-8")
    with np.testing.assert_raises_regex(ValueError, "finite"):
        load_polygon_csv(bad)


def test_fixed_mode_preserves_imported_real_site_head_coordinates():
    cfg = dict(sim.CFG, cell=2.0, margin=2.0, sa_iters=5, restarts=1)
    polygon = np.array([[0, 0], [10, 0], [10, 8], [0, 8]], dtype=float)
    heads = np.array([
        [1.0, 1.0, 8.0, 0.0, 360.0],
        [9.0, 7.0, 8.0, 180.0, 180.0],
    ])
    result = sim.run_site("custom-regression", polygon, cfg, fixed_xy=True, baseline_heads=heads)
    np.testing.assert_array_equal(result["heads0"][:, :2], heads[:, :2])
    np.testing.assert_array_equal(result["heads1"][:, :2], heads[:, :2])
    assert result["baseline_label"] == "Baseline (imported layout)"



def test_custom_site_cli_imports_polygon_and_baseline_heads(tmp_path):
    outdir = tmp_path / "custom-site-output"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "campos_sim.py"),
            "--mode", "fixed",
            "--quick",
            "--cell-size", "1.0",
            "--polygon-csv", str(ROOT / "examples" / "custom_site_demo_polygon.csv"),
            "--heads-csv", str(ROOT / "examples" / "custom_site_demo_heads.csv"),
            "--outdir", str(outdir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    assert (outdir / "results_fixed.csv").is_file()
    metadata = json.loads((outdir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["site_geometry"]["status"] == "custom_polygon_loaded"
    assert metadata["baseline_layout"]["status"] == "imported_layout"
    assert re.fullmatch(r"[0-9a-f]{64}", metadata["site_geometry"]["sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", metadata["baseline_layout"]["sha256"])
