# Changelog

This changelog records user-visible capabilities and important methodological clarifications. It is not a claim that every feature has been field validated.

## [0.1.0] - Unreleased

### Product and workflow
- Added a Streamlit interface for synthetic demonstrations and surveyed-site CSV inputs.
- Added fixed-head, movable-head, and Pareto comparison modes.
- Added result bundles, plots, reports, run metadata, and artifact-manifest verification.
- Added a hosted-app reachability monitor separate from local UI tests.

### Data and evaluation
- Added templates and input contracts for site polygons, sprinkler layouts, radial profiles, pressure/performance data, and catch-can observations.
- Added observation quality checks, pointwise catch-can prediction, and calibration/holdout evaluation.
- Added optional Gaussian-process residual correction as an experimental workflow.
- Added pre-registered acceptance thresholds and diagnostics for selected input/geometry inconsistencies.

### Numerical and optimization work
- Added protected road/sidewalk polygon objectives in supported Pareto modes.
- Added baseline-relative guards and diagnostics for selected overspray, interior-deficit, dry-area, and uniformity trade-offs.
- Added grid-size safety limits and resolution-sensitivity diagnostics.

### Verification and documentation
- Added regression tests, Python-version CI, UI smoke tests, and artifact-integrity checks.
- Documented objective definitions, model assumptions, custom-site inputs, and field-validation protocols.

### Important limitations
- Built-in site geometry is synthetic; the default radial distribution is an assumption unless replaced by measured data.
- Road/sidewalk water is a modelled geometric proxy, not a direct measurement of real pavement wetting.
- Wind, drift, evaporation, pressure losses, soil response, terrain, and system hydraulics are not fully represented or field validated.
- A green test run establishes only the tested software behavior. It does not establish predictive accuracy, reduced road wetting, or water savings.
- Confirm third-party dependency licenses and project ownership before making a formal release.
