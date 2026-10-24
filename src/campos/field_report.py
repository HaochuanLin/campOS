"""Build a readable HTML and Markdown report from campOS field-evaluation metrics."""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path


def md_escape(value: object) -> str:
    """Escape untrusted values before placing them in Markdown prose or tables."""
    return (
        str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    )


def fmt(value):
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:.4g}" if math.isfinite(number) else "n/a"


def build_report(metrics_path: Path) -> tuple[str, str]:
    report = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = report.get("metrics", {}).get("metrics", {})
    zone_metrics = report.get("metrics_by_zone", {})
    limitations = report.get("limitations", [])
    mismatches = report.get("zone_geometry_mismatch_can_ids", [])
    zone_gate = report.get("zone_geometry_gate") or {}
    zone_gate_passed = zone_gate.get("passed")
    zone_gate_passed_text = "not evaluated" if zone_gate_passed is None else str(zone_gate_passed)

    md = [
        "# campOS field-evaluation report",
        "",
        "**Warning:** this is a descriptive model-to-observation comparison, not a certification of model validity, an installation recommendation, or evidence of water savings.",
        "",
        "## Overall paired-error metrics",
        "",
        "| Split | n | Bias (mm) | MAE (mm) | RMSE (mm) | Max absolute error (mm) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, group in (
        ("Calibration", metrics.get("calibration") or {}),
        ("Holdout", metrics.get("holdout") or {}),
        ("All", metrics.get("all") or {}),
    ):
        md.append(
            f"| {name} | {group.get('n', 'n/a')} | "
            f"{fmt(group.get('bias_mm_predicted_minus_measured'))} | "
            f"{fmt(group.get('mae_mm'))} | {fmt(group.get('rmse_mm'))} | "
            f"{fmt(group.get('max_absolute_error_mm'))} |"
        )
    md += [
        "",
        "## Results by catch-can zone",
        "",
        "| Zone | n | Holdout n | Holdout bias (mm) | Holdout MAE (mm) | Holdout RMSE (mm) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for zone, values in sorted(zone_metrics.items()):
        holdout = values.get("holdout") or {}
        md.append(
            f"| {zone} | {values.get('n', 'n/a')} | {values.get('holdout_n', 0)} | "
            f"{fmt(holdout.get('bias_mm_predicted_minus_measured'))} | "
            f"{fmt(holdout.get('mae_mm'))} | {fmt(holdout.get('rmse_mm'))} |"
        )
    md += [
        "",
        "## Input provenance",
        "",
        f"- Status: {report.get('status', 'unknown')}",
        f"- Sprinkler heads: {report.get('n_sprinkler_heads', 'n/a')}",
        f"- Valid observations: {report.get('n_valid_observations', 'n/a')}",
        f"- Per-head flow rates (L/min): {json.dumps(report.get('flow_lpm_per_head', []))}",
        f"- Input SHA-256 hashes: {json.dumps(report.get('input_sha256', {}), sort_keys=True)}",
        f"- Software metadata: {json.dumps(report.get('software', {}), sort_keys=True)}",
        f"- Radial-profile SHA-256: {report.get('radial_profile_csv_sha256') or 'not supplied'}",
        "",
        "## Geometry / zone-label checks",
        "",
        f"- Zone/polygon mismatches: {report.get('zone_geometry_mismatch_count', 0)}",
        f"- Strict zone-geometry gate enabled: {zone_gate.get('enabled', False)}",
        f"- Strict zone-geometry gate passed: {zone_gate_passed_text}",
        f"- Affected catch-can IDs: {', '.join(md_escape(item) for item in mismatches) if mismatches else 'none'}",
        "",
        "## Limitations",
        "",
    ]
    md.extend(f"- {item}" for item in limitations)
    md += [
        "",
        "Do not infer a pass/fail conclusion unless a site-specific acceptance threshold was documented before inspecting holdout results. A split label alone cannot prove independence.",
        "",
    ]
    acceptance = report.get("acceptance_assessment")
    if acceptance:
        md.extend([
            "## Pre-registered holdout acceptance assessment",
            "",
            f"- Status: {acceptance.get('status', 'unknown')}",
            f"- Note: {acceptance.get('note', '')}",
            f"- Threshold config SHA-256: {report.get('acceptance_thresholds_json_sha256') or 'not recorded'}",
            "",
            "| Metric | Observed | Limit | Passed |",
            "|---|---:|---:|:---:|",
        ])
        for check in acceptance.get("checks", []):
            md.append(
                f"| {check.get('metric', 'unknown')} | {fmt(check.get('observed'))} | "
                f"{fmt(check.get('limit'))} | {'yes' if check.get('passed') else 'no'} |"
            )
        md.append("")

    markdown = chr(10).join(md)

    def esc(value):
        return html.escape(str(value))

    def table_rows(groups):
        rows = []
        for name, group in groups:
            rows.append("<tr>" + "".join([
                f"<td>{esc(name)}</td>",
                f"<td>{esc(group.get('n', 'n/a'))}</td>",
                f"<td>{esc(fmt(group.get('bias_mm_predicted_minus_measured')))}</td>",
                f"<td>{esc(fmt(group.get('mae_mm')))}</td>",
                f"<td>{esc(fmt(group.get('rmse_mm')))}</td>",
                f"<td>{esc(fmt(group.get('max_absolute_error_mm')))}</td>",
            ]) + "</tr>")
        return "".join(rows)

    overall = [
        ("Calibration", metrics.get("calibration") or {}),
        ("Holdout", metrics.get("holdout") or {}),
        ("All", metrics.get("all") or {}),
    ]
    zone_rows = []
    for zone, values in sorted(zone_metrics.items()):
        holdout = values.get("holdout") or {}
        zone_rows.append("<tr>" + "".join([
            f"<td>{esc(zone)}</td>",
            f"<td>{esc(values.get('n', 'n/a'))}</td>",
            f"<td>{esc(values.get('holdout_n', 0))}</td>",
            f"<td>{esc(fmt(holdout.get('bias_mm_predicted_minus_measured')))}</td>",
            f"<td>{esc(fmt(holdout.get('mae_mm')))}</td>",
            f"<td>{esc(fmt(holdout.get('rmse_mm')))}</td>",
        ]) + "</tr>")
    software = report.get("software", {})
    software_html = "".join(
        f"<li>{esc(key)}: <code>{esc(value)}</code></li>"
        for key, value in software.items() if key != "source_sha256"
    )
    for key, value in software.get("source_sha256", {}).items():
        software_html += f"<li>{esc(key)} SHA-256: <code>{esc(value)}</code></li>"
    limitations_html = "".join(f"<li>{esc(item)}</li>" for item in limitations)
    acceptance_html = ""
    if acceptance:
        acceptance_rows = "".join(
            "<tr>" + "".join([
                f"<td>{esc(check.get('metric', 'unknown'))}</td>",
                f"<td>{esc(fmt(check.get('observed')))}</td>",
                f"<td>{esc(fmt(check.get('limit')))}</td>",
                f"<td>{'yes' if check.get('passed') else 'no'}</td>",
            ]) + "</tr>"
            for check in acceptance.get("checks", [])
        )
        acceptance_html = (
            "<h2>Pre-registered holdout acceptance assessment</h2>"
            f"<p><strong>Status:</strong> {esc(acceptance.get('status', 'unknown'))}</p>"
            f"<p>{esc(acceptance.get('note', ''))}</p>"
            f"<p>Threshold config SHA-256: <code>{esc(report.get('acceptance_thresholds_json_sha256') or 'not recorded')}</code></p>"
            "<table><thead><tr><th>Metric</th><th>Observed</th><th>Limit</th>"
            f"<th>Passed</th></tr></thead><tbody>{acceptance_rows}</tbody></table>"
        )
    hashes_html = "".join(
        f"<li>{esc(key)}: <code>{esc(value)}</code></li>"
        for key, value in report.get("input_sha256", {}).items()
    )
    html_report = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>campOS field-evaluation report</title>
<style>
body{{font:16px/1.55 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#202124}}
h1,h2{{line-height:1.2}} .warning{{border-left:4px solid #b26a00;padding:.75rem 1rem;background:#fff8e8}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-variant-numeric:tabular-nums}}th,td{{border:1px solid #ddd;padding:.55rem;text-align:left}}th{{background:#f4f4f4}}code{{overflow-wrap:anywhere}}
</style></head><body>
<h1>campOS field-evaluation report</h1>
<p><strong>Status:</strong> {esc(report.get('status', 'unknown'))}</p>
<p class="warning">This is a descriptive model-to-observation comparison, not a certification of model validity, an installation recommendation, or evidence of water savings.</p>
<h2>Overall paired-error metrics</h2>
<table><thead><tr><th>Split</th><th>n</th><th>Bias (mm)</th><th>MAE (mm)</th><th>RMSE (mm)</th><th>Max absolute error (mm)</th></tr></thead><tbody>{table_rows(overall)}</tbody></table>
<h2>Results by catch-can zone</h2>
<table><thead><tr><th>Zone</th><th>n</th><th>Holdout n</th><th>Holdout bias (mm)</th><th>Holdout MAE (mm)</th><th>Holdout RMSE (mm)</th></tr></thead><tbody>{''.join(zone_rows)}</tbody></table>
<h2>Input provenance</h2>
<ul><li>Sprinkler heads: {esc(report.get('n_sprinkler_heads', 'n/a'))}</li><li>Valid observations: {esc(report.get('n_valid_observations', 'n/a'))}</li><li>Per-head flow rates (L/min): <code>{esc(json.dumps(report.get('flow_lpm_per_head', [])))}</code></li><li>Input hashes:</li>{hashes_html}{software_html}</ul>
<h2>Geometry / zone-label checks</h2>
<p>Zone/polygon mismatches: {esc(report.get('zone_geometry_mismatch_count', 0))}; strict geometry gate enabled: {esc(zone_gate.get('enabled', False))}; strict geometry gate passed: {esc(zone_gate_passed_text)}; affected catch-can IDs: {esc(', '.join(mismatches) if mismatches else 'none')}.</p>
{acceptance_html}
<h2>Limitations</h2><ul>{limitations_html}</ul>
<p>Do not infer a pass/fail conclusion unless a site-specific acceptance threshold was documented before inspecting holdout results. A split label alone cannot prove independence.</p>
</body></html>"""
    return markdown, html_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=Path, required=True, help="field_evaluation_metrics.json")
    parser.add_argument("--outdir", type=Path, default=None, help="output directory; defaults to input file directory")
    args = parser.parse_args()
    try:
        markdown, html_report = build_report(args.input_json)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(f"cannot build field report: {exc}")
    outdir = args.outdir or args.input_json.parent
    outdir.mkdir(parents=True, exist_ok=True)
    md_path = outdir / "field_evaluation_report.md"
    html_path = outdir / "field_evaluation_report.html"
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_report, encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
