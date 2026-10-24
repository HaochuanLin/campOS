# campOS

**A research prototype for sprinkler-layout optimization on synthetic lawn geometries.**

[![Tests](https://github.com/HaochuanLin/campOS/actions/workflows/tests.yml/badge.svg)](https://github.com/HaochuanLin/campOS/actions/workflows/tests.yml)
[![Python 3.10–3.12](https://img.shields.io/badge/python-3.10%E2%80%933.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Important:** campOS is not field-validated. Lawn geometry is synthetic, sprinkler physics and economic inputs include placeholders, and outputs must not be treated as installation instructions or guaranteed water savings.

## Project concept

campOS is an **open, reproducible decision-support prototype for comparing sprinkler-layout options on irregular lawns**. It is designed to make a design question inspectable: given a lawn boundary and an existing or proposed sprinkler layout, how do alternative configurations trade water applied outside the lawn against the modelled risk of insufficient coverage inside it?

It is not an autonomous irrigation controller, a certified engineering design tool, or a water-savings calculator. Its purpose at this stage is to compare candidate layouts under explicit assumptions, expose the trade-offs behind each result, and provide a disciplined path from synthetic experiments to measurement-based evaluation.

### The workflow

1. **Describe the site:** use a synthetic test shape or import a measured lawn boundary and existing head coordinates.
2. **Establish a baseline:** record the input geometry, layout, model assumptions, grid resolution, and random seed.
3. **Explore alternatives:** compare fixed-position retrofit and movable-head search; use Pareto modes when overspray and interior deficit must be considered together.
4. **Inspect evidence:** review the metrics, plots, raw CSVs, run metadata, and matched-scenario reports—not a single headline score alone.
5. **Validate before relying on it:** calibrate inputs with documented sprinkler data and evaluate predictions against independent observations before making real-site or savings claims.

### What the current prototype can and cannot support

- **Can support now:** reproducible synthetic comparisons, exploratory layout search, sensitivity checks, input provenance, and transparent reporting of model-defined metrics.
- **Can support with appropriate user data:** geometry-specific comparisons and model calibration workflows, provided the supplied data are documented and their limits are respected.
- **Cannot yet support:** validated installation recommendations, guaranteed water savings, payback estimates, or claims of field accuracy. The built-in lawn shapes are synthetic; wind, drift, evaporation, pressure losses, soil response, and other site effects are not fully modelled.

See [the project charter](docs/PROJECT_CHARTER.md) for the intended scope, evidence standards, and development priorities. For a practical measurement plan, required field records, and the distinction between calibration and independent evaluation, see the [real-site validation protocol](docs/REAL_SITE_VALIDATION_PROTOCOL.md).

Copy the empty [field observation template](data/templates/field_catch_can_template.csv), fill one row per can per run, and keep the raw copy unchanged. Before any model comparison, run the field-observation data-quality checker on the completed CSV:

```bash
cp data/templates/field_catch_can_template.csv data/field_catch_can_observations.csv
# Edit data/field_catch_can_observations.csv, then run:
python scripts/check_field_observations.py \
  --input data/field_catch_can_observations.csv \
  --outdir out/field-data-qc
```

It checks required columns, unique can IDs per site/run, numeric values, units, and basic flags; if depth is blank, it derives depth in mm from collected volume and opening area. It writes a normalized CSV and JSON quality summary. This is **data QC only**—it does not compare observations with model predictions or count as field validation. For already-paired measured/predicted depths, `scripts/evaluate_observation_errors.py` computes descriptive calibration/holdout error metrics; see the [real-site validation protocol](docs/REAL_SITE_VALIDATION_PROTOCOL.md) for its required input and important limitations. It does not generate spatial predictions from the simulator.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/HaochuanLin/campOS.git
cd campOS
python -m pip install -e ".[dev]"
python campos_sim.py --help
python -m pytest -q
```

Run a short smoke test on one synthetic rectangular site:

```bash
python campos_sim.py --mode movable --quick --sites A --outdir out/demo
```

The command writes CSV summaries, PNG plots, and `run_metadata.json` to `out/demo/`. The metadata records the selected modes and sites, effective model configuration, Python/platform details, NumPy/Matplotlib versions, and a SHA-256 hash of the simulation source.

### Import a measured site polygon and existing sprinkler positions

Custom input CSVs use metre-based coordinates. See the [input format and limitations](docs/CUSTOM_SITE_INPUTS.md); starter templates are in `data/templates/`.

```bash
python campos_sim.py --mode fixed --quick \
  --polygon-csv data/templates/site_polygon_template.csv \
  --heads-csv data/templates/sprinkler_layout_template.csv \
  --outdir out/custom-site
python scripts/build_design_report.py --input-dir out/custom-site
```

The checked-in templates contain **illustrative example coordinates only**, not a surveyed site or installation recommendation. For future catch-can measurements, start with the empty [field observation CSV template](data/templates/field_catch_can_template.csv) and follow the [validation protocol](docs/REAL_SITE_VALIDATION_PROTOCOL.md). Replace them with surveyed geometry and actual sprinkler coordinates. The run metadata records hashes and counts for the input files. If you provide only `--polygon-csv`, campOS generates its own baseline layout. Custom geometry runs as one site and cannot be combined with `--sites`.


Generate a shareable, self-contained HTML report and a Markdown copy from any completed run:

```bash
python scripts/build_design_report.py --input-dir out/demo
```

This creates `design_report.html` (figures embedded, no external assets required) and `design_report.md` alongside the run outputs. The report records the run configuration and available CSV results, and explicitly states the model's validation and economics limits. It does not convert AR changes into water savings or certify a real-site layout.


For a single-objective run, the main artifacts are `results_<mode>.csv`, `layouts_<mode>.png`, and `ranking_<mode>.png`. Pareto runs write `pareto_<fixed|movable>.csv` and `pareto_<fixed|movable>.png`. When both single-objective modes run together, a `comparison_single_objective.csv` is also written.

More examples:

```bash
# Fixed-position retrofit mode
python campos_sim.py --mode fixed --sites A C --outdir out/fixed

# Pareto trade-off for the synthetic kidney-shaped site
python campos_sim.py --mode pareto-fixed --quick --sites C --outdir out/pareto

# All four modes across all five synthetic sites (computationally expensive)
python campos_sim.py --mode all --outdir out/full
```

Use `--seed` to set the random seed and `--cell-size` to change the spatial grid resolution (in metres), for example:

```bash
python campos_sim.py --mode movable --quick --sites A --seed 19 --cell-size 1.0 --outdir out/coarse-grid
```

Compare grid resolutions for one synthetic site:

```bash
python scripts/grid_sensitivity.py --site 'A Rectangle' --cell-sizes 2,1,0.5 --out out/grid_sensitivity.csv
```

The seed and cell size are recorded in `run_metadata.json`. Smaller cells increase spatial resolution and runtime; results from different cell sizes should be treated as a sensitivity comparison, not directly interchangeable measurements. Invalid site IDs and non-positive or non-finite cell sizes are rejected with a clear CLI error.

`--quick` reduces optimization iterations for smoke testing. It is not a substitute for a full run. Generated output is ignored by Git by default; publish results only after reviewing the CSVs, metadata, and figures.

## Model inputs and physics references

campOS compares four search modes for rotary-sprinkler layouts:

- **Movable-head optimization:** sprinkler positions, throw radii, and sector angles may change.
- **Fixed-position retrofit optimization:** sprinkler coordinates remain unchanged; only radii and sector angles may change.
- **Pareto search:** explores the trade-off between overspray and interior water deficit, with a dry-area constraint.

### Use a measured sprinkler radial profile

If you have catch-can measurements for the actual nozzle and operating pressure, provide a CSV with `radius_fraction,relative_rate` columns and run:

```bash
# With measured catch-can data
python campos_sim.py --mode movable --quick --sites A --profile-csv data/catch_can_profile.csv --outdir out/profile-run

# Without measurements: compare alternative assumed radial shapes
python campos_sim.py --mode movable --quick --sites A --radial-slope -0.5 --outdir out/sensitivity-center-heavy
python campos_sim.py --mode movable --quick --sites A --radial-slope 0 --outdir out/sensitivity-uniform
python campos_sim.py --mode movable --quick --sites A --radial-slope 1 --outdir out/sensitivity-edge-heavy
```

For raw catch-can observations, use `scripts/prepare_radial_profile.py` to convert repeated depth readings into the loader's profile format. The measurement checklist, required raw CSV columns, endpoint assumptions, and validation limits are documented in [the radial-profile protocol](docs/RADIAL_PROFILE_PROTOCOL.md). The checked-in [CSV template](data/templates/catch_can_observations_template.csv) is intentionally empty and is not a dataset.

The profile is area-normalized and changes the radial distribution shape. It does **not** supply absolute flow or validate the model by itself. If you have no catch-can data, use the default uniform-depth null model and compare sensitivity scenarios with `--radial-slope` (valid values are greater than -1):

### Optional measured pressure-performance curve

For a specific sprinkler, provide a measured table with `pressure_kpa,flow_lpm,throw_m` and choose a pressure within the table's measured range:

```bash
python campos_sim.py --mode fixed --quick --sites A --profile-csv data/catch_can_profile.csv --performance-csv data/performance.csv --pressure-kpa 250 --outdir out/calibrated
```

This is an invocation example, not a recommended pressure setting. The performance table must come from the actual sprinkler/nozzle or a documented test. When active, the model uses interpolated flow and throw and locks throw radius during optimization. The absolute field is an estimated precipitation rate in mm/h under uniform-sector assumptions, not field validation.

### Public sprinkler-physics benchmark

I added a reproducible check against published Rain Bird 5000 Series standard-angle nozzle data:

```bash
python scripts/benchmark_sprinkler_curve.py
```

The six-point CSV includes pressure, flow, throw radius, and manufacturer-published square/triangular precipitation rates. The benchmark compares those rates with a flow / grid-cell-area calculation using the chart's half-circle operating assumption. A 1 mm/h tolerance accounts for integer rounding. This is a public manufacturer-chart consistency check, **not independent field validation** and not a measurement of the local radial spray pattern. Source and transcription details are in [data/benchmarks/README.md](data/benchmarks/README.md).

The same file is a runnable example of the pressure-performance option at 200–450 kPa:

```bash
python campos_sim.py --mode fixed --quick --sites A --performance-csv data/benchmarks/rainbird_5000_standard_1_5.csv --pressure-kpa 300 --outdir out/rainbird-example
```

Without a measured catch-can profile for this exact nozzle/pressure, the radial field remains a placeholder; do not interpret this example as a field-validated layout.

## Optimization modes

| Mode | Parameters allowed to change | Purpose |
|---|---|---|
| `movable` | Position `x/y`, radius `r`, start angle `a0`, arc width `w` | Explore a new layout using the legacy AR objective |
| `fixed` | Radius `r`, start angle `a0`, arc width `w`; `x/y` fixed | Explore a retrofit without relocating heads |
| `pareto-movable` | Position, radius, start angle, arc width | Explore overspray/deficit trade-offs with movable heads |
| `pareto-fixed` | Radius, start angle, arc width; `x/y` fixed | Explore retrofit trade-offs without relocating heads |

The built-in synthetic sites are **A** rectangle, **B** L-shape, **C** kidney, **D** wedge, and **E** roadside strip. They are generated polygons, not surveyed properties.

### Explicit optimization policy

The legacy `movable` and `fixed` modes remain available as a comparison baseline. Use `pareto-movable` or `pareto-fixed` when you want to examine the trade-off between overspray and interior deficit instead of optimizing AR alone.

The Pareto policy can be set explicitly and is recorded in `run_metadata.json`:

```bash
python campos_sim.py --mode pareto-fixed --quick --sites C \
  --dry-fraction-limit 0.02 \
  --target-factor 1.0 \
  --cu-drop-budget 0.03 \
  --pareto-weights 0,0.25,0.5,0.75,1 \
  --outdir out/pareto-policy
```

- `--dry-fraction-limit`: maximum fraction of lawn cells allowed below the configured dry threshold. This is a model constraint, not a plant-health guarantee.
- `--target-factor`: target depth as a multiple of the baseline lawn mean. The default of 1.0 is a comparison convention, not an agronomic prescription.
- `--cu-drop-budget`: maximum absolute CU loss allowed relative to the most uniform feasible point when selecting the displayed trade-off.
- `--pareto-weights`: weights used to guide stochastic exploration toward different parts of the Pareto front. They are search controls, not evidence-based utility weights; the final selected point is chosen using the CU-drop budget and lowest overspray ratio.

These settings make assumptions explicit; they do not make the model field-validated. Compare several settings and report the full trade-off before treating any one selection as a preferred design.

```mermaid
flowchart LR
    A[Synthetic polygon] --> B[Grid discretization]
    B --> C[Baseline layout]
    C --> D[AR optimization]
    C --> E[Pareto search]
    D --> F[CSV, plots, run metadata]
    E --> F
```

## Matched optimization benchmark

Run the legacy AR modes and Pareto modes against the same synthetic site, seed, grid, radial field, and baseline layout:

```bash
python scripts/compare_optimization_modes.py --quick --sites A
```

By default, the script compares all five synthetic sites; omit `--quick` for the configured full optimization iterations. It writes `benchmark_summary.csv`, a concise `README.md` report, and the raw simulation CSVs, plots, metadata, and console log under `out/optimization-benchmark/`. Set `--seed`, `--cell-size`, `--radial-slope`, `--dry-fraction-limit`, `--target-factor`, `--cu-drop-budget`, and `--pareto-weights` to reproduce or vary assumptions.

The comparison is matched at the scenario/configuration level, but the algorithms optimize different objective functions and Pareto search is a stochastic finite-search approximation. Pareto f1 and legacy overspray share different denominators; Pareto and legacy dry-area metrics also use different thresholds. The benchmark therefore reports both objective-specific and shared metrics instead of collapsing them into a single winner score. It is a synthetic model comparison, not field validation or a water-savings estimate.


## JSON configuration and matched design comparisons

Run a reproducible configuration file (CLI flags override JSON values):

```bash
python campos_sim.py --config configs/run.example.json
```

Compare named scenarios while keeping geometry, seed, grid, radial assumptions, and measurement files fixed:

```bash
python scripts/compare_design_configs.py \
  --spec configs/design_comparison.example.json \
  --outdir out/design-comparison
```

The script writes `design_comparison.csv`, `comparison_manifest.json`, a Markdown summary, and a separate raw run directory per scenario. Scenario overrides are deliberately restricted; see [configuration and comparison rules](docs/CONFIGURATION_AND_COMPARISONS.md). Run metadata and generated reports distinguish user-supplied files, illustrative assumptions, unconfigured physics, and placeholder economics. A supplied measurement file is not by itself proof that the model is validated.

## Parameter sensitivity and numerical robustness

Run a reproducible sweep across optimizer seeds, grid resolutions, and assumed radial distributions:

```bash
python scripts/parameter_sensitivity.py --quick --sites A --seeds 7 19 41 --cell-sizes 0.5 1.0 --slopes -0.5 0 1
```

By default, the sweep covers sites A–E, three seeds, two grid sizes, and three radial slopes. It writes one row per run to `sensitivity_summary.csv`, with the requested configuration cross-checked against each run's metadata; raw outputs and plots remain in scenario subfolders. Omit `--quick` for the simulator's full iteration budget. The full default sweep is computationally expensive.

This study checks sensitivity to stochastic search initialization, raster resolution, and illustrative radial-shape assumptions. It is **not** a formal probabilistic uncertainty analysis or empirical validation. The slopes are not measured sprinkler properties, and changes in the grid also change the raster approximation. For independent validation, use surveyed site geometry and held-out catch-can or field observations collected under documented conditions. The staged experiment design, calibration/holdout split, reporting requirements, and acceptance-threshold policy are in [the validation plan](docs/VALIDATION_PLAN.md). Do not interpret AR improvement as water savings.

## Metrics: read them carefully

The model reports several metrics that answer different questions. They are not interchangeable.

- **AR (legacy single-objective metric):** total modelled applied water divided by the product of lawn-cell count and the mean depth of the driest quarter of lawn cells. Lower is better for this objective.
- **AR metric improvement:** `1 - AR_optimized / AR_baseline`. This is **not water savings**. It expresses the relative change in a dimensionless low-quarter metric; optimized total discharge may increase.
- **Overspray (`f1`):** in Pareto mode, water outside the lawn divided by the baseline layout's total modelled water. The separate legacy overspray metric is the outside-water share of that layout's own total water. These denominators differ.
- **Interior deficit (`f2`):** average relative shortfall below a target depth over lawn cells. The target is a configurable multiple of the baseline mean lawn depth.
- **Dry-area fraction:** share of lawn cells below a configured fraction of the target depth. Pareto candidates must satisfy the configured limit to enter the archive.
- **CU:** a Christiansen-style uniformity metric reported for interpretation; it is not the Pareto search's primary objective.

The standard-grid baseline and the full-circle reference are different comparisons. The full-circle layout is a deliberately naive reference, not a measured existing installation. The project brief reported low baseline overspray (approximately 0–1%) but edge dry patches (5.6–8.1%) for the standard-grid/preset-arc baseline; it did **not** establish an overspray reduction against that baseline.

See [the model definition and limitations](docs/MODEL.md) for formulas and assumptions.

## Historical figures and reproducibility

Numbers quoted in earlier project materials are not presented here as current results because the corresponding raw result CSVs, configuration, and run metadata were not available for independent reproduction. Current claims should be based on committed or linked artifacts that can be rerun and inspected.

## Assumptions and limitations

- All lawn boundaries are synthetic; there is no real-site survey or field validation.
- The radial precipitation profile and throw range are stylized placeholders, not manufacturer specifications.
- Retrofit costs remain placeholders, not verified prices. Annual water savings, annual cost savings, and payback are not computed because AR is dimensionless and the model has no calibrated flow/volume conversion.
- Wind, pressure loss, evaporation, drift, slope, and soil effects are not modelled.
- Water depth is represented in relative model units, not litres.
- Grid-based polygon coverage is approximate and depends on the configured cell size.
- There is no calibrated manufacturer profile, lifecycle-cost analysis, uncertainty study, or operational safety assessment.

Use campOS for exploratory comparisons and method development only—not for construction, irrigation scheduling, procurement, or savings claims.

## Development and tests

Install the development dependencies and run the test suite:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

Tests cover fixed-position coordinate invariance, cache correctness across configurations, Pareto archive behavior, output generation, radial-profile preparation, sensitivity-run metadata, and the guard against deriving water-volume savings from AR. GitHub Actions runs the suite on Python 3.10, 3.11, and 3.12 for pushes and pull requests.

## Project structure

```text
campos_sim.py                 CLI launcher
src/campos/campos_sim.py      Optimization, CLI, and output orchestration
src/campos/model.py            Synthetic geometry, sprinkler field, and base metrics
tests/                        Regression and smoke tests
docs/MODEL.md                 Metrics, assumptions, and limitations
docs/RELEASE_NOTES_v0.1.0.md  Initial prototype notes
examples/                     Reproducible example commands
results/                      Curated results only; no generated files committed by default
```

## Roadmap

The roadmap prioritizes evidence and decision quality over feature count.

- [x] Make the legacy objective and its limitations explicit; keep it as a reproducible baseline.
- [x] Add matched synthetic comparisons, configurable Pareto trade-offs, and sensitivity checks.
- [x] Support custom polygon/layout inputs, configuration provenance, and shareable reports.
- [x] Add radial-profile preparation and an observation-error evaluator with explicit calibration/holdout separation.
- [x] Add geometry-topology checks and numerical regression tests for radial-profile normalization.
- [ ] Publish a small, reviewed set of reproducible synthetic case studies with raw outputs, metadata, and a clear interpretation of each metric.
- [ ] Audit and document the physical chain from pressure and nozzle performance to flow, throw, radial distribution, and applied depth; add conservation and dimensional-consistency tests.
- [ ] Establish a documented validation protocol with predeclared acceptance criteria and truly independent holdout observations.
- [ ] Only after adequate measured data exist, quantify uncertainty and evaluate real-site performance; keep economic analysis disabled until water-volume and cost inputs are defensible.

## Citation

If you use campOS in research, cite the repository and the specific version or commit you used. See [CITATION.cff](CITATION.cff). No DOI has been assigned.

## License

Released under the MIT License; see [LICENSE](LICENSE). Confirm code ownership and third-party license compatibility before making a formal release.


### Observation error evaluation (paired data only)

To report errors separately for calibration and independent holdout observations,
prepare a CSV with `measured_mm,predicted_mm,split` columns, where `split` is
`calibration` or `holdout`, then run:

```bash
python scripts/evaluate_observation_errors.py --input paired_depths.csv --out metrics.json
```

The evaluator reports bias, MAE, RMSE and related descriptive metrics; it does
not generate predictions, tune parameters, verify that holdout data are truly
independent, or declare the model validated. Define acceptance criteria before
evaluating holdout data. See [the configuration and comparison guide](docs/CONFIGURATION_AND_COMPARISONS.md).
