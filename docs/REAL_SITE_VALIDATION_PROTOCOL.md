# Real-site validation protocol

## Purpose and current status

This protocol defines the evidence required before campOS results are used to inform a real irrigation retrofit. It is a **data-collection and evaluation plan**, not evidence that the current model has passed field validation. The repository does not contain an independently measured site dataset or a pre-approved universal pass threshold.

The validation question is narrow: under documented operating conditions, how closely does the model predict the spatial distribution of applied water, including water collected outside the intended lawn boundary? A successful comparison at one site does not establish general validity for other sprinkler models, pressures, weather, soils, or layouts.

## Safety and scope

- Do not use an unvalidated simulation as an installation instruction or change an operating irrigation system solely because of its output.
- Obtain site-owner permission and follow site safety procedures. Keep people away from operating sprinkler equipment and avoid measurements near traffic or electrical hazards.
- Record whether the sprinkler system, nozzle, pressure, wind, and operating schedule match the model inputs. Do not silently treat unknown values as measured.
- This protocol does not estimate water savings or payback. Spatial catch measurements and the model's dimensionless overspray proxy are not, by themselves, total seasonal water use.

## Before collecting data

Create a versioned run directory and preserve the exact input CSVs, model configuration, software revision, random seed, grid size, and generated outputs. Record:

1. Site boundary in a consistent local metre-based coordinate system, plus a sketch/photo and the method used to survey it.
2. Every sprinkler head's coordinate, make/model, nozzle, arc setting, orientation, measured or documented operating pressure, and any known wear or obstruction.
3. Supply pressure at the relevant operating condition; where possible record pressure at the head, not only at the source.
4. Catch-can positions and heights, container opening areas, instrument resolution, reading procedure, run duration, and timestamps.
5. Weather and operating conditions, including wind direction/speed if available, temperature, and any interruption or visible drift.
6. The intended lawn boundary and the locations classified as outside-lawn surfaces (for example, sidewalk or road). Keep classification rules fixed before looking at results.

If a value is unavailable, enter an explicit missing value and explain it in notes; do not substitute a plausible-looking number.

## Measurement design

### Spatial catch-can survey

- Place calibrated, identical catch cans on a documented grid or set of transects spanning both the lawn and nearby outside-lawn area. Include boundary-crossing transects so overspray can be observed instead of inferred only from lawn samples.
- Survey each can's centre coordinate in the same coordinate frame as the polygon and head coordinates. Record the opening area and collected volume or water depth, and use consistent units.
- Collect repeat runs under as similar conditions as practicable. Record each run separately; do not average away a run affected by changed pressure, wind, blockage, or an interruption.
- Measure operating duration and pressure for every run. Use a consistent method to convert collected water to depth. Keep raw observations unchanged and store corrections as separate, documented fields.
- The measurement grid is a sample of the applied-water field, not a direct measure of plant water need, soil moisture, runoff, or seasonal consumption.

### Baseline and candidate comparison

1. Measure the existing layout before changing any equipment.
2. Freeze model assumptions and compare predicted values at the measured coordinates with baseline observations.
3. If calibration is needed, use only a predeclared calibration subset. Record every parameter changed and why.
4. Freeze the calibrated configuration before evaluating a held-out set of runs, locations, or dates. Do not tune on the held-out observations.
5. Only after baseline evaluation, simulate a candidate layout. If it is installed, repeat the same measurement procedure and document any differences in operating conditions.
6. Compare baseline and candidate with matched conditions where possible. Report all valid runs and exclusions with reasons.

The current simulator's raster output and catch-can samples may not be directly comparable without an explicit, documented spatial sampling/interpolation step. Do not claim a quantitative validation score until this mapping and its uncertainty are defined. Never silently compare a raster cell to a nearby can as if they were the same measurement.

## Pre-register the evaluation

Before examining held-out results, write down the site-specific acceptance criteria and why they are appropriate. Do not choose thresholds after seeing the errors. At minimum, report:

- Mean bias (prediction minus observation) in depth units.
- MAE and RMSE in depth units, with sample count and units.
- Error by distance from sprinkler and by inside/outside-lawn classification where the sample count permits.
- Repeatability across runs and the operating conditions represented.
- Uncertainty from measurement resolution, spatial sampling, raster resolution, and any interpolation.
- A separate outside-lawn analysis. Do not interpret an outside-lawn fraction as a measured water-volume saving unless absolute flow and the relevant water balance have been validated.

A field-validation claim should require acceptable performance on held-out observations, documented reproducibility, and a clear statement of the tested equipment and operating envelope. There is no universal pass threshold supplied by campOS; the threshold must be justified for the intended decision and agreed before evaluation.

## Data files

Use [field catch-can template](../data/templates/field_catch_can_template.csv) for raw observations. Keep one row per can per run. The template is intentionally empty and is not a dataset. Use a separate site log for survey method, sprinkler specification, pressure, weather, and deviations; link the files with stable site and run IDs.

Recommended folder layout:

```text
field-study/
  protocol-and-preregistered-thresholds.md
  site_log.csv
  site_polygon.csv
  sprinkler_layout.csv
  field_catch_can_observations.csv
  model_run/
    run_metadata.json
    raw_outputs...
  analysis/
    exclusions.csv
    held_out_metrics.csv
    plots...
```

## End-to-end point prediction and error evaluation

For a surveyed site with an explicit sprinkler layout, a completed catch-can CSV, and a **measured flow rate per head at the documented operating condition**, run the integrated prediction workflow:

