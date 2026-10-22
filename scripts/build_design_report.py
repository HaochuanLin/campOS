#!/usr/bin/env python3
"""Build a self-contained HTML and Markdown report from a campOS run directory.

Reports summarize generated artifacts; they do not turn a synthetic simulation
into a validated design or infer water, cost, or payback savings.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
from pathlib import Path

CSV_FILES = (
    "results_movable.csv",
    "results_fixed.csv",
    "comparison_single_objective.csv",
    "pareto_movable.csv",
    "pareto_fixed.csv",
)
IMAGE_EXTENSIONS = {".png"}
LIMITATIONS = [
    "Built-in lawn geometries are synthetic unless the user independently supplies and documents a surveyed site.",
    "The default radial field is a uniform-depth null model; a radial-slope value is an illustrative assumption, not calibrated sprinkler physics.",
    "AR metric improvement is not a water-savings estimate. Annual water savings, operating cost savings, and payback are not estimated by this model.",
    "A Pareto front is an approximate result of a stochastic finite search, not a guaranteed global optimum.",
    "This report is a simulation summary, not an installation instruction, engineering recommendation, or independent field validation.",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def pretty_name(path: Path) -> str:
    return path.stem.replace("_", " ").replace("results ", "").title()


def selected_columns(headers: list[str], filename: str) -> list[str]:
    preferred = {
        "results_movable.csv": [
            "site", "area_m2", "sprinkler_count", "heads_moved", "heads_changed",
            "baseline_AR", "optimized_AR", "baseline_overspray_pct_of_own_water",
            "optimized_overspray_pct_of_own_water", "baseline_CU", "optimized_CU",
            "baseline_dry_area_pct", "optimized_dry_area_pct", "AR_metric_improvement_pct",
            "annual_water_saving_m3_not_estimated", "annual_cost_saving_CNY_not_estimated",
            "retrofit_cost_CNY_placeholder", "payback_years_not_estimated",
        ],
        "results_fixed.csv": [
            "site", "area_m2", "sprinkler_count", "heads_moved", "heads_changed",
            "baseline_AR", "optimized_AR", "baseline_overspray_pct_of_own_water",
            "optimized_overspray_pct_of_own_water", "baseline_CU", "optimized_CU",
            "baseline_dry_area_pct", "optimized_dry_area_pct", "AR_metric_improvement_pct",
            "annual_water_saving_m3_not_estimated", "annual_cost_saving_CNY_not_estimated",
            "retrofit_cost_CNY_placeholder", "payback_years_not_estimated",
        ],
        "comparison_single_objective.csv": [
            "mode", "site", "AR", "overspray_pct_of_own_water", "CU", "dry_area_pct",
            "AR_metric_improvement_pct", "heads_moved", "heads_changed",
            "retrofit_cost_CNY_placeholder", "payback_years_not_estimated",
        ],
    }
    return [name for name in preferred.get(filename, headers) if name in headers]


def md_table(headers: list[str], rows: list[dict[str, str]]) -> str:
    if not headers:
        return "_No columns available._"
    clean = lambda value: str(value or "").replace("|", "\\|").replace("\n", " ")
    lines = [
        "| " + " | ".join(clean(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(clean(row.get(h, "")) for h in headers) + " |" for row in rows)
    return "\n".join(lines)


def build_report(run_dir: Path, html_path: Path, md_path: Path) -> None:
    metadata_path = run_dir / "run_metadata.json"
    if not metadata_path.is_file():
        raise SystemExit(f"Missing {metadata_path}; point --input-dir at a simulator output directory.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    tables = []
    for filename in CSV_FILES:
        path = run_dir / filename
        if path.is_file():
            rows = load_csv(path)
            if rows:
                headers = selected_columns(list(rows[0]), filename)
                tables.append((filename, headers, rows))

    images = sorted(p for p in run_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    warnings = metadata.get("limitations", [])
    cfg = metadata.get("config", {})
    policy = metadata.get("optimization_policy", {})
    radial = metadata.get("radial_distribution", {})
    hydraulic = metadata.get("hydraulic_performance", {})
    profile = metadata.get("radial_profile", {})
    site_input = metadata.get("site_input", {})

    md = [
        "# campOS simulation report",
        "",
        "> Simulation summary only. Not a field-validated design or installation instruction.",
        "",
        "## Run provenance",
        "",
        f"- Project version: {metadata.get('project_version', 'not recorded')}",
        f"- Python: {metadata.get('python_version', 'not recorded')}",
        f"- NumPy: {metadata.get('numpy_version', 'not recorded')}",
        f"- Matplotlib: {metadata.get('matplotlib_version', 'not recorded')}",
        f"- Modes: {', '.join(metadata.get('selected_modes', [])) or 'not recorded'}",
        f"- Sites: {', '.join(metadata.get('selected_sites', [])) or 'not recorded'}",
        f"- Seed: {cfg.get('seed', 'not recorded')}; grid cell: {cfg.get('cell', 'not recorded')} m",
        f"- Radial model: {radial.get('model', 'not recorded')}; slope: {radial.get('radial_slope', 'not recorded')}",
        f"- Radial profile status: {profile.get('status', 'not recorded')}",
        f"- Hydraulic performance status: {hydraulic.get('status', 'not recorded')}",
        f"- Site input status: {site_input.get('status', 'not recorded')}",
        f"- Polygon CSV SHA-256: {site_input.get('polygon_sha256', 'not supplied')}",
        f"- Sprinkler CSV SHA-256: {site_input.get('heads_sha256', 'not supplied')}",
        f"- Polygon vertices: {site_input.get('polygon_vertex_count', 'not recorded')}",
        f"- Initial sprinkler count: {site_input.get('initial_head_count', 'generated or not recorded')}",
        f"- Coordinate units: {site_input.get('coordinate_units', 'not recorded')}",
        "",
        "## Optimization policy",
        "",
        f"- Legacy modes: {', '.join(policy.get('legacy_modes', [])) or 'not recorded'}",
        f"- Pareto objectives: {json.dumps(policy.get('pareto_objectives', {}), ensure_ascii=False)}",
        f"- Dry-area limit: {policy.get('dry_fraction_limit', 'not recorded')}",
        f"- Target factor: {policy.get('target_factor', 'not recorded')}",
        f"- CU-drop budget: {policy.get('cu_drop_budget', 'not recorded')}",
        f"- Pareto search weights: {policy.get('pareto_overspray_weights', 'not recorded')}",
        "",
        "## Results",
        "",
    ]
    if not tables:
        md.append("No recognized result CSVs were found in this run directory.")
        md.append("")
    for filename, headers, rows in tables:
        md.extend([f"### {pretty_name(Path(filename))}", "", md_table(headers, rows), ""])
    md.extend(["## Figures", ""])
    md.extend([f"- {path.name}" for path in images] or ["- No PNG figures were found."])
    md.extend(["", "## Interpretation limits", ""])
    md.extend([f"- {item}" for item in LIMITATIONS])
    md.extend([
        "",
        "The report records what this run produced; it does not certify suitability for a real site. Before field use, independently survey geometry, calibrate the exact sprinkler/nozzle and operating pressure, and validate predictions against held-out measurements.",
        "",
    ])
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md), encoding="utf-8")

    esc = html.escape
    sections = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>campOS simulation report</title>",
        "<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#202124}h1,h2,h3{line-height:1.2} .notice{border-left:4px solid #b45309;padding:.75rem 1rem;background:#fff7ed} .meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.5rem} .meta div{padding:.65rem;background:#f3f4f6;border-radius:.4rem;overflow-wrap:anywhere} .table-wrap{overflow-x:auto;margin:1rem 0}table{border-collapse:collapse;font-size:.88rem;white-space:nowrap}th,td{padding:.45rem .6rem;border:1px solid #d1d5db;text-align:left}th{background:#f3f4f6}figure{margin:1.5rem 0}figure img{max-width:100%;height:auto;border:1px solid #ddd}figcaption{color:#555;font-size:.9rem}code{overflow-wrap:anywhere}</style></head><body>",
        "<h1>campOS simulation report</h1>",
        "<p class=\"notice\"><strong>Important:</strong> This is a simulation summary only. It is not field-validated, not an installation instruction, and not a guarantee of water or cost savings.</p>",
        "<h2>Run provenance</h2><div class=\"meta\">",
    ]
    provenance = [
        ("Project version", metadata.get("project_version", "not recorded")),
        ("Python", metadata.get("python_version", "not recorded")),
        ("NumPy", metadata.get("numpy_version", "not recorded")),
        ("Matplotlib", metadata.get("matplotlib_version", "not recorded")),
        ("Modes", ", ".join(metadata.get("selected_modes", [])) or "not recorded"),
        ("Sites", ", ".join(metadata.get("selected_sites", [])) or "not recorded"),
        ("Seed", cfg.get("seed", "not recorded")),
        ("Grid cell (m)", cfg.get("cell", "not recorded")),
        ("Radial model", radial.get("model", "not recorded")),
        ("Radial slope", radial.get("radial_slope", "not recorded")),
        ("Radial profile", profile.get("status", "not recorded")),
        ("Hydraulic performance", hydraulic.get("status", "not recorded")),
        ("Site input", site_input.get("status", "not recorded")),
        ("Polygon CSV SHA-256", site_input.get("polygon_sha256", "not supplied")),
        ("Sprinkler CSV SHA-256", site_input.get("heads_sha256", "not supplied")),
        ("Polygon vertices", site_input.get("polygon_vertex_count", "not recorded")),
        ("Initial sprinkler count", site_input.get("initial_head_count", "generated or not recorded")),
        ("Coordinate units", site_input.get("coordinate_units", "not recorded")),
    ]
    for label, value in provenance:
        sections.append(f"<div><strong>{esc(str(label))}</strong><br>{esc(str(value))}</div>")
    sections.append("</div><h2>Optimization policy</h2><ul>")
    for label, value in [
        ("Legacy modes", ", ".join(policy.get("legacy_modes", [])) or "not recorded"),
        ("Pareto objectives", json.dumps(policy.get("pareto_objectives", {}), ensure_ascii=False)),
        ("Dry-area limit", policy.get("dry_fraction_limit", "not recorded")),
        ("Target factor", policy.get("target_factor", "not recorded")),
        ("CU-drop budget", policy.get("cu_drop_budget", "not recorded")),
        ("Pareto search weights", policy.get("pareto_overspray_weights", "not recorded")),
    ]:
        sections.append(f"<li><strong>{esc(str(label))}:</strong> {esc(str(value))}</li>")
    sections.append("</ul><h2>Results</h2>")
    if not tables:
        sections.append("<p>No recognized result CSVs were found in this run directory.</p>")
    for filename, headers, rows in tables:
        sections.append(f"<h3>{esc(pretty_name(Path(filename)))}</h3><div class=\"table-wrap\"><table><thead><tr>")
        sections.extend(f"<th>{esc(h)}</th>" for h in headers)
        sections.append("</tr></thead><tbody>")
        for row in rows:
            sections.append("<tr>" + "".join(f"<td>{esc(str(row.get(h, '')))}</td>" for h in headers) + "</tr>")
        sections.append("</tbody></table></div>")
    sections.append("<h2>Figures</h2>")
    if not images:
        sections.append("<p>No PNG figures were found.</p>")
    for path in images:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        sections.append(f"<figure><img src=\"data:image/png;base64,{data}\" alt=\"{esc(path.name)}\"><figcaption>{esc(path.name)}</figcaption></figure>")
    sections.append("<h2>Interpretation limits</h2><ul>")
    sections.extend(f"<li>{esc(item)}</li>" for item in LIMITATIONS)
    sections.append("</ul><p>Before field use, independently survey geometry, calibrate the exact sprinkler/nozzle and operating pressure, and validate predictions against held-out measurements.</p></body></html>")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text("\n".join(sections), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="simulator output directory containing run_metadata.json")
    parser.add_argument("--html", default=None, help="HTML report path (default: <input-dir>/design_report.html)")
    parser.add_argument("--markdown", default=None, help="Markdown report path (default: <input-dir>/design_report.md)")
    args = parser.parse_args()
    run_dir = Path(args.input_dir).resolve()
    build_report(
        run_dir,
        Path(args.html).resolve() if args.html else run_dir / "design_report.html",
        Path(args.markdown).resolve() if args.markdown else run_dir / "design_report.md",
    )
    print(f"HTML report: {Path(args.html).resolve() if args.html else run_dir / 'design_report.html'}")
    print(f"Markdown report: {Path(args.markdown).resolve() if args.markdown else run_dir / 'design_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
