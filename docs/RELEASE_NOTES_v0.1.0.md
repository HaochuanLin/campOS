# campOS v0.1.0 — Initial prototype release

## Included
- Synthetic irregular-lawn geometry and rotary-sprinkler simulation prototype.
- Simulated-annealing AR optimization in fixed-position and movable modes.
- Pareto search for overspray versus interior deficit.
- CSV and PNG output generation.
- Basic regression tests and GitHub Actions CI.

## Important caveats
- Synthetic shapes only; no field data or field validation.
- Sprinkler profile/range and economic assumptions are placeholders.
- Wind, pressure loss, evaporation, drift, slope, and soil are not modelled.
- AR-based saving is not equivalent to total-water-use reduction; optimized total discharge may be higher.
- This release is an exploratory prototype, not an engineering design or savings guarantee.

## Before tagging the release
- Add the intended result images and original CSV files, if they are cleared for public release.
- Run `python -m pytest -q` on the target platform.
- Confirm ownership and suitability of the provisional MIT license.
