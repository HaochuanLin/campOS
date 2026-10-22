#!/usr/bin/env python3
"""Run named campOS scenarios while holding site/model inputs constant."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SHARED_KEYS = (
    "sites", "polygon_csv", "heads_csv", "seed", "cell_size", "radial_slope",
    "profile_csv", "performance_csv", "pressure_kpa", "quick",
)
OVERRIDE_KEYS = {"mode", "dry_fraction_limit", "target_factor", "cu_drop_budget", "pareto_weights"}
SUPPORTED_MODES = {"movable", "fixed", "pareto-movable", "pareto-fixed"}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def validate_spec(spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("shared"), dict):
        raise ValueError("comparison JSON must contain an object named 'shared'")
    scenarios = spec.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        raise ValueError("'scenarios' must contain at least two named scenarios")
    shared = spec["shared"]
    unknown_shared = sorted(set(shared) - (set(SHARED_KEYS) | OVERRIDE_KEYS))
    if unknown_shared:
        raise ValueError(f"unknown shared configuration key(s): {', '.join(unknown_shared)}")
    names = set()
    normalized = []
    for item in scenarios:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("each scenario needs a non-empty name")
        name = item["name"].strip()
        if name in names:
            raise ValueError(f"duplicate scenario name: {name}")
        names.add(name)
        overrides = item.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError(f"overrides for {name!r} must be an object")
        unknown = sorted(set(overrides) - OVERRIDE_KEYS)
        if unknown:
            raise ValueError(f"unsupported override(s) for {name!r}: {', '.join(unknown)}")
        config = dict(shared)
        config.update(overrides)
        mode = config.get("mode", "fixed")
        if isinstance(mode, list):
            if len(mode) != 1:
                raise ValueError(f"scenario {name!r} must run exactly one mode")
            mode = mode[0]
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"scenario {name!r} mode must be one of {sorted(SUPPORTED_MODES)}")
        config["mode"] = [mode]
        normalized.append((name, mode, config))
    # Inputs that determine geometry, physical assumptions, or stochastic comparability
    # are shared by construction and cannot be overridden per scenario.
    return shared, normalized


def summarize(name, mode, run_dir, config):
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    rows = []
    if mode in {"movable", "fixed"}:
        rows = read_csv(run_dir / f"results_{mode}.csv")
        for row in rows:
            row["scenario"] = name
            row["mode"] = mode
            row["seed"] = config.get("seed", metadata["config"]["seed"])
            row["cell_size_m"] = metadata["config"]["cell"]
            row["radial_slope"] = metadata["config"].get("radial_slope", 0)
            row["status"] = "completed"
    else:
        path = run_dir / ("pareto_movable.csv" if mode == "pareto-movable" else "pareto_fixed.csv")
        for row in read_csv(path):
            if row.get("point_type") != "PARETO":
                continue
            if str(row.get("selected_tradeoff", "")).upper() != "YES":
                continue
            row = dict(row)
            row.update({
                "scenario": name, "mode": mode,
                "seed": config.get("seed", metadata["config"]["seed"]),
                "cell_size_m": metadata["config"]["cell"],
                "radial_slope": metadata["config"].get("radial_slope", 0),
                "status": "selected_feasible_tradeoff",
            })
            rows.append(row)
    for row in rows:
        row["site_input_status"] = metadata.get("site_input", {}).get("status", "not recorded")
        row["radial_field_status"] = metadata.get("radial_profile", {}).get("status", "not recorded")
        row["hydraulic_status"] = metadata.get("hydraulic_performance", {}).get("status", "not recorded")
        row["config_sha256"] = metadata.get("configuration_input", {}).get("sha256", "")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="JSON comparison specification")
    parser.add_argument("--outdir", default="out/design-comparison")
    args = parser.parse_args()
    spec_path = Path(args.spec).resolve()
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        shared, scenarios = validate_spec(spec)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    out = Path(args.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    manifest = {
        "comparison_spec": str(spec_path),
        "shared_inputs": shared,
        "shared_keys_locked": list(SHARED_KEYS),
        "scenarios": [],
        "interpretation": "Matched simulation comparison only; not field validation or evidence of water savings.",
    }
    for index, (name, mode, config) in enumerate(scenarios, start=1):
        slug = f"scenario_{index:02d}"
        run_dir = out / slug
        run_dir.mkdir(parents=True, exist_ok=True)
        config_path = run_dir / "effective_config.json"
        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        command = [
            sys.executable, str(ROOT / "campos_sim.py"),
            "--config", str(config_path), "--outdir", str(run_dir),
        ]
        log = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=False)
        (run_dir / "console.log").write_text(log.stdout, encoding="utf-8")
        if log.returncode:
            raise SystemExit(f"Scenario {name!r} failed; inspect {run_dir / 'console.log'}")
        report = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_design_report.py"),
             "--input-dir", str(run_dir)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        (run_dir / "report-builder.log").write_text(report.stdout, encoding="utf-8")
        if report.returncode:
            raise SystemExit(f"Report generation failed for {name!r}; inspect {run_dir / 'report-builder.log'}")
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        for key in SHARED_KEYS:
            actual = metadata["arguments"].get(key)
            expected = shared.get(key)
            if key not in shared:
                continue
            if key in {"sites"} and actual is not None:
                actual = list(actual)
            if actual != expected:
                # Normalize a scalar site or mode only when the JSON schema allows it.
                if not (key == "sites" and isinstance(expected, str) and actual == [expected]):
                    raise SystemExit(f"Scenario {name!r} did not preserve shared input {key!r}: {actual!r} != {expected!r}")
        rows = summarize(name, mode, run_dir, config)
        summary_rows.extend(rows)
        manifest["scenarios"].append({
            "name": name, "mode": mode, "run_dir": str(run_dir),
            "status": "completed", "result_rows": len(rows),
            "effective_config": config,
            "input_classification": metadata.get("data_classification", {}),
        })
        print(f"[{index}/{len(scenarios)}] {name}: {len(rows)} result rows")

    csv_path = out / "design_comparison.csv"
    all_columns = []
    for row in summary_rows:
        for key in row:
            if key not in all_columns:
                all_columns.append(key)
    if not all_columns:
        all_columns = ["scenario", "mode", "status"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=all_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary_rows)
    (out / "comparison_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# Matched design comparison", "",
        f"- Scenarios: {len(scenarios)}",
        f"- Shared input fields locked across scenarios: {', '.join(SHARED_KEYS)}",
        "- Scenario-specific overrides are limited to mode and optimization-policy parameters.",
        "- User-supplied measurements, illustrative assumptions, and missing validation data are identified in each run's metadata and individual HTML/Markdown report.",
        "- A missing selected feasible Pareto trade-off yields no row for that site; inspect each raw run directory.",
        "- Results are model comparisons only. They are not evidence of measured water savings, cost savings, or field performance.", "",
        "| Scenario | Mode | Result rows | Geometry | Radial field | Hydraulic data |",
        "|---|---|---:|---|---|---|",
    ]
    for item in manifest["scenarios"]:
        classification = item.get("input_classification", {})
        report.append(
            f"| {item['name']} | {item['mode']} | {item['result_rows']} | "
            f"{classification.get('site_geometry', 'not recorded')} | "
            f"{classification.get('radial_field', 'not recorded')} | "
            f"{classification.get('hydraulic_curve', 'not recorded')} |"
        )
    report.extend([
        "",
        "See `design_comparison.csv` for combined result rows, `comparison_manifest.json` for exact shared settings, and each `scenario_NN/design_report.html` for the detailed run report.",
        "",
    ])
    (out / "design_comparison.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {csv_path} and {out / 'design_comparison.md'}")


if __name__ == "__main__":
    main()
