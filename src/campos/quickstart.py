"""One-command synthetic demo and self-contained HTML launch page for campOS."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys


LIMITATIONS = [
    "This starter run uses built-in synthetic lawn geometry, not a surveyed site.",
    "Simulation metrics are model-defined proxies; they are not field measurements or guaranteed water savings.",
    "Wind, drift, pressure losses, evaporation, soil response, and other site effects are not fully modelled.",
    "Do not use this output as an installation instruction or certified engineering design.",
]


def build_index(outdir: Path, manifest: dict) -> Path:
    files = sorted(
        p for p in outdir.iterdir()
        if p.is_file() and p.name not in {"index.html", "quickstart_manifest.json"}
    )
    artifact_rows = "".join(
        "<tr><td><a href=\"{}\">{}</a></td><td>{}</td></tr>".format(
            html.escape(p.name, quote=True),
            html.escape(p.name),
            f"{p.stat().st_size:,} bytes",
        )
        for p in files
    ) or '<tr><td colspan="2">No output files were generated.</td></tr>'

    metric_table = ""
    results_path = outdir / "results_movable.csv"
    if results_path.is_file():
        with results_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        preferred = [
            "site", "area_m2", "sprinkler_count", "baseline_AR", "optimized_AR",
            "baseline_CU", "optimized_CU", "baseline_overspray_pct_of_own_water",
            "optimized_overspray_pct_of_own_water", "baseline_dry_area_pct",
            "optimized_dry_area_pct",
        ]
        headers = [key for key in preferred if rows and key in rows[0]]
        if headers:
            th = "".join(f"<th>{html.escape(key)}</th>" for key in headers)
            trs = "".join(
                "<tr>" + "".join(
                    f"<td>{html.escape(str(row.get(key, '')))}</td>" for key in headers
                ) + "</tr>"
                for row in rows
            )
            metric_table = (
                "<h2>Modelled result preview</h2>"
                "<p>These values are simulator outputs, not measured field outcomes.</p>"
                f"<div class=\"table-wrap\"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>"
            )

    caveats = "".join(f"<li>{html.escape(item)}</li>" for item in LIMITATIONS)
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>campOS quickstart report</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1rem; line-height: 1.55; }}
header {{ padding: 1.2rem; border: 1px solid #8886; border-radius: 1rem; }}
.notice {{ padding: 1rem; border-left: 4px solid #c88719; background: #8881; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
th, td {{ text-align: left; padding: .55rem; border-bottom: 1px solid #8885; }}
code {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
<h1>campOS quickstart</h1>
<p>One-command synthetic demo. Run finished at {html.escape(manifest["finished_at_utc"])}.</p>
<p><strong>Mode:</strong> {html.escape(manifest["mode"])} ·
<strong>Sites:</strong> {html.escape(", ".join(manifest["sites"]))} ·
<strong>Quick mode:</strong> {html.escape(str(manifest["quick"]))}</p>
</header>
<div class="notice"><strong>Important limitation:</strong> This is a software demo, not a field-validated irrigation design. Synthetic success does not establish real-world water savings or road-wetting reduction.</div>
{metric_table}
<h2>Generated files</h2>
<table><thead><tr><th>Artifact</th><th>Size</th></tr></thead><tbody>{artifact_rows}</tbody></table>
<h2>Known limitations</h2><ul>{caveats}</ul>
<h2>Next step when a real site becomes available</h2>
<p>Collect a surveyed lawn boundary, existing head layout, manufacturer precipitation data, protected road/sidewalk geometry, and catch-can observations. Keep raw observations unchanged and reserve entire runs for independent holdout evaluation.</p>
<p>Machine-readable run details: <a href="quickstart_manifest.json">quickstart_manifest.json</a>.</p>
</body></html>
"""
    target = outdir / "index.html"
    target.write_text(document, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a no-data-required synthetic campOS demo and create a browsable HTML report."
    )
    parser.add_argument("--outdir", default="out/campos-quickstart", help="Output directory (default: out/campos-quickstart)")
    parser.add_argument(
        "--mode", choices=("movable", "fixed", "pareto-movable", "pareto-fixed"),
        default="movable", help="Optimization mode (default: movable)",
    )
    parser.add_argument("--sites", nargs="+", choices=("A", "B", "C", "D", "E"), default=["A"])
    parser.add_argument("--full", action="store_true", help="Run without the quick smoke-test settings")
    args = parser.parse_args(argv)

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    command = shutil.which("campos-sim")
    if command:
        invocation = [command]
    else:
        invocation = [sys.executable, "-m", "campos.campos_sim"]
    invocation += ["--mode", args.mode, "--sites", *args.sites, "--outdir", str(outdir)]
    if not args.full:
        invocation.append("--quick")

    print("campOS quickstart: running a synthetic demonstration.", flush=True)
    print("Command:", " ".join(invocation), flush=True)
    try:
        subprocess.run(invocation, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"campOS simulation failed: {exc}", file=sys.stderr)
        print("No success report was written. Check the error above and retry.", file=sys.stderr)
        return 2

    manifest = {
        "product": "campOS",
        "workflow": "quickstart-synthetic-demo",
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "sites": args.sites,
        "quick": not args.full,
        "command": invocation,
        "output_directory": str(outdir),
        "limitations": LIMITATIONS,
        "status": "simulation_completed_not_field_validated",
    }
    (outdir / "quickstart_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    report = build_index(outdir, manifest)
    print(f"Quickstart report: {report}", flush=True)
    print("This synthetic run is not a field-validated design.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
