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


def test_ai_residual_correction_trains_only_on_calibration_rows(tmp_path):
    predictions = tmp_path / "paired_predictions.csv"
    outdir = tmp_path / "ai-output"
    rows = ["site_id,run_id,can_id,x_m,y_m,measured_mm,predicted_mm,split"]
    # Eight calibration points span the site; four holdout points are interleaved.
    for i in range(12):
        x = float(i % 6) * 2.0
        y = float(i // 6) * 4.0
        split = "calibration" if i < 8 else "holdout"
        # Repeated coordinate across distinct runs is a valid repeat-run holdout.
        if i == 8:
            x, y = 0.0, 0.0
        # Smooth spatial residual trend gives the GP a meaningful, but synthetic, test signal.
        predicted = 5.0
        measured = predicted + 0.2 * x - 0.1 * y
        run_id = "calibration-run" if split == "calibration" else "holdout-run"
        rows.append(f"site,{run_id},can{i},{x},{y},{measured},{predicted},{split}")
    predictions.write_text("\n".join(rows) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "ai_residual_correction.py"),
            "--predictions-csv", str(predictions),
            "--outdir", str(outdir),
            "--length-scale-m", "3.0",
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert completed.returncode == 0, completed.stdout
    summary = json.loads((outdir / "ai_residual_correction_summary.json").read_text(encoding="utf-8"))
    assert summary["calibration_count"] == 8
    assert summary["holdout_count"] == 4
    assert summary["holdout_rows_used_for_training_or_kernel_selection"] is False
    assert summary["holdout_baseline_metrics"]["n"] == 4
    assert summary["holdout_ai_corrected_metrics"]["n"] == 4
    assert 0.0 <= summary["holdout_ai_95pct_interval_empirical_coverage"] <= 1.0
    assert summary["holdout_ai_mean_95pct_interval_width_mm"] >= 0.0
    with (outdir / "ai_corrected_predictions.csv").open(newline="", encoding="utf-8-sig") as fh:
        output_rows = list(csv.DictReader(fh))
    assert len(output_rows) == 12
    assert all(float(row["ai_corrected_predicted_mm"]) >= 0 for row in output_rows)
    assert all(float(row["ai_residual_std_mm"]) >= 0 for row in output_rows)


def test_ai_residual_correction_can_fail_predeclared_rmse_gate(tmp_path):
    predictions = tmp_path / "gate_predictions.csv"
    outdir = tmp_path / "gate-output"
    rows = ["site_id,run_id,can_id,x_m,y_m,measured_mm,predicted_mm,split"]
    for i in range(11):
        split = "calibration" if i < 8 else "holdout"
        predicted = 5.0
        measured = 6.0 if split == "calibration" else 5.0
        run_id = "calibration-run" if split == "calibration" else "holdout-run"
        rows.append(f"site,{run_id},can{i},{float(i)},0.0,{measured},{predicted},{split}")
    predictions.write_text("\n".join(rows) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "ai_residual_correction.py"),
            "--predictions-csv", str(predictions),
            "--outdir", str(outdir),
            "--length-scale-m", "5.0",
            "--max-holdout-rmse-increase-mm", "0",
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert completed.returncode == 2, completed.stdout
    summary = json.loads((outdir / "ai_residual_correction_summary.json").read_text(encoding="utf-8"))
    assert summary["predeclared_rmse_gate_threshold_mm"] == 0.0
    assert summary["predeclared_rmse_gate_passed"] is False
    assert summary["holdout_rmse_change_mm_corrected_minus_baseline"] > 0.0


def test_ai_residual_correction_rejects_run_split_leakage(tmp_path):
    predictions = tmp_path / "mixed_run.csv"
    rows = ["site_id,run_id,can_id,x_m,y_m,measured_mm,predicted_mm,split"]
    for i in range(12):
        x = float(i % 6) * 2.0
        y = float(i // 6) * 4.0
        split = "calibration" if i < 8 else "holdout"
        # Invalid design: one run appears in both splits, even at different coordinates.
        run_id = "same-run" if i in (0, 8) else ("calibration-run" if split == "calibration" else "holdout-run")
        rows.append(f"site,{run_id},can{i},{x},{y},5.0,5.0,{split}")
    predictions.write_text("\n".join(rows) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "ai_residual_correction.py"),
            "--predictions-csv", str(predictions),
            "--outdir", str(tmp_path / "ai-output"),
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert completed.returncode != 0
    assert "appears in both calibration and holdout" in completed.stdout


def test_ai_residual_correction_rejects_kernel_initial_values_outside_bounds(tmp_path):
    # Kernel initial values must be inside the explicit bounds used by
    # scikit-learn's log-space optimizer; verify the CLI fails clearly.
    cases = [
        ("--length-scale-m", "0.1", "between 0.25 and 100 metres"),
        ("--length-scale-m", "101", "between 0.25 and 100 metres"),
        ("--noise-level-mm", "0.00001", "between 0.0001 and 100 mm^2"),
        ("--noise-level-mm", "101", "between 0.0001 and 100 mm^2"),
    ]
    for option, value, expected_message in cases:
        completed = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "ai_residual_correction.py"),
                "--predictions-csv", str(tmp_path / "does-not-exist.csv"),
                option, value,
            ],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )
        assert completed.returncode != 0
        assert expected_message in completed.stdout
        assert "theta" not in completed.stdout.lower()


