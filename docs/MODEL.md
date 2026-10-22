# Model definition, metrics, and limitations

This document describes the current implementation in `src/campos/campos_sim.py`. It documents the code; it does not establish that the model matches real-world irrigation performance.

## Geometry and discretization

The five built-in lawn outlines are synthetic polygons. The surrounding simulation domain is rasterized to cell-center points at the configured `cell` resolution. A point-in-polygon mask separates lawn cells from surrounding cells. Reported lawn area is the number of masked cells multiplied by the cell area, so it is a grid-based approximation of polygon area.

The baseline layout is a square grid with edge heads assigned preset arc angles. The implementation evaluates three candidate radii and nine grid offsets using the legacy AR score. A cached baseline is reused only when the site geometry and configuration match.

## Sprinkler field

Each sprinkler contributes a stylized relative depth field. For distance `d` from a head and throw radius `r`, the radial profile inside the radius and sector is:

```text
q(d) = 1.5 * (1 - 0.5 * d/r), for 0 <= d <= r
```

Overlapping fields are added. This profile is a placeholder, not a calibrated manufacturer precipitation curve. Radius and arc angle are optimization parameters; there is no hydraulic flow, pressure, or weather model.

## Legacy single-objective metric

Let:

- `n` be the number of lawn cells.
- `LQ` be the mean depth of the driest 25% of lawn cells.
- `W` be the sum of the modelled field over the full simulated grid, including the surrounding area.

The reported legacy AR metric is:

```text
AR = W / (n * LQ)
```

Lower AR is preferred by the single-objective optimizer. A penalty is added when the share of lawn cells below the configured fraction of that layout's own mean depth exceeds the dry-area limit.

The reported AR-based saving metric is `1 - AR_optimized / AR_baseline`. It compares this model-specific score; it is not a direct measurement of the change in total discharge. The optimized total field can increase even when AR improves.

## Pareto objectives

The Pareto modes normalize their objectives against the standard-grid baseline for the same site:

- `W0`: total baseline field over the entire simulation grid.
- `T`: configured target factor multiplied by the baseline mean depth on lawn cells.
- `f1`: water outside the polygon divided by `W0`.
- `f2`: mean relative shortfall below `T` over lawn cells.
- `D`: share of lawn cells whose depth is below the configured dry threshold times `T`.

In formula form:

```text
f1 = W_outside / W0
f2 = (1 / n) * sum(max(0, 1 - d_i / T))
D  = count(d_i < tau * T) / n
```

Here, `d_i` is the depth at lawn cell `i`, and `tau` is `dry_thresh_frac`. Only candidate states satisfying `D <= D_max` are offered to the Pareto archive. The weighted objective used during simulated annealing is a search mechanism, not a combined final score.

The Pareto archive is approximate: points within the configured objective tolerance may be discarded to control archive size. The final front is thinned before CSV and plot generation.

## Reported secondary metrics

- **Overspray share of own water:** outside-field total divided by that layout's own total field. This denominator differs from `W0` used by `f1`.
- **CU:** a Christiansen-style uniformity statistic computed over lawn cells.
- **Dry-area fraction:** share of lawn cells below the selected threshold.
- **Economic outputs:** retrofit cost is still a placeholder estimate based on configured per-head costs. Annual water savings, annual monetary savings, and payback are deliberately not estimated and are written as blank CSV fields. The legacy AR metric is dimensionless; its difference cannot be multiplied by annual irrigation depth and lawn area to obtain a physical water volume. A defensible payback estimate requires a calibrated water-volume or flow model, verified irrigation demand, tariffs, and installation costs.

## Baselines and comparisons

The standard-grid/preset-arc layout is the main baseline for AR and Pareto normalization. The full-circle reference uses the same baseline head positions and radii but changes every arc to a full circle. It is a deliberately naive reference, not a measured existing installation. Results against that reference must not be described as improvements over a real installed system.

## Known omissions

The current implementation does not model:

- Wind, spray drift, evaporation, or weather variation.
- Pressure loss, hydraulic network behavior, flow-rate curves, or manufacturer-specific precipitation profiles.
- Terrain slope, soil infiltration, runoff, or plant response.
- Survey uncertainty, sensor noise, parameter uncertainty, or measured field validation.

All results are synthetic and model-dependent. Do not use them as construction instructions, operating schedules, procurement specifications, or guaranteed savings claims.
