# Real-site data contract

This compatibility guide points to the current branch's detailed input definitions and validation workflow.

## Coordinates and polygon
- Use one local projected Cartesian coordinate system in metres for the lawn, sprinkler heads, and protected surfaces.
- The lawn polygon CSV requires `x_m,y_m` with at least three distinct vertices in boundary order. A repeated closing vertex is accepted.
- Do not enter longitude/latitude degrees as metres. Record the source drawing/CRS, origin, axis directions, and any coordinate transformation.

See [custom-site input formats](CUSTOM_SITE_INPUTS.md).

## Sprinkler layout
The current optimizer layout contract is `x_m,y_m,radius_m,start_angle_deg,arc_width_deg`; an optional `flow_lpm` column may supply measured flow for pointwise field evaluation. All initial head coordinates must lie inside the lawn polygon and radii must fall within the optimizer's configured range. Extra descriptive columns such as `head_id` may be retained in the CSV but are not currently used as stable identities by the optimizer.

## Catch-can observations
Use the [field catch-can template](../data/templates/field_catch_can_template.csv). Preserve one row per collector per run, raw readings, duration, units, validity flag, site/run IDs, and the calibration/holdout split. Keep all observations from a given site/run in a single split. Do not tune parameters against holdout observations.

## Provenance and limitations
Record sprinkler/nozzle model, arc, pressure, flow, runtime, weather, survey method, timestamps, software revision, seed, grid size, and reasons for exclusions. Missing values must remain explicitly missing; do not invent plausible measurements.

The current model is not field-validated. Wind/drift, evaporation, pressure losses, soil response, and network hydraulics are incompletely modelled. See the [real-site validation protocol](REAL_SITE_VALIDATION_PROTOCOL.md) for safety, measurement design, and acceptance-threshold rules.