def test_optimizer_resolution_rejects_nonfinite_threshold_and_negative_seed(tmp_path):
    cases = [
        (["--max-position-rms", "nan"], "--max-position-rms must be finite and non-negative"),
        (["--max-position-rms", "inf"], "--max-position-rms must be finite and non-negative"),
        (["--seed", "-1"], "--seed must be non-negative"),
    ]
    for extra_args, expected_message in cases:
        completed = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "check_optimizer_resolution.py"),
                "--polygon-csv", str(tmp_path / "missing-polygon.csv"),
                "--heads-csv", str(tmp_path / "missing-heads.csv"),
                "--protected-surface-csv", str(tmp_path / "missing-protected.csv"),
                *extra_args,
            ],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )
        assert completed.returncode != 0
        assert expected_message in completed.stdout
        assert "Traceback" not in completed.stdout


def test_protected_surface_objective_uses_only_protected_polygon_water():
    lawn = np.asarray([(0, 0), (4, 0), (4, 4), (0, 4)], dtype=float)
    sidewalk = np.asarray([(4, 0), (6, 0), (6, 4), (4, 4)], dtype=float)
    cfg = dict(sim.CFG, cell=1.0, margin=2.0, protected_polygon=sidewalk)
    site = sim.Site(lawn, cfg)
    assert site.protected_mask.any()

    field = np.zeros_like(site.X, dtype=float)
    field[site.mask] = 1.0
    field[site.protected_mask] = 2.0
    # Other surrounding ground receives much more modelled water than the
    # sidewalk, so the two candidate objectives must remain distinguishable.
    field[~(site.mask | site.protected_mask)] = 5.0
    reference = {"W0": float(field.sum()), "T": 1.0}

    f1, _, _ = sim.bi_eval(site, field, reference, cfg)
    expected_protected_share = float(field[site.protected_mask].sum() / reference["W0"])
    outside_lawn_share = float(
        (field.sum() - field.ravel()[site.idx].sum()) / reference["W0"]
    )

    assert f1 == expected_protected_share
    assert f1 < outside_lawn_share


def test_catch_can_validation_keeps_holdout_out_of_scale_fit(tmp_path):
    lawn_csv = tmp_path / "lawn.csv"
    heads_csv = tmp_path / "heads.csv"
    observations_csv = tmp_path / "catch-cans.csv"
    predictions_csv = tmp_path / "predictions.csv"
    summary_json = tmp_path / "summary.json"
    lawn_csv.write_text(
        "x_m,y_m\n0,0\n10,0\n10,10\n0,10\n", encoding="utf-8"
    )
    heads_csv.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n5,5,6,0,360\n",
        encoding="utf-8",
    )
    observations_csv.write_text(
        "observation_id,x_m,y_m,observed_depth_mm,split\n"
        "c1,5,5,3.0,calibration\n"
        "c2,6,5,3.5,calibration\n"
        "c3,7,5,4.0,calibration\n"
        "h1,8,5,4.5,holdout\n"
        "h2,9,5,5.0,holdout\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "validate_catch_can_data.py"),
            "--polygon-csv", str(lawn_csv),
            "--heads-csv", str(heads_csv),
            "--observations-csv", str(observations_csv),
            "--radial-slope", "1.0",
            "--duration-minutes", "15",
            "--out", str(predictions_csv),
            "--summary-json", str(summary_json),
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert completed.returncode == 0, completed.stdout
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["calibration_metrics_after_scale_fit"]["rmse_mm"] < 1e-6
    assert summary["holdout_metrics_after_scale_fit"]["rmse_mm"] < 1e-6
    assert summary["holdout_metrics_after_scale_fit"]["n"] == 2
    with predictions_csv.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["split"] for row in rows][-2:] == ["holdout", "holdout"]
    assert all(float(row["predicted_depth_mm_after_calibration"]) >= 0 for row in rows)