```bash
python scripts/predict_catch_can_depths.py \
  --polygon-csv data/site_polygon.csv \
  --heads-csv data/sprinkler_layout.csv \
  --observations data/field_catch_can_observations.csv \
  --flow-lpm 4.0 \
  --outdir out/field-evaluation
```

Replace the example paths and flow with the actual measured inputs. The script evaluates the model at each exact catch-can coordinate (rather than silently matching a nearby raster cell), multiplies predicted precipitation rate by the recorded collection duration, and writes: it reports errors overall and separately for the user-labelled inside/outside/boundary zones, so outside-lawn observations can be inspected independently. A conflict between the zone label and polygon geometry is flagged rather than silently corrected.

- `paired_predictions.csv`: measured and predicted depth, residual, absolute error, location, zone, split, and whether the coordinate falls inside the supplied polygon.
- `field_evaluation_metrics.json`: input and model-source SHA-256 hashes, Python/NumPy versions, assumptions, calibration and holdout counts, descriptive error metrics, and any conflict between a row's inside/outside label and the polygon geometry.

The sprinkler layout may include an optional `flow_lpm` column with a measured flow for each head. If a head's value is blank, supply `--flow-lpm` as a fallback; a CLI fallback is unnecessary when every head has a measured value. The field CSV must include a `split` column set to `calibration` or `holdout`. All cans from a single `site_id,run_id` must remain in one split; the tool rejects mixed splits within a run. The default uniform radial profile is a null-model assumption. A measured relative radial profile can be supplied with `--profile-csv`, but it still requires measured flow for absolute depth prediction.

**Scope:** all heads are assumed to have the same supplied flow. Predictions omit wind, drift, evaporation, pressure loss, and network hydraulics. The tool computes errors but does not declare a model valid or decide pass/fail. Set acceptance thresholds before looking at holdout errors, and do not calibrate using holdout observations.

### Optional machine-readable acceptance assessment

If the study protocol already specifies justified limits, store them in a JSON file before evaluating holdout data. The following numbers are **illustrative syntax only**, not recommended engineering tolerances:

```json
{
  "max_holdout_mae_mm": 1.0,
  "max_holdout_rmse_mm": 1.5,
  "max_absolute_bias_mm": 0.5
}
```

Pass the file to the installed command:

```bash
campos-field-evaluate \
  --polygon-csv data/site_polygon.csv \
  --heads-csv data/sprinkler_layout.csv \
  --observations data/field_catch_can_observations.csv \
  --acceptance-thresholds-json data/preregistered-thresholds.json \
  --outdir out/field-evaluation
```

The metrics JSON and generated HTML/Markdown reports then record each observed holdout metric, its user-supplied limit, and whether that individual check passed. The threshold file's SHA-256 is recorded for provenance. Without this option, the tool reports descriptive errors and does not invent an acceptance result. A software-level pass only means the chosen numeric limits were met for these supplied observations; it does not establish general validity, independent sampling, or water savings.

## Paired error metrics for predictions already available

campOS also includes `scripts/evaluate_observation_errors.py`. It computes descriptive bias, MAE, RMSE, maximum absolute error, and an optional R-squared-style comparison for paired depths supplied by the user. It requires a CSV with `measured_mm,predicted_mm,split`; `split` must be `calibration` or `holdout`, and at least two holdout rows are required by default.

Example input (illustrative values only, not a dataset):

```csv
measured_mm,predicted_mm,split
4.2,4.0,calibration
3.8,4.1,calibration
4.5,4.3,holdout
3.9,4.0,holdout
```

Run it with:

```bash
python scripts/evaluate_observation_errors.py \
  --input out/paired_depths.csv \
  --out out/paired_error_metrics.json
```

**Important limitation:** this utility scores paired values only. It does not produce a prediction at each catch-can coordinate, perform spatial interpolation, calibrate parameters, or prove that the holdout split is independent. The user must document how each prediction was obtained and how it was spatially matched to the observation. Do not report these metrics as model validation until the prediction mapping, independence, measurement uncertainty, and pre-registered acceptance criteria are justified.

## What a valid conclusion may say

A defensible report identifies the site, sprinkler/nozzle, pressure range, weather and measurement procedure; distinguishes calibration from held-out evaluation; shows raw data and errors; and states limitations. It should not generalize from one lawn to all sites.

Until the model has a documented observation-to-prediction comparison workflow and independent held-out results, describe these steps as **preparation for field validation**, not completed validation.


## Optional AI residual correction experiment

Only after generating the physical-model paired_predictions.csv, an optional Gaussian-process correction can model the spatial pattern of calibration residuals:

~~~bash
python -m pip install -e ".[ai]"
python scripts/ai_residual_correction.py \
  --predictions-csv out/field-evaluation/paired_predictions.csv \
  --outdir out/ai-residual-correction
~~~

The tool requires at least eight calibration observations, three holdout observations at unique coordinates, and five distinct calibration coordinates. Calibration and holdout run IDs must be disjoint to block run-level leakage; repeated coordinates across distinct runs are allowed and can test repeat-run transfer. It trains on measured_mm minus predicted_mm from calibration rows only; holdout observations are never used for model fitting or kernel selection. It reports uncorrected and corrected holdout errors, empirical coverage and average width of nominal 95% model-based intervals. Coverage estimates from small holdout sets are unstable and do not guarantee future interval coverage.

Treat this as a competing model, not an automatic upgrade. Pre-register the evaluation criteria, inspect residuals and uncertainty, and evaluate on a separate run/day/site before deciding whether the correction is useful. Do not repeatedly tune the model against one holdout set. This spatial correction cannot infer unmeasured wind, pressure, nozzle wear, or hydraulics, and it does not establish water savings.
