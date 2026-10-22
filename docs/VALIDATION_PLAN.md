# Validation and sensitivity study plan

## Status and scope

This document defines experiments to run before describing campOS as validated. No field data or validation results are included here. All built-in sites are synthetic, and the current radial-slope scenarios are assumptions rather than measured sprinkler properties.

The work is split into three evidence levels. Passing an earlier level does not imply passing a later one.

1. **Software/numerical verification:** unit tests, flow-integral checks, configuration recording, grid sensitivity, and repeated random seeds.
2. **Component calibration:** fit a radial profile and pressure/flow/throw relationship using documented measurements for the actual sprinkler/nozzle and pressure.
3. **Independent system validation:** compare model predictions with held-out measurements for overlapping heads and a surveyed lawn under recorded field conditions.

## Stage A — reproducible numerical sensitivity

Use the parameter sweep:

```bash
python scripts/parameter_sensitivity.py --quick --sites A --seeds 7 19 41 --cell-sizes 0.5 1.0 --slopes -0.5 0 1
```

For a more representative search, omit `--quick` and retain the exact output directory and Git commit. Before interpreting results:

- Compare repeated seeds at the same site, grid size, and radial assumption to quantify optimizer variability.
- Compare grid sizes only as discretization sensitivity; the cell-centre raster and baseline layout may change with resolution.
- Compare radial slopes as alternative assumptions, not as a probability distribution or calibrated nozzle model.
- Inspect AR, overspray, CU, dry area, sprinkler count, and raw plots together. Do not reduce them to a single winner unless the decision rule was specified beforehand.
- Keep all failed runs and logs; do not silently omit inconvenient cases.

The automated report's fraction of runs with improved AR is descriptive for the selected sweep only. It is not a confidence level, success probability, or estimate of water savings.

## Stage B — component calibration data

For the exact hardware and pressure being modelled, collect:

- Nozzle/sprinkler model and identifier, arc setting, pressure at the head while operating, measured throw radius, and measured flow.
- Catch-can dimensions and measurement method, duration, radial positions, multiple directions/transects, repeated runs, wind and test conditions.
- Raw observations, instrument resolution/calibration, exclusions, and any estimated center or edge values.
- A pressure-performance table over the intended operating range if the model will estimate absolute precipitation.

Prepare the radial profile with `scripts/prepare_radial_profile.py`. Retain the raw data and the derived file. Fit or tune the profile on a calibration subset only; document any smoothing and endpoint assumptions. The loader's area normalization preserves the relative shape but does not independently validate the absolute flow.

## Stage C — independent validation

Use a surveyed test plot whose polygon, head coordinates, nozzle/arc settings, and operating pressure are measured independently of the optimizer. Do not use validation measurements to tune the radial profile or select the final optimization policy.

1. **Baseline:** measure the existing or deliberately specified layout before optimization. Record operating conditions and replicate the catch-can grid or collection method.
2. **Single-head check:** compare predicted radial rates against a held-out transect or repeat session not used to fit the profile.
3. **Overlap check:** measure the combined application field for multiple heads. Single-head agreement alone does not establish that overlap is correct.
4. **Replicates:** repeat under more than one run/session; record wind and pressure variation. If conditions are outside the model's scope, flag the run rather than treating the mismatch as optimizer error.
5. **Predeclare metrics:** report bias and absolute error for application depth, spatial error across catch-can locations, CU, dry-area fraction at a declared threshold, and outside-boundary water. Report uncertainty from instrument resolution and repeat runs.
6. **Held-out comparison:** compare baseline and optimized layouts under comparable conditions. Report raw observations, predicted values, residuals, exclusions, and the complete configuration/commit.
7. **Decision rule:** choose acceptable error bounds before looking at held-out results, based on instrument uncertainty and the intended use. This repository does not impose universal numeric acceptance thresholds because the measurement setup and application requirements have not been specified.

A calibrated profile fitted to a dataset is not independently validated by comparing it against the same dataset. A manufacturer aggregate flow/throw chart can check mass-balance consistency but does not validate a local radial distribution or a real site's overlapping field.

## Reporting requirements

Every published experiment should include:

- Repository commit, software/Python/dependency versions, complete command, random seed, grid size, and all model parameters.
- Site survey and sprinkler/nozzle/pressure details, raw data provenance, calibration/validation split, and instrument uncertainty.
- CSV results, plots, failed-run notes, and the exact definitions/denominators for each metric.
- Separate statements for software verification, calibration fit, and independent validation.
- No claim of water, cost, or payback savings unless total discharge and annual demand are independently calibrated and the comparison is supported by measured or otherwise defensible evidence.
