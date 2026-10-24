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
    st.header("Demo setup")
    mode = st.selectbox(
        "Optimization mode",
        ["compare", "fixed", "movable", "pareto-fixed", "pareto-movable"],
        index=0,
        help="Compare runs fixed-position and movable-head modes using the same synthetic site.",
    )
    sites = st.multiselect("Synthetic sites", ["A", "B", "C", "D", "E"], default=["A"])
    full = st.checkbox("Run a longer search", value=False, help="May take substantially longer.")
    run = st.button("Run simulation", type="primary", disabled=not sites, use_container_width=True)

st.warning(
    "This demo needs no real data, but it does not fabricate field measurements. "
    "Its metrics cannot prove actual road wetting, field accuracy, or water savings."
)

if run:
    with st.spinner("Running campOS simulation and building the report…"):
        with tempfile.TemporaryDirectory(prefix="campos-ui-") as temporary:
            outdir = Path(temporary) / "results"
            command = shutil.which("campos-start")
            invocation = [command] if command else [sys.executable, "-m", "campos.quickstart"]
            invocation += ["--mode", mode, "--sites", *sites, "--outdir", str(outdir)]
            if full:
                invocation.append("--full")
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
                "sites": sites,
                "command": invocation,
                "stdout": completed.stdout[-6000:],
            }

result = st.session_state.get("campos_run")
if result:
    st.subheader("Results")
    st.write(f"**Mode:** {result['mode']} · **Sites:** {', '.join(result['sites'])}")
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
