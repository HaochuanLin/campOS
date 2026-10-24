# Changelog

## [0.1.0] - Unreleased

### Added
- CSV loaders for custom site polygons and imported baseline sprinkler layouts in local metric coordinates.
- Real-site data contracts, catch-can validation protocols, model development roadmap, and input templates.
- Baseline-relative Pareto guardrails for overspray, interior deficit, CU, and dry area, plus candidate rejection diagnostics.
- Optional protected road/sidewalk polygon objectives and grid-resolution sensitivity checks.
- Catch-can prediction and holdout evaluation, with optional Gaussian-process spatial residual correction.
- One-command synthetic quickstart, local Streamlit UI, and artifact SHA-256 verification.
- Regression tests for model invariants, geometry contracts, artifact integrity, and reproducible quickstart configuration.
- CI workflows for the Python test matrix, artifact verification, and local UI startup.
- Input hardening for ambiguous acceptance-threshold JSON, duplicate catch-can records, out-of-range AI kernel settings, and oversized or numerically invalid simulation grids.

### Clarifications
- Synthetic geometry and model-defined metrics are not field validation or proof of water savings.
- The default radial profile is a null-model assumption unless replaced by measured data.
- Road/sidewalk water is a simulated geometric proxy; wind, drift, evaporation, pressure losses, and network hydraulics remain incompletely modelled.
- Verify code ownership and third-party license compatibility before making a formal release.
