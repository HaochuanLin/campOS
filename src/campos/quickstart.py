"""One-command synthetic demo and self-contained HTML launch page for campOS."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import sys


LIMITATIONS = [
    "This starter run uses built-in synthetic lawn geometry, not a surveyed site.",
    "Simulation metrics are model-defined proxies; they are not field measurements or guaranteed water savings.",
    "Wind, drift, pressure losses, evaporation, soil response, and other site effects are not fully modelled.",
    "Do not use this output as an installation instruction or certified engineering design.",
]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_checksums(
    outdir: Path, include_names: set[str] | None = None
) -> dict[str, dict[str, int | str]]:
    """Hash generated artifacts, excluding the self-referential manifest and HTML index."""
    excluded = {"index.html", "quickstart_manifest.json"}
    artifacts = {}
    for path in sorted(outdir.iterdir()):
        if (
            path.is_file() and not path.is_symlink() and path.name not in excluded
            and (include_names is None or path.name in include_names)
        ):
            artifacts[path.name] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
    return artifacts


def build_index(outdir: Path, manifest: dict) -> Path:
    artifact_checksums_in_manifest = manifest.get("artifact_checksums")
    artifact_names = (
        set(artifact_checksums_in_manifest)
        if isinstance(artifact_checksums_in_manifest, dict) else None
    )
    files = sorted(
        p for p in outdir.iterdir()
        if p.is_file()
        and not p.is_symlink()
        and p.name not in {"index.html", "quickstart_manifest.json"}
        and (artifact_names is None or p.name in artifact_names)
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
    if (
        results_path.is_file() and not results_path.is_symlink()
        and (artifact_names is None or "results_movable.csv" in artifact_names)
    ):
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

    comparison_table = ""
    comparison_rows = []
    for mode, filename in (("fixed", "results_fixed.csv"), ("movable", "results_movable.csv")):
        path = outdir / filename
        if path.is_file() and not path.is_symlink() and (artifact_names is None or filename in artifact_names):
            with path.open(newline="", encoding="utf-8-sig") as f:
                comparison_rows.extend((mode, row) for row in csv.DictReader(f))
    if len({mode for mode, _ in comparison_rows}) == 2:
        columns = ("mode", "site", "baseline_AR", "optimized_AR", "optimized_overspray_pct_of_own_water", "optimized_CU", "optimized_dry_area_pct")
        th = "".join(f"<th>{html.escape(key)}</th>" for key in columns)
        trs = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(mode if key == 'mode' else row.get(key, '')))}</td>" for key in columns) + "</tr>"
            for mode, row in comparison_rows
        )
        comparison_table = "<h2>Fixed vs movable comparison</h2><p>Compare model-defined outcomes across the same synthetic site. Lower overspray is not guaranteed by a better AR score.</p><div class=\"table-wrap\"><table><thead><tr>" + th + "</tr></thead><tbody>" + trs + "</tbody></table></div>"

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
<strong>Seed:</strong> {html.escape(str(manifest.get("seed", "n/a")))} ·
<strong>Grid:</strong> {html.escape(str(manifest.get("cell_size_m", "n/a")))} m ·
<strong>Quick mode:</strong> {html.escape(str(manifest["quick"]))}</p>
</header>
<div class="notice"><strong>Important limitation:</strong> This is a software demo, not a field-validated irrigation design. Synthetic success does not establish real-world water savings or road-wetting reduction.</div>
{metric_table}
{comparison_table}
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
        "--mode", choices=("compare", "movable", "fixed", "pareto-movable", "pareto-fixed"),
        default="compare", help="Compare fixed and movable layouts (default: compare)",
    )
    parser.add_argument("--sites", nargs="+", choices=("A", "B", "C", "D", "E"), default=["A"])
    parser.add_argument("--seed", type=int, default=7, help="random seed shared by compared scenarios (default: 7)")
    parser.add_argument("--cell-size", type=float, default=0.5, help="simulation grid resolution in metres (default: 0.5)")
    parser.add_argument("--full", action="store_true", help="Run without the quick smoke-test settings")
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("--seed must be a non-negative integer")
    if not math.isfinite(args.cell_size) or args.cell_size <= 0:
        parser.error("--cell-size must be finite and greater than zero")

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    # Remove the previous success markers before starting a new run. If a
    # subprocess fails, an old report must not masquerade as this run's result.
    for summary_name in ("index.html", "quickstart_manifest.json"):
        summary_path = outdir / summary_name
        if summary_path.is_file() or summary_path.is_symlink():
            summary_path.unlink()
    command = shutil.which("campos-sim")
    base_command = [command] if command else [sys.executable, "-m", "campos.campos_sim"]
    modes = ["fixed", "movable"] if args.mode == "compare" else [args.mode]
    invocations = []
    before_artifacts = {}
    for path in outdir.iterdir():
        if path.is_file() and not path.is_symlink() and path.name not in {"index.html", "quickstart_manifest.json"}:
            stat = path.stat()
            before_artifacts[path.name] = (stat.st_size, stat.st_mtime_ns, sha256_file(path))
    print("campOS quickstart: running synthetic demonstration(s).", flush=True)
    try:
        for mode in modes:
            invocation = base_command + [
                "--mode", mode, "--sites", *args.sites,
                "--seed", str(args.seed), "--cell-size", str(args.cell_size),
                "--outdir", str(outdir),
            ]
            if not args.full:
                invocation.append("--quick")
            invocations.append(invocation)
            print("Command:", " ".join(invocation), flush=True)
            subprocess.run(invocation, check=True)
            metadata = outdir / "run_metadata.json"
            if args.mode == "compare" and metadata.is_file():
                (outdir / f"run_metadata_{mode}.json").write_text(metadata.read_text(encoding="utf-8"), encoding="utf-8")
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"campOS simulation failed: {exc}", file=sys.stderr)
        print("No success report was written. Check the error above and retry.", file=sys.stderr)
        return 2
    generated_names = set()
    for path in outdir.iterdir():
        if path.is_file() and not path.is_symlink() and path.name not in {"index.html", "quickstart_manifest.json"}:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns, sha256_file(path))
            if before_artifacts.get(path.name) != signature:
                generated_names.add(path.name)

    manifest = {
        "product": "campOS",
        "workflow": "quickstart-synthetic-demo",
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "runs": modes,
        "sites": args.sites,
        "seed": args.seed,
        "cell_size_m": args.cell_size,
        "quick": not args.full,
        "commands": invocations,
        "output_directory": str(outdir),
        "python_version": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}".strip(),
        "artifact_checksums": artifact_checksums(outdir, include_names=generated_names),
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