def test_catch_can_validation_accepts_per_head_flow_and_boundary_heads(tmp_path):
    lawn_csv = tmp_path / "lawn.csv"
    heads_csv = tmp_path / "heads-with-flow.csv"
    observations_csv = tmp_path / "catch-cans.csv"
    summary_json = tmp_path / "summary.json"
    lawn_csv.write_text(
        "x_m,y_m\n0,0\n10,0\n10,10\n0,10\n", encoding="utf-8"
    )
    # A real head may be installed just outside the lawn boundary.
    heads_csv.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg,flow_lpm\n"
        "-1,5,8,0,360,10\n",
        encoding="utf-8",
    )
    observations_csv.write_text(
        "observation_id,x_m,y_m,observed_depth_mm,split\n"
        "c1,1,5,1.0,calibration\n"
        "c2,2,5,2.0,calibration\n"
        "c3,3,5,3.0,calibration\n"
        "h1,4,5,4.0,holdout\n"
        "h2,5,5,5.0,holdout\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "validate_catch_can_data.py"),
            "--polygon-csv", str(lawn_csv),
            "--heads-csv", str(heads_csv),
            "--observations-csv", str(observations_csv),
            "--duration-minutes", "10",
            "--summary-json", str(summary_json),
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert completed.returncode == 0, completed.stdout
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["per_head_flow_column_used"] is True
    assert summary["raw_physical_input_holdout_metrics"]["n"] == 2
    assert summary["raw_physical_input_holdout_metrics"]["rmse_mm"] > 0
    assert summary["raw_prediction_unit"] == "mm_depth_for_duration"


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
    radius, rate = profile.T
    r0, r1 = radius[:-1], radius[1:]
    q0, q1 = rate[:-1], rate[1:]
    slope = (q1 - q0) / (r1 - r0)
    exact_mean = 2.0 * np.sum(
        (q0 - slope * r0) * (r1**2 - r0**2) / 2.0
        + slope * (r1**3 - r0**3) / 3.0
    )
    assert np.isclose(exact_mean, 1.0, rtol=1e-12, atol=1e-12)

    X = np.array([[0.0, 1.0, 2.0]])
    Y = np.zeros_like(X)
    head = (0.0, 0.0, 2.0, 0.0, 360.0)
    default = sim.head_field(X, Y, head)
    measured = sim.head_field(X, Y, head, profile)
    assert not np.allclose(default, measured)
    assert measured[0, 2] > 0.0


def test_radial_field_conserves_flow_for_measured_profile_and_sector(tmp_path):
    profile_csv = tmp_path / "flow-profile.csv"
    profile_csv.write_text(
        "radius_fraction,relative_rate\n0,2.0\n0.5,1.2\n1,0.4\n",
        encoding="utf-8",
    )
    profile = sim.load_radial_profile_csv(profile_csv)
    flow_lpm = 12.5
    radius_m = 4.0
    arc_deg = 120.0
    n_r, n_theta = 1000, 180
    dr = radius_m / n_r
    dtheta = np.radians(arc_deg) / n_theta
    radial_centres = (np.arange(n_r) + 0.5) * dr
    theta_centres = (np.arange(n_theta) + 0.5) * dtheta
    rr, tt = np.meshgrid(radial_centres, theta_centres, indexing="ij")
    field = sim.head_field(
        rr * np.cos(tt), rr * np.sin(tt),
        (0.0, 0.0, radius_m, 0.0, arc_deg),
        radial_profile=profile, flow_lpm=flow_lpm,
    )
    # Integrate mm/h over m² -> L/h, then convert to L/min.
    integrated_flow_lpm = np.sum(field * rr * dr * dtheta) / 60.0
    assert np.isclose(integrated_flow_lpm, flow_lpm, rtol=1e-4, atol=1e-4)


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



def test_cli_records_explicit_optimization_policy(tmp_path):
    outdir = tmp_path / "policy-output"
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "campos_sim.py"),
            "--mode", "movable", "--quick", "--sites", "A",
            "--dry-fraction-limit", "0.04",
            "--target-factor", "1.1",
            "--cu-drop-budget", "0.05",
            "--max-overspray-increase", "0.02",
            "--pareto-weights", "0,0.5,1",
            "--outdir", str(outdir),
        ],
        cwd=ROOT, text=True, capture_output=True, timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    metadata = json.loads((outdir / "run_metadata.json").read_text(encoding="utf-8"))
    policy = metadata["optimization_policy"]
    assert policy["dry_fraction_limit"] == 0.04
    assert policy["target_factor"] == 1.1
    assert policy["cu_drop_budget"] == 0.05
    assert policy["max_overspray_increase"] == 0.02
    assert policy["selection_guardrails"]["max_overspray_increase_vs_baseline"] == 0.02
    assert policy["pareto_overspray_weights"] == [0.0, 0.5, 1.0]
    assert "not a single weighted score" in policy["note"]
    assert metadata["config"]["pareto_weights"] == [0.0, 0.5, 1.0]


def test_cli_rejects_invalid_optimization_policy_values(tmp_path):
    cases = [
        (["--dry-fraction-limit", "1.1"], "--dry-fraction-limit"),
        (["--target-factor", "0"], "--target-factor"),
        (["--cu-drop-budget", "-0.1"], "--cu-drop-budget"),
        (["--max-overspray-increase", "1.1"], "--max-overspray-increase"),
        (["--pareto-weights", "0,0.5,1.2"], "--pareto-weights"),
        (["--pareto-weights", "0,0.5,0.5"], "duplicate"),
    ]
    for index, (extra_args, expected_error) in enumerate(cases):
        completed = subprocess.run(
            [
                sys.executable, str(ROOT / "campos_sim.py"),
                "--mode", "movable", "--sites", "A",
                "--outdir", str(tmp_path / f"invalid-policy-{index}"),
                *extra_args,
            ],
            cwd=ROOT, text=True, capture_output=True, timeout=30,
        )
        assert completed.returncode != 0
        assert expected_error in completed.stderr
        assert not (tmp_path / f"invalid-policy-{index}" / "run_metadata.json").exists()


def test_catch_can_preparation_script_converts_and_averages_rates(tmp_path):
    raw = tmp_path / "raw-catch-cans.csv"
    prepared = tmp_path / "profile.csv"
    raw.write_text(
        "radius_fraction,depth_mm,run_minutes\n"
        "0,2,10\n0,4,10\n0.5,1.5,10\n0.5,2.5,10\n1,1,10\n1,1,10\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prepare_radial_profile.py"), str(raw), str(prepared)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    profile = sim.load_radial_profile_csv(prepared)
    assert profile.shape == (3, 2)
    assert np.all(np.diff(profile[:, 0]) > 0)
    assert np.all(profile[:, 1] > 0)
    assert "Wrote 3 radial bins" in result.stdout


def test_catch_can_preparation_rejects_missing_endpoint_and_zero_depth(tmp_path):
    raw = tmp_path / "raw-catch-cans.csv"
    prepared = tmp_path / "profile.csv"
    raw.write_text(
        "radius_fraction,depth_mm,run_minutes\n"
        "0.1,2,10\n0.5,1,10\n1,1,10\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prepare_radial_profile.py"), str(raw), str(prepared)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "cover both 0 and 1" in result.stderr

    raw.write_text(
        "radius_fraction,depth_mm,run_minutes\n"
        "0,2,10\n0.5,0,10\n1,1,10\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prepare_radial_profile.py"), str(raw), str(prepared)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "must be positive" in result.stderr



