# campOS project charter

## Product definition

campOS is an open, reproducible decision-support prototype for comparing sprinkler layouts around irregular lawn boundaries. It helps users inspect the modelled trade-off between water applied outside the intended lawn and insufficient coverage inside it.

**Live demo:** https://campos-optimizer.streamlit.app/  
**Repository:** https://github.com/HaochuanLin/campOS

## The problem

Sprinklers do not stop at a property boundary. A layout may wet pavement or a sidewalk while leaving dry areas inside the lawn. Moving heads may improve a modelled layout but require installation work; retaining existing heads imposes different constraints. A single aggregate score can conceal these conflicts.

campOS makes these trade-offs easier to inspect under explicit, reproducible assumptions. The intended outcome is better-informed comparison—not an automatic guarantee that a particular layout is correct.

## Primary decision question

> For a defined lawn boundary, sprinkler layout, and documented set of operating assumptions, how do candidate layouts compare on outside-lawn application, interior deficit, and distribution uniformity?

This question is narrower than “How much water will this property save?” A credible savings estimate needs measured flow and operating time, calibrated sprinkler behavior, local conditions, and field evidence.

## Intended users

- Students and researchers exploring irrigation-layout optimization.
- Landscape and irrigation practitioners screening candidate configurations.
- Developers testing transparent, reproducible optimization and validation workflows.

The current prototype is not a certified engineering tool, autonomous irrigation controller, or substitute for a qualified site assessment.

## Current capabilities

- Reproducible synthetic scenarios and fixed-head versus movable-head comparisons.
- Pareto exploration of competing objectives, including a protected-surface polygon in supported modes.
- Import of custom lawn polygons and sprinkler-layout CSVs in metre-based coordinates.
- Optional measured radial profiles and pressure/flow/throw data.
- Catch-can observation quality checks, pointwise prediction, and calibration/holdout evaluation.
- Exportable artifacts and run metadata for auditability.

These are software capabilities. They do not establish predictive accuracy or field performance.

## Evidence boundaries

Every input should be identified as measured, manufacturer-published, derived, assumed, or unavailable. Never silently substitute an assumption for a measurement.

The built-in lawn shapes are synthetic. Grid-based metrics depend on discretization. Real sprinkler behavior can depend on nozzle design, pressure, wind, droplet drift, evaporation, overlapping patterns, soil infiltration, terrain, and system hydraulics. These effects are not all represented or validated in the current model.

The project must not claim that campOS reduces road wetting, saves a specified amount of water, or produces installation-ready designs until those claims are supported by a documented field protocol and independent measurements.

## Product principles

1. **Show trade-offs, not just a winner.** Report overspray, interior deficit, dry area, distribution uniformity, and relevant feasibility warnings separately where available.
2. **Reproducibility by default.** Preserve seeds, configuration, input provenance, software details, and generated artifacts.
3. **Fail visibly.** Invalid or missing inputs must produce actionable messages rather than silently becoming plausible-looking defaults.
4. **Separate calibration from validation.** Do not tune on holdout data and then present it as independent evidence.
5. **Make uncertainty visible.** A precise-looking number is not proof of a precise physical prediction.
6. **Prefer evidence over feature count.** New optimization features must have a clear objective, tests, and documented limitations.

## Development gates

### Gate 1 — Product and deployment reliability
- Tests cover startup, core user flows, input errors, and artifact generation.
- The hosted page and health endpoint are checked separately from local CI.
- Real browser tests verify a simulation run and downloaded ZIP contents.
- User-facing documentation matches the actual UI.

### Gate 2 — Objective and numerical audit
- Objective terms, units, normalization, penalties, and feasibility rules are documented.
- Baselines and candidates are compared under matched settings.
- Regression tests cover geometry, grid sensitivity, deterministic behavior, and metric invariants.

### Gate 3 — Physical calibration and independent evaluation
- Inputs are sourced from measurements or identified manufacturer data.
- Acceptance thresholds are chosen before inspecting holdout errors.
- Evaluation uses independent observations and reports errors and failure cases.
- Optional AI correction remains experimental until it demonstrates generalization.

### Gate 4 — Field trial
- Collect a surveyed site boundary, head locations, nozzle and pressure data, flow, weather/context, and catch-can measurements.
- Compare predicted and observed water distribution under a documented protocol.
- Evaluate road/sidewalk wetting and water use directly before making claims about either.

## Definition of done for a claim

A claim is accepted only when its evidence is recorded, the method can be reproduced, limitations are stated, and a test or independent measurement supports it. A green software test proves only the tested software behavior. Synthetic simulation proves only what follows from the model and its assumptions.

## Immediate priorities

1. Close the gap between local CI evidence and hosted browser behavior.
2. Audit the optimization objective against the stated road/sidewalk-protection goal.
3. Validate physical assumptions and sensitivity before expanding AI features.
4. Make the first-run experience and data templates understandable without expert setup.
