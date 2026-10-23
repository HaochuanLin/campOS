# Model development roadmap

This roadmap prioritizes scientific credibility and future compatibility with real campus data over adding features for appearance. Items describe planned work unless explicitly marked as implemented.

## Current foundation

Implemented in the prototype:

- synthetic polygon generation and grid-based spatial model;
- movable-head and fixed-position optimization modes;
- a two-objective Pareto search for overspray versus interior deficit;
- optional normalized radial-profile CSV input;
- optional pressure-performance curve input with interpolation limited to the supplied pressure range;
- reproducible run metadata and source/input hashes;
- custom single-polygon CSV input and optional imported baseline-head CSV;
- unit/regression tests and a GitHub Actions test matrix;
- a public manufacturer-chart consistency benchmark, explicitly not independent field validation.

## Stage 1 — Reliable input and experiment contracts

**Goal:** ensure every result can be reproduced and traced to its inputs.

- [x] Define a CSV contract for a simple local-metric polygon.
- [x] Define a CSV contract for an imported baseline head layout.
- [x] Record custom input paths, hashes, and geometry/layout status in run metadata.
- [ ] Add schema-versioned case manifests with CRS, source, timestamp, units, and quality flags.
- [ ] Support explicit exclusions/obstacles and multiple lawn polygons without silently merging them.
- [ ] Add stronger geometry checks, including self-intersection detection and invalid polygon diagnostics.
- [ ] Add stable head IDs and preserve them through optimization outputs.

## Stage 2 — Physical calibration

**Goal:** replace generic assumptions with documented equipment behaviour.

- [x] Accept an externally prepared normalized radial profile.
- [x] Accept a pressure-flow-throw table and reject extrapolation.
- [ ] Build a documented processor from raw catch-can observations to profile estimates.
- [ ] Represent head/nozzle model, operating pressure, arc, and flow as linked parameters rather than independent free values.
- [ ] Add calibration uncertainty and confidence intervals instead of a single deterministic profile.
- [ ] Keep manufacturer data, bench measurements, and field measurements as separate provenance classes.
- [ ] Add model checks for mass conservation, grid-resolution sensitivity, and interpolation boundaries.

## Stage 3 — Constraints that matter on a campus

**Goal:** avoid geometrically attractive but impossible layouts.

- [ ] Represent obstacles, paths, buildings, trees, protected areas, and no-spray zones.
- [ ] Represent valve zones and shared hydraulic supply.
- [ ] Add keep-out regions and allowed installation corridors.
- [ ] Add practical sprinkler spacing, model-specific arc/nozzle choices, and permitted adjustment ranges.
- [ ] Include pipe/pressure constraints only when the required network data and a defensible hydraulic model are available.
- [ ] Separate existing-layout repair, nozzle/arc adjustment, and new-layout design as different decision problems.

## Stage 4 — Calibrated water balance and validation

**Goal:** connect model output to measurable application, not just relative scores.

- [ ] Predict application depth at actual collector coordinates and compare it with measured depths.
- [ ] Separate calibration data from validation data.
- [ ] Report MAE/RMSE, uniformity metrics, dry-area diagnostics, and uncertainty.
- [ ] Quantify sensitivity to grid size, pressure variation, wind, and measurement error.
- [ ] Only estimate volume or water savings after flow, runtime, and demand assumptions are measured or otherwise defensible.
- [ ] Publish an anonymized, permission-cleared benchmark case with input data, metadata, and expected checks.

## Stage 5 — Decision support and deployment

**Goal:** turn a validated model into a useful professional workflow.

- [ ] Generate an auditable report containing inputs, assumptions, baseline, candidate layouts, constraints, metrics, and validation status.
- [ ] Export candidate layouts to common engineering formats only after coordinate and geometry handling is robust.
- [ ] Add a simple interface for drawing/importing boundaries and reviewing candidates.
- [ ] Add change history and review/approval workflow.
- [ ] Consider sensor or controller integrations only after the model has proven useful on real sites and the data interface is specified.

## Architectural principle

Keep four layers separate:

1. **Observed data:** site geometry, installed equipment, collector measurements, pressure, runtime, weather, and notes.
2. **Calibrated parameters:** radial profile, flow/throw curves, uncertainty, and the exact evidence supporting each parameter.
3. **Model and optimizer:** field calculation, physical constraints, objectives, and search algorithm.
4. **Decision/reporting layer:** candidate comparison, uncertainty, feasibility review, and export.

Never silently turn a missing measurement into a measured value. Every parameter should be labelled as measured, manufacturer-published, inferred, assumed, or unavailable. A sophisticated optimizer cannot compensate for untrustworthy inputs.