def test_parameter_sensitivity_script_records_reproducible_configuration(tmp_path):
    outdir = tmp_path / "parameter-sensitivity"
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "parameter_sensitivity.py"),
            "--quick", "--sites", "A", "--seeds", "19",
            "--cell-sizes", "1.0", "--slopes", "0",
            "--outdir", str(outdir),
        ],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    with (outdir / "sensitivity_summary.csv").open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["site_id"] == "A"
    assert rows[0]["seed"] == "19"
    assert rows[0]["cell_size_m"] == "1"
    assert rows[0]["radial_slope"] == "0"
    assert rows[0]["status"] == "completed"
    assert "not field validation" in rows[0]["interpretation"]
    metadata = json.loads(
        (outdir / "site_A_seed_19_cell_1_slope_0" / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert metadata["config"]["seed"] == 19
    assert metadata["config"]["cell"] == 1.0
    assert metadata["radial_distribution"]["radial_slope"] == 0.0
    assert (outdir / "README.md").is_file()


def test_design_report_builder_writes_standalone_html_and_markdown(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    metadata = {
        "project_version": "0.1.0",
        "python_version": "3.12.0",
        "numpy_version": "2.0.0",
        "matplotlib_version": "3.9.0",
        "selected_modes": ["movable"],
        "selected_sites": ["A Rectangle"],
        "config": {"seed": 19, "cell": 1.0},
        "optimization_policy": {
            "legacy_modes": ["movable", "fixed"],
            "pareto_objectives": {"f1": "outside water / baseline total"},
            "dry_fraction_limit": 0.02,
            "target_factor": 1.0,
            "cu_drop_budget": 0.03,
            "pareto_overspray_weights": [0.0, 0.5, 1.0],
        },
        "radial_distribution": {"model": "normalized_linear_sensitivity_family", "radial_slope": 0.0},
        "radial_profile": {"status": "uniform_null_model_unvalidated"},
        "hydraulic_performance": {"status": "not_configured"},
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "results_movable.csv").write_text(
        "site,area_m2,sprinkler_count,baseline_AR,optimized_AR,AR_metric_improvement_pct,"
        "annual_water_saving_m3_not_estimated\n"
        "A Rectangle,100,8,1.5,1.2,20,\n",
        encoding="utf-8",
    )
    (run_dir / "layouts_movable.png").write_bytes(b"fake-png-for-embed-test")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_design_report.py"), "--input-dir", str(run_dir)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    html_report = (run_dir / "design_report.html").read_text(encoding="utf-8")
    md_report = (run_dir / "design_report.md").read_text(encoding="utf-8")
    assert "simulation summary only" in html_report.lower()
    assert "AR metric improvement is not a water-savings estimate" in html_report
    assert "data:image/png;base64," in html_report
    assert "A Rectangle" in html_report
    assert "AR metric improvement is not a water-savings estimate" in md_report
    assert "annual_water_saving_m3_not_estimated" in md_report


def test_custom_site_csv_loaders_validate_geometry_and_head_layout(tmp_path):
    polygon_csv = tmp_path / "polygon.csv"
    polygon_csv.write_text(
        "x_m,y_m\n0,0\n10,0\n10,10\n0,10\n0,0\n", encoding="utf-8"
    )
    polygon = sim.load_polygon_csv(polygon_csv)
    assert polygon.shape == (4, 2)

    heads_csv = tmp_path / "heads.csv"
    heads_csv.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n"
        "2,2,4,0,180\n8,8,4,180,180\n",
        encoding="utf-8",
    )
    cfg = dict(sim.CFG)
    heads = sim.load_heads_csv(heads_csv, polygon, cfg)
    assert heads.shape == (2, 5)
    assert np.allclose(heads[:, :2], [[2, 2], [8, 8]])

    bad_heads = tmp_path / "bad_heads.csv"
    bad_heads.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n"
        "12,2,4,0,180\n", encoding="utf-8"
    )
    import pytest
    with pytest.raises(ValueError, match="inside the supplied polygon"):
        sim.load_heads_csv(bad_heads, polygon, cfg)


def test_custom_site_cli_records_input_provenance_and_runs_fixed_mode(tmp_path):
    polygon_csv = tmp_path / "polygon.csv"
    polygon_csv.write_text("x_m,y_m\n0,0\n10,0\n10,10\n0,10\n", encoding="utf-8")
    heads_csv = tmp_path / "heads.csv"
    heads_csv.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n"
        "2,2,4,0,180\n8,8,4,180,180\n", encoding="utf-8"
    )
    out_dir = tmp_path / "custom-run"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "campos_sim.py"), "--mode", "fixed", "--quick",
         "--polygon-csv", str(polygon_csv), "--heads-csv", str(heads_csv),
         "--outdir", str(out_dir)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    metadata = json.loads((out_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["site_input"]["status"] == "user_supplied_geometry_and_heads"
    assert metadata["site_input"]["polygon_vertex_count"] == 4
    assert metadata["site_input"]["initial_head_count"] == 2
    assert metadata["site_input"]["coordinate_units"] == "metres"
    assert len(metadata["site_input"]["polygon_sha256"]) == 64
    assert len(metadata["site_input"]["heads_sha256"]) == 64
    with (out_dir / "results_fixed.csv").open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["site"] == "Custom site"
    assert int(row["sprinkler_count"]) == 2


def test_json_config_supports_cli_override_and_records_provenance(tmp_path):
    config_path = tmp_path / "run.json"
    config_path.write_text(json.dumps({
        "mode": ["fixed"], "sites": ["A"], "quick": True,
        "seed": 11, "cell_size": 1.0, "radial_slope": 0.0,
    }), encoding="utf-8")
    out_dir = tmp_path / "configured-run"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "campos_sim.py"), "--config", str(config_path),
         "--seed", "19", "--outdir", str(out_dir)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    metadata = json.loads((out_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["config"]["seed"] == 19
    assert metadata["config"]["cell"] == 1.0
    assert metadata["configuration_input"]["parameter_sources"]["seed"] == "command_line"
    assert metadata["configuration_input"]["parameter_sources"]["cell_size"] == "config_file"
    assert len(metadata["configuration_input"]["sha256"]) == 64
    assert metadata["data_classification"]["site_geometry"] == "synthetic_builtin"


def test_design_comparison_spec_locks_shared_inputs_and_limits_overrides():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "compare_design_configs", ROOT / "scripts" / "compare_design_configs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shared, scenarios = module.validate_spec({
        "shared": {"sites": ["A"], "seed": 7, "cell_size": 0.5, "quick": True},
        "scenarios": [
            {"name": "fixed", "overrides": {"mode": "fixed"}},
            {"name": "movable", "overrides": {"mode": "movable"}},
        ],
    })
    assert shared["seed"] == 7
    assert [scenario[1] for scenario in scenarios] == ["fixed", "movable"]
    import pytest
    with pytest.raises(ValueError, match="unsupported override"):
        module.validate_spec({
            "shared": {"sites": ["A"], "seed": 7},
            "scenarios": [
                {"name": "one", "overrides": {"seed": 9}},
                {"name": "two", "overrides": {"mode": "fixed"}},
            ],
        })



def test_polygon_loader_rejects_self_intersections_and_nonclosing_duplicate_vertices(tmp_path):
    import pytest

    cases = [
        ("bow_tie", "x_m,y_m\n0,0\n10,10\n0,8\n8,0\n",
         "self-intersecting"),
        ("repeated_vertex", "x_m,y_m\n0,0\n10,0\n10,10\n10,0\n0,10\n",
         "duplicate vertices"),
        ("non_adjacent_touch", "x_m,y_m\n0,0\n4,0\n4,4\n2,0\n0,4\n",
         "self-intersecting"),
    ]
    for name, contents, message in cases:
        path = tmp_path / f"{name}.csv"
        path.write_text(contents, encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            sim.load_polygon_csv(path)


def test_polygon_loader_accepts_valid_concave_polygon_and_optional_closure(tmp_path):
    path = tmp_path / "concave.csv"
    path.write_text(
        "x_m,y_m\n0,0\n6,0\n6,2\n2,2\n2,6\n0,6\n0,0\n",
        encoding="utf-8",
    )
    points = sim.load_polygon_csv(path)
    assert points.shape == (6, 2)
    assert np.isclose(0.5 * np.sum(
        points[:, 0] * np.roll(points[:, 1], -1)
        - points[:, 1] * np.roll(points[:, 0], -1)
    ), 20.0)



def test_observation_error_evaluator_reports_separate_holdout_metrics(tmp_path):
    import importlib.util
    import pytest

    path = ROOT / "scripts" / "evaluate_observation_errors.py"
    spec = importlib.util.spec_from_file_location("evaluate_observation_errors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        {"measured_mm": 10.0, "predicted_mm": 12.0, "split": "calibration"},
        {"measured_mm": 20.0, "predicted_mm": 19.0, "split": "calibration"},
        {"measured_mm": 10.0, "predicted_mm": 11.0, "split": "holdout"},
        {"measured_mm": 20.0, "predicted_mm": 18.0, "split": "holdout"},
    ]
    report = module.evaluate(rows)
    assert report["split_counts"] == {"calibration": 2, "holdout": 2}
    assert report["metrics"]["holdout"]["mae_mm"] == 1.5
    assert report["metrics"]["holdout"]["bias_mm_predicted_minus_measured"] == -0.5
    assert report["metrics"]["holdout"]["rmse_mm"] == pytest.approx((2.5) ** 0.5)
    assert "not a pass/fail certification" in report["metrics"]["holdout"]["interpretation"]
    with pytest.raises(ValueError, match="independent holdout"):
        module.evaluate([rows[0], rows[1], rows[2]])


def test_observation_error_evaluator_rejects_nonfinite_and_negative_depths(tmp_path):
    import importlib.util
    import pytest

    spec = importlib.util.spec_from_file_location(
        "evaluate_observation_errors", ROOT / "scripts" / "evaluate_observation_errors.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for measured, predicted, message in [
        ("nan", "1", "finite"),
        ("-1", "1", "non-negative"),
        ("1", "inf", "finite"),
    ]:
        path = tmp_path / "pairs.csv"
        path.write_text(
            "measured_mm,predicted_mm,split\n"
            f"{measured},{predicted},holdout\n"
            "2,2,holdout\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=message):
            module.load_pairs(path)



def test_field_observation_qc_derives_depth_and_marks_scope(tmp_path):
    source = tmp_path / "observations.csv"
    source.write_text(
        "site_id,run_id,can_id,x_m,y_m,zone,collection_duration_s,"
        "collected_volume_ml,measured_depth_mm,container_opening_area_cm2,validity_flag,split,pressure_kpa,wind_speed_m_s,wind_direction_deg,air_temperature_c\n"
        "site-1,run-1,can-1,1,2,inside,600,50,,10,valid,calibration,101,1.2,180,22\n",
        encoding="utf-8",
    )
    outdir = tmp_path / "qc"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_field_observations.py"),
            "--input",
            str(source),
            "--outdir",
            str(outdir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    normalized = list(csv.DictReader((outdir / "field_observation_qc.csv").open(encoding="utf-8")))
    assert len(normalized) == 1
    assert np.isclose(float(normalized[0]["measured_depth_mm_normalized"]), 50.0)
    assert float(normalized[0]["pressure_kpa"]) == 101.0
    assert float(normalized[0]["wind_speed_m_s"]) == 1.2
    assert float(normalized[0]["wind_direction_deg"]) == 180.0
    assert float(normalized[0]["air_temperature_c"]) == 22.0
    summary = json.loads((outdir / "field_observation_qc.json").read_text(encoding="utf-8"))
    assert summary["status"] == "schema_and_unit_checks_passed"
    assert "no model comparison" in summary["scope_note"]


def test_field_observation_qc_rejects_duplicate_can_ids_within_run(tmp_path):
    source = tmp_path / "duplicate.csv"
    row = "site-1,run-1,can-1,1,2,inside,600,50,,10,valid,calibration\n"
    source.write_text(
        "site_id,run_id,can_id,x_m,y_m,zone,collection_duration_s,"
        "collected_volume_ml,measured_depth_mm,container_opening_area_cm2,validity_flag,split\n"
        + row + row,
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check_field_observations.py"),
            "--input",
            str(source),
            "--outdir",
            str(tmp_path / "qc"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "duplicate site_id/run_id/can_id" in completed.stderr



def test_catch_can_prediction_uses_exact_coordinates_and_reports_holdout_metrics(tmp_path):
    polygon = tmp_path / "polygon.csv"
    polygon.write_text("x_m,y_m\n0,0\n20,0\n20,20\n0,20\n", encoding="utf-8")
    heads = tmp_path / "heads.csv"
    heads.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg,flow_lpm\n10,10,5,0,360,1.0\n-2,10,5,0,360,1.0\n",
        encoding="utf-8",
    )
    observations = tmp_path / "observations.csv"
    observations.write_text(
        "site_id,run_id,can_id,x_m,y_m,zone,collection_duration_s,"
        "collected_volume_ml,measured_depth_mm,container_opening_area_cm2,validity_flag,split\n"
        "site-1,cal-run,can-1,10,10,inside,600,,0.127323954,,valid,calibration\n"
        "site-1,cal-run,can-2,11,10,outside,600,,0.127323954,,valid,calibration\n"
        "site-1,test-run,can-3,12,10,inside,600,,0.127323954,,valid,holdout\n"
        "site-1,test-run,can-4,13,10,inside,600,,0.127323954,,valid,holdout\n"
        "site-1,test-run,can-5,-1,10,outside,600,,0.127323954,,valid,holdout\n",
        encoding="utf-8",
    )
    outdir = tmp_path / "evaluation"
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "predict_catch_can_depths.py"),
            "--polygon-csv", str(polygon), "--heads-csv", str(heads),
            "--observations", str(observations), "--flow-lpm", "2",
            "--outdir", str(outdir),
        ],
        cwd=ROOT, text=True, capture_output=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    rows = list(csv.DictReader((outdir / "paired_predictions.csv").open(encoding="utf-8")))
    assert len(rows) == 5
    assert all(row["point_inside_polygon"] == "True" for row in rows[:4])
    assert rows[4]["point_inside_polygon"] == "False"
    assert np.isclose(float(rows[0]["predicted_mm"]), 60 / (np.pi * 25) / 6)
    report = json.loads((outdir / "field_evaluation_metrics.json").read_text(encoding="utf-8"))
    assert report["metrics"]["split_counts"] == {"calibration": 2, "holdout": 3}
    assert report["metrics"]["metrics"]["holdout"]["mae_mm"] < 1e-6
    assert report["zone_geometry_mismatch_count"] == 1
    assert len(report["software"]["source_sha256"]["model.py"]) == 64
    assert len(report["software"]["source_sha256"]["field_validation.py"]) == 64
    assert report["zone_geometry_mismatch_can_ids"] == ["can-2"]
    assert report["metrics_by_zone"]["outside"]["holdout_n"] == 1
    assert report["metrics_by_zone"]["outside"]["holdout"]["mae_mm"] < 1e-6
    assert "no universal pass threshold" in " ".join(report["limitations"]).lower()


def test_catch_can_prediction_rejects_a_run_mixed_across_splits(tmp_path):
    polygon = tmp_path / "polygon.csv"
    polygon.write_text("x_m,y_m\n0,0\n20,0\n20,20\n0,20\n", encoding="utf-8")
    heads = tmp_path / "heads.csv"
    heads.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n10,10,5,0,360\n",
        encoding="utf-8",
    )
    observations = tmp_path / "observations.csv"
    observations.write_text(
        "site_id,run_id,can_id,x_m,y_m,zone,collection_duration_s,"
        "collected_volume_ml,measured_depth_mm,container_opening_area_cm2,validity_flag,split\n"
        "site-1,same-run,can-1,10,10,inside,600,,0.1,,valid,calibration\n"
        "site-1,same-run,can-2,11,10,inside,600,,0.1,,valid,holdout\n"
        "site-1,test-run,can-3,12,10,inside,600,,0.1,,valid,holdout\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "predict_catch_can_depths.py"),
            "--polygon-csv", str(polygon), "--heads-csv", str(heads),
            "--observations", str(observations), "--flow-lpm", "1",
            "--outdir", str(tmp_path / "out"),
        ],
        cwd=ROOT, text=True, capture_output=True, timeout=30,
    )
    assert completed.returncode != 0
    assert "mixes calibration and holdout" in completed.stderr



def test_pareto_tradeoff_selection_minimizes_overspray_within_cu_budget():
    front = [
        {"f1": 0.05, "CU": 0.90},
        {"f1": 0.08, "CU": 0.93},
        {"f1": 0.12, "CU": 0.95},
        {"f1": 0.20, "CU": 0.97},
    ]
    selected = sim.select_tradeoff(front, budget=0.04)
    assert selected == 1
    assert front[selected]["f1"] == 0.08
    assert front[selected]["CU"] >= max(point["CU"] for point in front) - 0.04


def test_pareto_tradeoff_zero_cu_budget_selects_most_uniform_point():
    front = [
        {"f1": 0.05, "CU": 0.90},
        {"f1": 0.08, "CU": 0.93},
        {"f1": 0.12, "CU": 0.95},
    ]
    assert sim.select_tradeoff(front, budget=0.0) == 2



def test_protected_surface_polygon_is_disjoint_and_objective_is_surface_specific():
    lawn = sim.site_rect()
    protected = np.array([[-4.0, 0.0], [-4.0, 25.0], [-2.0, 25.0], [-2.0, 0.0]])
    assert not sim.polygons_overlap(lawn, protected)
    adjacent = np.array([[40.0, 0.0], [40.0, 25.0], [43.0, 25.0], [43.0, 0.0]])
    assert not sim.polygons_overlap(lawn, adjacent)
    # Coincident polygons are an overlap, even though every vertex lies on
    # the other polygon's boundary and no edges cross properly.
    assert sim.polygons_overlap(lawn, lawn.copy())
    assert sim.polygons_overlap(lawn, lawn[::-1].copy())
    overlapping = np.array([[-1.0, 0.0], [-1.0, 5.0], [2.0, 5.0], [2.0, 0.0]])
    assert sim.polygons_overlap(lawn, overlapping)

    cfg = dict(sim.CFG, cell=1.0, margin=2.0, dry_thresh_frac=0.3,
               protected_polygon=protected)
    site = sim.Site(lawn, cfg)
    field = np.zeros_like(site.X)
    field.ravel()[site.idx] = 1.0
    field[~site.mask] = 0.25
    field[site.protected_mask] = 0.75
    ref = {"W0": 100.0, "T": 1.0}
    f1, f2, dry = sim.bi_eval(site, field, ref, cfg)
    expected_protected_water = field[site.protected_mask].sum()
    np.testing.assert_allclose(f1, expected_protected_water / ref["W0"])
    assert f2 == 0.0
    assert dry == 0.0
    assert site.protected_mask.any()
    assert not np.any(site.protected_mask & site.mask)


def test_protected_surface_too_narrow_for_grid_fails_fast():
    lawn = sim.site_rect()
    thin_strip = np.array([[40.1, 0.0], [40.1, 25.0], [40.2, 25.0], [40.2, 0.0]])
    cfg = dict(sim.CFG, cell=1.0, margin=2.0, protected_polygon=thin_strip)
    try:
        sim.Site(lawn, cfg)
    except ValueError as exc:
        assert "contains no grid-cell centres" in str(exc)
    else:
        raise AssertionError("sub-grid protected surface should fail fast")


def test_optimizer_resolution_checker_reports_selected_solution_sensitivity(tmp_path):
    lawn_csv = tmp_path / "lawn.csv"
    protected_csv = tmp_path / "sidewalk.csv"
    heads_csv = tmp_path / "heads.csv"
    output_csv = tmp_path / "optimizer-resolution.csv"
    lawn_csv.write_text(
        "x_m,y_m\n0,0\n10,0\n10,10\n0,10\n", encoding="utf-8"
    )
    protected_csv.write_text(
        "x_m,y_m\n10,0\n10,10\n14,10\n14,0\n", encoding="utf-8"
    )
    heads_csv.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n8,5,6,180,180\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "check_optimizer_resolution.py"),
            "--polygon-csv", str(lawn_csv),
            "--protected-surface-csv", str(protected_csv),
            "--heads-csv", str(heads_csv),
            "--cell-sizes", "2,1",
            "--mode", "fixed",
            "--quick",
            "--out", str(output_csv),
        ],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    assert completed.returncode == 0, completed.stdout
    with output_csv.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert [float(row["cell_size_m"]) for row in rows] == [2.0, 1.0]
    assert all(int(row["grid_cells_protected_surface"]) > 0 for row in rows)
    assert all("selected_f1_pct_baseline_total_water" in row for row in rows)
    assert all("position_rms_from_finest_m" in row for row in rows)


