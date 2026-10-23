# Real-site data contract

This document defines the minimum input contract for moving campOS from synthetic examples toward a real campus lawn. The CSV loaders validate structure and basic numeric ranges; they do **not** certify a survey, equipment choice, installation feasibility, or model accuracy.

## Coordinate system

All geometry and sprinkler coordinates in the current CSV interface must use the **same local projected Cartesian coordinate system in metres**:

- x increases east/right in the chosen local drawing frame.
- y increases north/up in the chosen local drawing frame.
- angles are measured counter-clockwise from the positive x-axis.
- the polygon vertices must be ordered around one simple boundary, clockwise or counter-clockwise.
- do not enter longitude/latitude degrees as metres.
- do not mix CAD millimetres, image pixels, GPS degrees, and metres in one file.

For an initial campus test, a local engineering drawing with a known scale is sufficient. Record how the origin and axes were defined. For GIS data, transform the geometry to a suitable projected CRS before exporting; preserve the source CRS and transformation details in the case notes. Holes, multiple disconnected lawn islands, retaining walls, and non-irrigated exclusions are not yet represented by the single-polygon interface. Model them separately or wait for explicit support rather than silently joining them.

## Input files

### 1. Site boundary: `site_polygon.csv`

Required columns: `x_m,y_m`.

Each row is one polygon vertex in boundary order. A final repeated copy of the first vertex is optional. Do not include a header row for each ring or put multiple polygons in one file.

Template: [../data/templates/site_polygon_template.csv](../data/templates/site_polygon_template.csv)

### 2. Existing sprinkler layout: `baseline_heads.csv`

Required columns: `x_m,y_m,throw_m,start_angle_deg,arc_width_deg`.

- `x_m,y_m`: measured or digitized sprinkler centre in the same coordinate frame as the polygon.
- `throw_m`: documented nominal throw radius in metres at the stated nozzle and pressure. If this is only a guess, label it as an assumption in the case record.
- `start_angle_deg`: sector start angle, counter-clockwise from +x.
- `arc_width_deg`: sector width in degrees, greater than 0 and at most 360.
- extra columns such as `head_id`, `manufacturer`, `model`, `nozzle`, `zone_id`, `source`, and `confidence` may be retained in the source workbook, but are not consumed by the current optimizer.

Template: [../data/templates/baseline_heads_template.csv](../data/templates/baseline_heads_template.csv)

When `--heads-csv` is supplied, the imported positions and settings form the baseline. In `fixed` / `pareto-fixed` modes, x/y must remain unchanged. In movable modes the optimizer is allowed to move heads under the current simplified constraints. Neither mode knows where buried pipes, valve zones, utilities, access routes, or legal setbacks are unless those constraints are explicitly modelled; therefore its output is a research candidate, not an installation plan.

### 3. Radial catch-can profile: `catch_can_profile.csv`

Required columns: `radius_fraction,relative_rate`, with radii increasing from 0 to 1 and positive rates. The current loader area-normalizes the radial curve. It uses the **shape** of the distribution; it does not infer total flow or absolute precipitation.

Template: [../data/templates/catch_can_profile_template.csv](../data/templates/catch_can_profile_template.csv)

Do not derive a single-head radial profile from measurements of a fully overlapping multi-head zone unless you have a defensible method to attribute each collector's water to each head. Prefer a controlled single-head test, manufacturer documentation for the exact nozzle, or a documented parameter-estimation method. Keep the raw measurements even if a processed profile is created.

### 4. Pressure-performance curve: `sprinkler_performance.csv`

Required columns: `pressure_kpa,flow_lpm,throw_m`. Pressure must increase strictly; flow and throw must be positive. The current loader interpolates only within the measured table and rejects extrapolation.

Template: [../data/templates/sprinkler_performance_template.csv](../data/templates/sprinkler_performance_template.csv)

Use a curve for the actual sprinkler/nozzle family and document whether the numbers are manufacturer-published, bench-measured, or field-measured. A public product chart is a useful prior, not proof that the installed equipment matches it.

### 5. Raw catch-can observations

Template: [../data/templates/catch_can_observations_template.csv](../data/templates/catch_can_observations_template.csv)

Record a stable case ID, zone ID, collector ID, coordinates, test start/end or duration, measured water depth or volume, pressure, wind, nozzle configuration, and notes. The template is a data-collection aid; the current CLI does not yet ingest it directly. Preserve the raw file unchanged and create processed files as separate derived artifacts.

## Reproducibility and provenance

For every case, maintain a case folder containing:

1. `site_polygon.csv` and, if available, `baseline_heads.csv`.
2. raw observation files, without editing the original values.
3. equipment and pressure sources, including manufacturer/model/nozzle identifiers.
4. a short `case_notes.md` recording date, coordinate origin/CRS, units, operator, weather, operating zone, test duration, and known defects.
5. model input files and generated `run_metadata.json`.
6. a separate validation report comparing predictions to measurements.

The simulator hashes its loaded CSV files in run metadata when applicable. Keep file hashes with results so later changes in input data can be distinguished from code changes.

## Privacy and permission

Do not commit private campus maps, security-sensitive infrastructure locations, identifiable people, access-control details, or proprietary contractor drawings to a public repository. Use a generalized or anonymized geometry in public examples. Obtain written permission before collecting or publishing site data. Keep private raw measurements in a controlled location; publish only data you are authorized to share.

## Current exclusions

The current interface supports one simple polygon and an optional list of heads. It does not yet support holes, multiple islands, obstacles, pipe networks, valve-zone topology, slope, soil properties, wind fields, head failures, or as-built drawing constraints. A file passing CSV validation means only that its format and basic numeric values are acceptable.
