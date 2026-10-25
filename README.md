# campOS

**Compare sprinkler layouts. Make overspray and coverage trade-offs visible. Validate with measurements before relying on predictions.**

[**▶ Open the live campOS demo**](https://campos-optimizer.streamlit.app/) · [Source code](https://github.com/HaochuanLin/campOS) · [Report a bug](https://github.com/HaochuanLin/campOS/issues)

[![Tests](https://github.com/HaochuanLin/campOS/actions/workflows/tests.yml/badge.svg)](https://github.com/HaochuanLin/campOS/actions/workflows/tests.yml)
[![UI smoke](https://github.com/HaochuanLin/campOS/actions/workflows/ui-smoke.yml/badge.svg)](https://github.com/HaochuanLin/campOS/actions/workflows/ui-smoke.yml)
[![Python 3.10–3.12](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Research prototype — not field validated.** Built-in sites are synthetic. Results depend on discretization, assumed or supplied sprinkler characteristics, and the chosen objective. Do not use outputs as installation instructions or as evidence of guaranteed water savings.

## Start here

You do not need field data to try the demo.

1. Open the **[live app](https://campos-optimizer.streamlit.app/)**.
2. Keep **Use surveyed site CSVs** unchecked to run a reproducible synthetic example.
3. Choose an optimization mode and site, then click **Run simulation**.
4. Inspect the metrics, plots, execution details, and generated artifacts.
5. Download the complete run ZIP if you want to preserve the outputs.

The hosted app uses temporary runtime storage. Download anything you need to keep, and do not upload private surveys or sensitive location data to a public demo.

### What the modes mean

| Mode | Purpose |
|---|---|
| `compare` | Compare the built-in fixed-head and movable-head scenarios. |
| `fixed` | Search while keeping existing head positions fixed. |
| `movable` | Explore candidate head positions. |
| `pareto-fixed` | Explore the overspray-versus-interior-coverage trade-off with fixed heads. |
| `pareto-movable` | Explore that trade-off while allowing head positions to move. |

Exact objective definitions and metric caveats are documented in [the model reference](docs/MODEL.md) and [objective audit](docs/OBJECTIVE_AUDIT.md).

## What campOS is for

campOS is an open, reproducible decision-support prototype for comparing sprinkler layouts on irregular lawn boundaries. Its motivating problem is simple: water can land outside the intended lawn while parts of the lawn still receive too little water. A single score can hide that trade-off.

The project aims to make comparisons inspectable: preserve inputs and assumptions, compare alternatives under matched conditions, show multiple metrics, and provide a path to evaluate predictions against catch-can measurements.

**What it can do today**
- Run repeatable synthetic sprinkler-layout comparisons.
- Explore fixed-position and movable-head optimization.
- Include a protected road/sidewalk polygon in supported Pareto modes.
- Import a site polygon and sprinkler layout in metric coordinates.
- Generate reports, plots, machine-readable outputs, and reproducibility metadata.
- Check field-observation CSV quality and compare predicted depths with observed catch-can measurements.
- Experiment with an optional AI residual correction workflow, with calibration/holdout separation.

**What it has not established**
- That predictions match a real sprinkler system.
- That a recommended layout reduces actual water use or road wetting.
- That wind, drift, evaporation, pressure variation, soil infiltration, hydraulics, and all site constraints are represented adequately.
- That an AI correction generalizes to new sites or operating conditions.

A more complex optimizer cannot compensate for inaccurate inputs or an unvalidated physical model. Treat all outputs as exploratory until independent field evaluation supports the relevant claim.

## Run locally

Requires Python 3.10 or newer.

```bash
git clone https://github.com/HaochuanLin/campOS.git
cd campOS
python -m pip install -e ".[dev]"
python -m pytest -q
```

Run the command-line simulator:

```bash
campos-sim --help
python campos_sim.py --mode movable --quick --sites A --outdir out/demo
```

The `--quick` run is a smoke test, not scientific validation.

### Start the web interface locally

```bash
python -m pip install -e ".[ui]"
streamlit run streamlit_app.py
```

For a guided local setup and troubleshooting, see [the local UI guide](docs/LOCAL_UI_GUIDE.md).

## Use your own site data

The UI accepts CSV inputs for a lawn polygon and sprinkler layout. Coordinates and radii must use metres. Optional inputs include a measured radial distribution profile, pressure/flow/throw performance data, catch-can observations, and a protected road/sidewalk polygon for Pareto modes.

Start with the [custom-site input guide](docs/CUSTOM_SITE_INPUTS.md) and download the example files under [data/templates](data/templates/). Do not label illustrative values as measurements.

For observation quality checks:

```bash
campos-observation-qc --help
```

For pointwise prediction and calibration/holdout evaluation:

```bash
campos-field-evaluate --help
```

The evaluation workflow requires appropriately documented geometry, layout, flow and observation inputs. Reserve independent holdout data for evaluation; do not tune the model on the same observations and then report those observations as independent validation. See the [real-site validation protocol](docs/REAL_SITE_VALIDATION_PROTOCOL.md).

## Reproducibility and outputs

A run can produce CSV data, JSON metadata, plots, HTML/Markdown reports, and a ZIP bundle through the UI. Keep the command, seed, configuration, input files, software version, and generated metadata with any result you share.

To run the synthetic quickstart and verify the generated artifact manifest:

```bash
python -m pip install -e ".[dev]"
campos-start --help
campos-verify-artifacts --help
```

See [artifact integrity](docs/ARTIFACT_INTEGRITY.md) for what the SHA-256 manifest verifies. File integrity is not model accuracy.

## Deployment and test evidence

- [Live Streamlit app](https://campos-optimizer.streamlit.app/)
- [Python test workflow](https://github.com/HaochuanLin/campOS/actions/workflows/tests.yml)
- [UI smoke workflow](https://github.com/HaochuanLin/campOS/actions/workflows/ui-smoke.yml)
- [Artifact integrity workflow](https://github.com/HaochuanLin/campOS/actions/workflows/artifact-integrity.yml)
- [Hosted-app reachability monitor](https://github.com/HaochuanLin/campOS/actions/workflows/hosted-smoke.yml)
- [Phase 1 acceptance checklist](docs/PHASE1_ACCEPTANCE.md)
- [Evidence-based scorecard and small delivery stages](docs/SCORECARD_AND_DELIVERY_PLAN.md)

Local CI tests and hosted reachability checks answer different questions. A successful local Streamlit test does not prove the deployed service is reachable; a rendered landing page does not prove the simulation and downloads work. The hosted monitor has previously observed redirects to authentication paths, while a user-provided browser screenshot showed the landing page rendering. This discrepancy must be resolved by checking the current monitor result and Streamlit Community Cloud configuration rather than treating either observation as conclusive.

## Project documents

- [Project charter and scope](docs/PROJECT_CHARTER.md)
- [Model definition and limitations](docs/MODEL.md)
- [Objective-function audit](docs/OBJECTIVE_AUDIT.md)
- [Configuration and comparison methodology](docs/CONFIGURATION_AND_COMPARISONS.md)
- [Model development roadmap](docs/MODEL_DEVELOPMENT_ROADMAP.md)
- [Importing a custom site](docs/CUSTOM_SITE_INPUTS.md)
- [Real-site data requirements](docs/REAL_SITE_DATA.md)
- [Real-site validation protocol](docs/REAL_SITE_VALIDATION_PROTOCOL.md)
- [Radial-profile measurement protocol](docs/RADIAL_PROFILE_PROTOCOL.md)
- [Phase 1 acceptance checklist](docs/PHASE1_ACCEPTANCE.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Development priorities

1. Verify numerical invariants, geometry handling, grid sensitivity, and objective semantics.
2. Improve hosted deployment and real-browser acceptance evidence.
3. Calibrate the physical model with documented sprinkler measurements.
4. Evaluate against pre-registered thresholds on independent holdout observations.
5. Only then assess whether field trials support claims about reduced overspray or water use.

## License

campOS is distributed under the MIT License. See [LICENSE](LICENSE).