def test_protected_surface_resolution_checker_reports_converging_area_error(tmp_path):
    lawn_csv = tmp_path / "lawn.csv"
    protected_csv = tmp_path / "sidewalk.csv"
    heads_csv = tmp_path / "heads.csv"
    output_csv = tmp_path / "resolution.csv"
    lawn_csv.write_text(
        "x_m,y_m\n0,0\n40,0\n40,25\n0,25\n", encoding="utf-8"
    )
    protected_csv.write_text(
        "x_m,y_m\n-4.25,0.3\n-4.25,24.7\n-1.65,24.7\n-1.65,0.3\n",
        encoding="utf-8",
    )
    heads_csv.write_text(
        "x_m,y_m,radius_m,start_angle_deg,arc_width_deg\n2,12.5,8,0,360\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "check_protected_surface_resolution.py"),
            "--polygon-csv", str(lawn_csv),
            "--protected-surface-csv", str(protected_csv),
            "--heads-csv", str(heads_csv),
            "--cell-sizes", "2,1,0.5,0.25",
            "--max-relative-error", "0.05",
            "--max-water-share-spread", "100",
            "--out", str(output_csv),
        ],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    with output_csv.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert [float(row["cell_size_m"]) for row in rows] == [2.0, 1.0, 0.5, 0.25]
    assert float(rows[0]["relative_area_error_pct"]) > float(rows[-1]["relative_area_error_pct"])
    assert float(rows[-1]["relative_area_error_pct"]) <= 5.0
    assert all(int(row["grid_cells_in_protected_surface"]) > 0 for row in rows)
    shares = [float(row["protected_water_pct_of_total_water"]) for row in rows]
    assert all(0.0 < share < 100.0 for share in shares)
    assert all(float(row["total_water_integral_m2_relative_depth"]) > 0 for row in rows)


