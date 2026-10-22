# campOS v0.1.0 — Initial prototype release notes

## Included
- Synthetic irregular-lawn geometry and rotary-sprinkler simulation prototype.
- Simulated-annealing AR optimization in fixed-position and movable modes.
- Pareto search for overspray versus interior deficit.
- CSV and PNG output generation, plus per-run JSON metadata.
- English-only documentation, installable package metadata, regression tests, and GitHub Actions CI.

## Important caveats
- Synthetic shapes only; no field data or field validation.
- Sprinkler profile/range and economic assumptions are placeholders.
- Wind, pressure loss, evaporation, drift, slope, and soil are not modelled.
- The AR-based saving metric is not equivalent to total-water-use reduction; optimized total discharge may be higher.
- This release is an exploratory prototype, not an engineering design or savings guarantee.
- Preliminary figures mentioned in the project brief cannot be independently verified because the source CSVs and run configuration were not supplied.

## Before tagging a formal release
- Generate and review selected full-run CSVs, `run_metadata.json`, and figures.
- Run `python -m pytest -q` on supported Python versions.
- Confirm ownership and suitability of the MIT license.
- Assign a version tag only after the source, documentation, and reproducibility artifacts have been reviewed together.
