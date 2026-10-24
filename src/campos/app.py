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
    polygon_upload = heads_upload = protected_upload = None
    if custom_site:
        polygon_upload = st.file_uploader("Lawn polygon CSV (x_m,y_m)", type=["csv"], key="lawn-polygon")
        heads_upload = st.file_uploader(
            "Sprinkler layout CSV (x_m,y_m,radius_m,start_angle_deg,arc_width_deg)",
            type=["csv"],
            key="sprinkler-layout",
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
            if completed.returncode:
                st.error("The simulation failed. No successful result is being shown.")
                st.code((completed.stderr or completed.stdout)[-12000:])
                st.stop()

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
            st.session_state["campos_run"] = {
                "artifacts": artifacts,
                "tables": tables,
                "mode": mode,
                "sites": result_sites,
                "custom_site": custom_site,
                "seed": int(seed),
                "cell_size_m": float(cell_size),
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
        st.info("Custom geometry and layout were supplied by you. This simulation still requires independent field validation before real-world use.")
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