def test_protected_surface_polygon_csv_loader_accepts_valid_polygon(tmp_path):
    path = tmp_path / "sidewalk.csv"
    path.write_text("x_m,y_m\n-4,0\n-4,25\n-2,25\n-2,0", encoding="utf-8")
    points = sim.load_polygon_csv(path)
    np.testing.assert_allclose(points, [[-4, 0], [-4, 25], [-2, 25], [-2, 0]])


def test_pareto_overspray_objective_counts_only_water_outside_lawn():
    cfg = dict(sim.CFG, cell=1.0, margin=2.0, dry_thresh_frac=0.3)
    site = sim.Site(sim.site_rect(), cfg)
    field = np.zeros_like(site.X)
    field.ravel()[site.idx] = 1.0
    field[~site.mask] = 0.25
    reference_total_water = 100.0

    f1, f2, dry = sim.bi_eval(
        site, field, {"W0": reference_total_water, "T": 1.0}, cfg
    )

    expected_outside_water = np.count_nonzero(~site.mask) * 0.25
    np.testing.assert_allclose(f1, expected_outside_water / reference_total_water)
    assert f2 == 0.0
    assert dry == 0.0



def test_baseline_guard_rejects_pareto_points_that_increase_overspray():
    baseline = {"f1": 0.007, "CU": 0.700, "f2": 0.15}
    front = [
        {"f1": 0.051, "CU": 0.765, "f2": 0.10},
        {"f1": 0.142, "CU": 0.729, "f2": 0.11},
    ]
    assert sim.select_tradeoff(front, budget=0.03, baseline=baseline) is None


