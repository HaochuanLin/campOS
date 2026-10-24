"""Optional local Streamlit UI for the no-data-required campOS demo."""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import streamlit as st


st.set_page_config(page_title="campOS | Irrigation layout explorer", layout="wide")
st.title("campOS · Irrigation layout explorer")
st.caption("A local decision-support prototype. The starter scenarios are synthetic, not field-validated.")

with st.sidebar:
    st.header("Run setup")
    custom_site = st.checkbox(
        "Use surveyed site CSVs",
        value=False,
        help="Upload a lawn polygon and existing sprinkler layout in metre-based coordinates.",
    )
    mode_options = (
        ["fixed", "movable", "pareto-fixed", "pareto-movable"]
        if custom_site else
        ["compare", "fixed", "movable", "pareto-fixed", "pareto-movable"]
    )
    mode = st.selectbox(
        "Optimization mode",
        mode_options,
        index=0,
        help="Custom-site mode uses one explicit optimization mode; synthetic compare runs fixed and movable scenarios.",
    )
    sites = []
    polygon_upload = heads_upload = protected_upload = observations_upload = None
    thresholds_upload = None
    profile_upload = performance_upload = None
    fallback_flow_lpm = 0.0
    pressure_kpa = 0.0
    ai_correction = False
    strict_zone_gate = False
    if custom_site:
        polygon_upload = st.file_uploader("Lawn polygon CSV (x_m,y_m)", type=["csv"], key="lawn-polygon")
        heads_upload = st.file_uploader(
            "Sprinkler layout CSV (x_m,y_m,radius_m,start_angle_deg,arc_width_deg)",
            type=["csv"],
            key="sprinkler-layout",
        )
        profile_upload = st.file_uploader(
            "Measured radial profile CSV (optional: radius_fraction,relative_rate)",
            type=["csv"],
            key="radial-profile",
        )
        performance_upload = st.file_uploader(
            "Manufacturer/bench pressure-flow-throw CSV (optional)",
            type=["csv"],
            key="pressure-performance",
        )
        if performance_upload is not None:
            pressure_kpa = st.number_input(
                "Measured operating pressure (kPa)",
                min_value=1.0, max_value=1500.0, value=200.0, step=5.0,
                help="Required with a pressure-flow-throw curve; the model will not extrapolate beyond its measured pressure range.",
            )
        observations_upload = st.file_uploader(
            "Catch-can observations CSV (optional, for model evaluation)",
            type=["csv"],
            key="catch-can-observations",
        )
        fallback_flow_lpm = st.number_input(
            "Fallback measured flow per head (L/min; 0 = none)",
            min_value=0.0, max_value=100.0, value=0.0, step=0.1,
            help="Only used when a head has no flow_lpm value in the layout CSV.",
        )
        if observations_upload is not None:
            thresholds_upload = st.file_uploader(
                "Pre-registered holdout acceptance thresholds JSON (optional)",
                type=["json"],
                key="field-acceptance-thresholds",
                help="Upload limits decided before inspecting holdout errors. A failed limit marks the evaluation as failed while preserving outputs.",
            )
            strict_zone_gate = st.checkbox(
                "Fail on zone/polygon label mismatch",
                value=False,
                help="Fail the evaluation command if a catch-can labelled inside/outside contradicts the uploaded lawn polygon. Boundary observations should be labelled boundary.",
            )
            ai_correction = st.checkbox(
                "Experimental AI residual correction",
                value=False,
                help="Requires the optional AI dependency (pip install -e \".[ui,ai]\"). "
                     "Uses calibration rows for fitting and reports holdout errors; it is not a validated controller.",
            )
        if mode.startswith("pareto-"):
            protected_upload = st.file_uploader(
                "Protected road/sidewalk polygon CSV (optional)",
                type=["csv"],
                key="protected-surface",
                help="In Pareto modes, this polygon becomes the protected-surface water objective.",
            )
        else:
            st.caption("The protected-surface objective is active in Pareto modes only. Choose pareto-fixed or pareto-movable to optimize against a road/sidewalk polygon.")
        st.caption("Coordinates and radii must be in metres. These are illustrative examples, not surveyed measurements.")
        template_dir = Path(__file__).resolve().parents[2] / "data" / "templates"
        for label, filename in (
            ("Download lawn polygon example", "site_polygon_template.csv"),
            ("Download sprinkler layout example", "sprinkler_layout_template.csv"),
            ("Download protected-surface example", "protected_surface_template.csv"),
            ("Download catch-can observation template", "field_catch_can_template.csv"),
            ("Download radial-profile template", "catch_can_profile_template.csv"),
            ("Download pressure-performance template", "sprinkler_performance_template.csv"),
        ):
            template_path = template_dir / filename
            if template_path.is_file():
                st.download_button(
                    label, data=template_path.read_bytes(), file_name=filename,
                    mime="text/csv", key=f"template-{filename}", use_container_width=True,
                )
    else:
        sites = st.multiselect("Synthetic sites", ["A", "B", "C", "D", "E"], default=["A"])
    seed = st.number_input("Random seed", min_value=0, max_value=2147483647, value=7, step=1)
    cell_size = st.number_input("Grid cell size (m)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)
    full = st.checkbox("Run a longer search", value=False, help="May take substantially longer.")
    ready = bool(polygon_upload and heads_upload) if custom_site else bool(sites)
    run = st.button("Run simulation", type="primary", disabled=not ready, use_container_width=True)

st.warning(
    "This demo needs no real data, but it does not fabricate field measurements. "
    "Its metrics cannot prove actual road wetting, field accuracy, or water savings."
)

if run:
    # Avoid showing a previous run as if it were the result of this attempt.
    st.session_state.pop("campos_run", None)
    with st.spinner("Running campOS simulation and building the report…"):
        with tempfile.TemporaryDirectory(prefix="campos-ui-") as temporary:
            workdir = Path(temporary)
            outdir = workdir / "results"
            outdir.mkdir(parents=True, exist_ok=True)
            if custom_site:
                polygon_path = workdir / "site_polygon.csv"
                heads_path = workdir / "sprinkler_layout.csv"
                polygon_path.write_bytes(polygon_upload.getvalue())
                heads_path.write_bytes(heads_upload.getvalue())
                observations_path = None
                if observations_upload is not None:
                    observations_path = workdir / "catch_can_observations.csv"
                    observations_path.write_bytes(observations_upload.getvalue())
                thresholds_path = None
                if thresholds_upload is not None:
                    thresholds_path = workdir / "acceptance_thresholds.json"
                    thresholds_path.write_bytes(thresholds_upload.getvalue())
                profile_path = None
                if profile_upload is not None:
                    profile_path = workdir / "radial_profile.csv"
                    profile_path.write_bytes(profile_upload.getvalue())
                performance_path = None
                if performance_upload is not None:
                    performance_path = workdir / "pressure_performance.csv"
                    performance_path.write_bytes(performance_upload.getvalue())
                command = shutil.which("campos-sim")
                invocation = [command] if command else [sys.executable, "-m", "campos.campos_sim"]
                invocation += [
                    "--mode", mode,
                    "--polygon-csv", str(polygon_path),
                    "--heads-csv", str(heads_path),
                    "--seed", str(int(seed)),
                    "--cell-size", str(float(cell_size)),
                    "--outdir", str(outdir),
                ]
                if protected_upload is not None:
                    protected_path = workdir / "protected_surface.csv"
                    protected_path.write_bytes(protected_upload.getvalue())
                    invocation += ["--protected-surface-csv", str(protected_path)]
                if profile_path is not None:
                    invocation += ["--profile-csv", str(profile_path)]
                if performance_path is not None:
                    invocation += [
                        "--performance-csv", str(performance_path),
                        "--pressure-kpa", str(float(pressure_kpa)),
                    ]
                if not full:
                    invocation.append("--quick")
                result_sites = ["custom surveyed site"]
            else:
                command = shutil.which("campos-start")
                invocation = [command] if command else [sys.executable, "-m", "campos.quickstart"]
                invocation += [
                    "--mode", mode, "--sites", *sites,
                    "--seed", str(int(seed)), "--cell-size", str(float(cell_size)),
                    "--outdir", str(outdir),
                ]
                if full:
                    invocation.append("--full")
                result_sites = list(sites)
            try:
                completed = subprocess.run(
                    invocation, check=False, capture_output=True, text=True, timeout=900
                )
            except subprocess.TimeoutExpired:
                st.error("The run exceeded the 15-minute safety timeout. Try quick mode or fewer sites.")
                st.stop()
            except OSError as exc:
                st.error("The simulation command could not be launched.")
                st.code(str(exc))
                st.stop()
            if completed.returncode:
                st.error("The simulation failed. No successful result is being shown.")
                st.code((completed.stderr or completed.stdout)[-12000:])
                st.stop()

            field_eval_ok = None
            field_eval_message = None
            field_eval_log = ""
            if custom_site and observations_upload is not None:
                eval_command = shutil.which("campos-field-evaluate")
                eval_invocation = [eval_command] if eval_command else [sys.executable, "-m", "campos.field_validation"]
                eval_invocation += [
                    "--polygon-csv", str(polygon_path),
                    "--heads-csv", str(heads_path),
                    "--observations", str(observations_path),
                    "--outdir", str(outdir),
                ]
                if fallback_flow_lpm > 0:
                    eval_invocation += ["--flow-lpm", str(float(fallback_flow_lpm))]
                if strict_zone_gate:
                    eval_invocation.append("--fail-on-zone-geometry-mismatch")
                if thresholds_path is not None:
                    eval_invocation += ["--acceptance-thresholds-json", str(thresholds_path)]
                if profile_path is not None:
                    eval_invocation += ["--profile-csv", str(profile_path)]
                try:
                    evaluated = subprocess.run(
                        eval_invocation, check=False, capture_output=True, text=True, timeout=300
                    )
                    field_eval_ok = evaluated.returncode == 0
                    field_eval_log = (evaluated.stdout + "\n" + evaluated.stderr)[-12000:]
                    if field_eval_ok:
                        field_eval_message = (
                            "Pointwise field-evaluation artifacts were generated. Review holdout errors; this is not a certification."
                        )
                    else:
                        evaluation_report_path = outdir / "field_evaluation_metrics.json"
                        failed_gate_statuses = {"acceptance_thresholds_failed", "zone_geometry_gate_failed"}
                        try:
                            evaluation_report = json.loads(evaluation_report_path.read_text(encoding="utf-8"))
                        except (OSError, UnicodeError, json.JSONDecodeError):
                            evaluation_report = {}
                        if evaluation_report.get("status") in failed_gate_statuses:
                            field_eval_message = (
                                "Field-evaluation artifacts were generated, but a configured acceptance gate failed. "
                                "Review the saved metrics and predictions; AI correction is intentionally blocked."
                            )
                        else:
                            field_eval_message = (
                                "Field evaluation did not complete. The optimization outputs are still available; inspect the diagnostic log."
                            )
                except subprocess.TimeoutExpired:
                    field_eval_ok = False
                    field_eval_message = "Field evaluation timed out. The optimization outputs are still available."
                    field_eval_log = "The field-evaluation command exceeded the 5-minute timeout."
                except OSError as exc:
                    field_eval_ok = False
                    field_eval_message = "Field evaluation could not be launched. The optimization outputs are still available."
                    field_eval_log = str(exc)

            ai_eval_ok = None
            ai_eval_message = None
            ai_eval_log = ""
            if custom_site and ai_correction:
                if not field_eval_ok:
                    ai_eval_ok = False
                    ai_eval_message = "AI correction requires a successful catch-can evaluation first."
                else:
                    ai_script = Path(__file__).resolve().parents[2] / "scripts" / "ai_residual_correction.py"
                    ai_outdir = workdir / "ai-correction"
                    ai_invocation = [
                        sys.executable, str(ai_script),
                        "--predictions-csv", str(outdir / "paired_predictions.csv"),
                        "--outdir", str(ai_outdir),
                    ]
                    try:
                        ai_completed = subprocess.run(
                            ai_invocation, check=False, capture_output=True, text=True, timeout=300
                        )
                        ai_eval_ok = ai_completed.returncode == 0
                        ai_eval_log = (ai_completed.stdout + "\n" + ai_completed.stderr)[-12000:]
                        if ai_outdir.is_dir():
                            for ai_path in ai_outdir.iterdir():
                                if ai_path.is_file():
                                    shutil.copy2(ai_path, outdir / ai_path.name)
                        ai_eval_message = (
                            "Experimental GP residual correction completed. Review the holdout comparison; this does not establish generalization."
                            if ai_eval_ok else
                            "AI correction did not complete. The physical-model and field-evaluation outputs remain available."
                        )
                    except subprocess.TimeoutExpired:
                        ai_eval_ok = False
                        ai_eval_message = "AI correction timed out. Other outputs remain available."
                        ai_eval_log = "The AI residual-correction command exceeded the 5-minute timeout."
                    except OSError as exc:
                        ai_eval_ok = False
                        ai_eval_message = "AI correction could not be launched. Other outputs remain available."
                        ai_eval_log = str(exc)

            artifacts = {}
            for path in sorted(outdir.iterdir()):
                if path.is_file():
                    artifacts[path.name] = path.read_bytes()
            tables = {}
            for name, payload in artifacts.items():
                if name.endswith(".csv"):
                    try:
                        tables[name] = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
                    except (UnicodeDecodeError, csv.Error):
                        continue
            field_metrics = {}
            metrics_payload = artifacts.get("field_evaluation_metrics.json")
            if metrics_payload:
                try:
                    evaluation_report = json.loads(metrics_payload.decode("utf-8"))
                    field_metrics = (
                        evaluation_report.get("metrics", {}).get("metrics", {}).get("holdout") or {}
                    )
                except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                    field_metrics = {}
            ai_summary = {}
            ai_payload = artifacts.get("ai_residual_correction_summary.json")
            if ai_payload:
                try:
                    ai_summary = json.loads(ai_payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    ai_summary = {}
            st.session_state["campos_run"] = {
                "artifacts": artifacts,
                "tables": tables,
                "field_metrics": field_metrics,
                "ai_summary": ai_summary,
                "ai_eval_ok": ai_eval_ok,
                "ai_eval_message": ai_eval_message,
                "ai_eval_log": ai_eval_log,
                "mode": mode,
                "sites": result_sites,
                "custom_site": custom_site,
                "seed": int(seed),
                "cell_size_m": float(cell_size),
                "field_eval_ok": field_eval_ok,
                "field_eval_message": field_eval_message,
                "field_eval_log": field_eval_log,
                "command": invocation,
                "stdout": completed.stdout[-6000:],
            }

result = st.session_state.get("campos_run")
if result:
    st.subheader("Results")
    st.write(
        f"**Mode:** {result['mode']} · **Sites:** {', '.join(result['sites'])} · "
        f"**Seed:** {result['seed']} · **Grid:** {result['cell_size_m']:g} m"
    )
    if result["custom_site"]:
        st.info("Custom geometry and layout were supplied by you. Simulation output alone is not field validation.")
    if result.get("field_eval_message"):
        if result.get("field_eval_ok"):
            st.info(result["field_eval_message"])
        else:
            st.warning(result["field_eval_message"])
        if result.get("field_eval_log"):
            with st.expander("Field-evaluation diagnostics"):
                st.code(result["field_eval_log"])
    if result.get("field_metrics"):
        metrics = result["field_metrics"]
        st.subheader("Catch-can holdout diagnostics")
        st.caption("Descriptive error metrics in millimetres; these are not a universal pass/fail certification.")
        metric_columns = st.columns(4)
        metric_columns[0].metric("Holdout observations", str(metrics.get("n", "—")))
        metric_columns[1].metric("RMSE (mm)", f"{metrics['rmse_mm']:.3f}" if metrics.get("rmse_mm") is not None else "—")
        metric_columns[2].metric("MAE (mm)", f"{metrics['mae_mm']:.3f}" if metrics.get("mae_mm") is not None else "—")
        metric_columns[3].metric(
            "Bias (mm)",
            f"{metrics['bias_mm_predicted_minus_measured']:.3f}"
            if metrics.get("bias_mm_predicted_minus_measured") is not None else "—",
        )
    if result.get("ai_eval_message"):
        if result.get("ai_eval_ok"):
            st.info(result["ai_eval_message"])
        else:
            st.warning(result["ai_eval_message"])
        if result.get("ai_eval_log"):
            with st.expander("AI correction diagnostics"):
                st.code(result["ai_eval_log"])
    if result.get("ai_summary"):
        summary = result["ai_summary"]
        baseline = summary.get("holdout_baseline_metrics", {})
        corrected = summary.get("holdout_ai_corrected_metrics", {})
        st.subheader("Experimental AI residual-correction comparison")
        st.caption("The GP is fitted on calibration rows only. Holdout metrics are for evaluation and must not be used repeatedly to tune the model.")
        ai_columns = st.columns(4)
        ai_columns[0].metric("Physical RMSE (mm)", f"{baseline['rmse_mm']:.3f}" if baseline.get("rmse_mm") is not None else "—")
        ai_columns[1].metric("AI-corrected RMSE (mm)", f"{corrected['rmse_mm']:.3f}" if corrected.get("rmse_mm") is not None else "—")
        delta = summary.get("holdout_rmse_change_mm_corrected_minus_baseline")
        ai_columns[2].metric("RMSE change (mm)", f"{delta:+.3f}" if isinstance(delta, (int, float)) else "—")
        coverage = summary.get("holdout_ai_95pct_interval_empirical_coverage")
        ai_columns[3].metric("Nominal 95% interval coverage", f"{100 * coverage:.1f}%" if isinstance(coverage, (int, float)) else "—")
    if "results_fixed.csv" in result["artifacts"] and "results_movable.csv" in result["artifacts"]:
        left, right = st.columns(2)
        for column, title, filename in (
            (left, "Fixed-position layout", "results_fixed.csv"),
            (right, "Movable-head layout", "results_movable.csv"),
        ):
            with column:
                st.markdown(f"**{title}**")
                rows = result["tables"].get(filename, [])
                if rows:
                    st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        for filename, rows in result["tables"].items():
            if rows:
                st.markdown(f"**{filename}**")
                st.dataframe(rows, use_container_width=True, hide_index=True)

    images = [(name, data) for name, data in result["artifacts"].items() if name.lower().endswith(".png")]
    if images:
        st.subheader("Generated plots")
        for name, data in images:
            with st.expander(name, expanded=(len(images) <= 2)):
                st.image(data, caption=name, use_container_width=True)

    st.subheader("Download outputs")
    buttons = st.columns(3)
    downloadable = [
        (name, data) for name, data in result["artifacts"].items()
        if name.endswith((".csv", ".json", ".png", ".md", ".html"))
    ]
    for index, (name, data) in enumerate(downloadable):
        with buttons[index % len(buttons)]:
            st.download_button(
                label=f"Download {name}",
                data=data,
                file_name=name,
                mime="application/json" if name.endswith(".json") else
                     "text/csv" if name.endswith(".csv") else
                     "text/markdown" if name.endswith(".md") else
                     "text/html" if name.endswith(".html") else
                     "image/png" if name.endswith(".png") else "application/octet-stream",
                key=f"download-{name}",
                use_container_width=True,
            )
    with st.expander("Execution details"):
        st.code(" ".join(result["command"]))
        st.text(result["stdout"])
else:
    st.info("Choose a synthetic site and click **Run simulation**. No field observations or AI training data are required.")