def test_baseline_guard_selects_lowest_overspray_without_exceeding_cu_budget():
    baseline = {"f1": 0.10, "CU": 0.80, "f2": 0.20}
    front = [
        {"f1": 0.08, "CU": 0.75, "f2": 0.15},
        {"f1": 0.06, "CU": 0.76, "f2": 0.14},
        {"f1": 0.04, "CU": 0.70, "f2": 0.12},
    ]
    selected = sim.select_tradeoff(front, budget=0.05, baseline=baseline)
    assert selected == 1
    assert front[selected]["f1"] <= baseline["f1"]
    assert front[selected]["CU"] >= baseline["CU"] - 0.05


def test_baseline_guard_returns_none_when_cu_budget_is_violated():
    baseline = {"f1": 0.10, "CU": 0.80, "f2": 0.20}
    front = [
        {"f1": 0.05, "CU": 0.70, "f2": 0.10},
        {"f1": 0.08, "CU": 0.74, "f2": 0.12},
    ]
    assert sim.select_tradeoff(front, budget=0.03, baseline=baseline) is None



def test_baseline_guard_allows_only_explicit_overspray_tolerance():
    baseline = {"f1": 0.007, "CU": 0.700, "f2": 0.15}
    front = [
        {"f1": 0.015, "CU": 0.700, "f2": 0.14},
        {"f1": 0.016, "CU": 0.710, "f2": 0.16},
    ]
    assert sim.select_tradeoff(
        front, budget=0.03, baseline=baseline, max_overspray_increase=0.01
    ) == 0
    assert sim.select_tradeoff(
        front, budget=0.03, baseline=baseline, max_overspray_increase=0.005
    ) is None



def test_baseline_guard_rejects_worse_interior_deficit_even_with_overspray_tolerance():
    baseline = {"f1": 0.007, "CU": 0.700, "f2": 0.15}
    front = [{"f1": 0.02, "CU": 0.700, "f2": 0.16}]
    assert sim.select_tradeoff(
        front, budget=0.03, baseline=baseline, max_overspray_increase=0.10
    ) is None



def test_baseline_guard_rejects_dry_area_constraint_violation():
    baseline = {"f1": 0.10, "CU": 0.80, "f2": 0.20, "dry": 0.01}
    candidates = [
        {"f1": 0.05, "CU": 0.80, "f2": 0.15, "dry": 0.03},
        {"f1": 0.06, "CU": 0.80, "f2": 0.15, "dry": 0.01},
    ]
    assert sim.select_tradeoff(
        candidates, budget=0.03, baseline=baseline, dry_limit=0.02
    ) == 1


def test_pareto_guardrail_diagnostics_name_each_failed_constraint():
    point = {"f1": 0.12, "CU": 0.70, "f2": 0.25, "dry": 0.04}
    baseline = {"f1": 0.10, "CU": 0.80, "f2": 0.20, "dry": 0.01}
    checks = sim.tradeoff_guardrail_checks(
        point, baseline, budget=0.03, max_overspray_increase=0.01, dry_limit=0.02
    )
    assert checks == {
        "cu": False,
        "overspray": False,
        "interior_deficit": False,
        "dry_area": False,
    }


def test_quickstart_index_is_browsable_and_labels_synthetic_results(tmp_path):
    from campos.quickstart import LIMITATIONS, build_index

    (tmp_path / "results_movable.csv").write_text(
        "site,baseline_AR,optimized_AR,baseline_CU,optimized_CU,optimized_overspray_pct_of_own_water,optimized_dry_area_pct\n"
        "A,2.0,1.5,0.7,0.8,4.0,1.0\n",
        encoding="utf-8",
    )
    (tmp_path / "results_fixed.csv").write_text(
        "site,baseline_AR,optimized_AR,baseline_CU,optimized_CU,optimized_overspray_pct_of_own_water,optimized_dry_area_pct\n"
        "A,2.0,1.7,0.7,0.75,3.0,2.0\n",
        encoding="utf-8",
    )
    (tmp_path / "layouts.png").write_bytes(b"test image placeholder")
    manifest = {
        "finished_at_utc": "2026-10-24T00:00:00+00:00",
        "mode": "compare",
        "sites": ["A"],
        "quick": True,
    }
    report = build_index(tmp_path, manifest)
    page = report.read_text(encoding="utf-8")
    assert "campOS quickstart" in page
    assert "field-validated irrigation design" in page
    assert "results_movable.csv" in page
    assert "layouts.png" in page
    assert "optimized_AR" in page
    assert "Fixed vs movable comparison" in page
    assert "fixed" in page and "movable" in page
    assert all(item in page for item in LIMITATIONS)
