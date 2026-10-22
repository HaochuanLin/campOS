# Model definition, metrics, and limitations

This document describes the current implementation in `src/campos/campos_sim.py`. It is a description of the code, not evidence that the model matches real-world irrigation performance.

## Geometry and discretization

The five built-in lawn outlines are synthetic polygons. The domain is rasterized to cell-center points at the configured `cell` resolution. A point-in-polygon mask separates lawn cells from surrounding cells. Reported lawn area is the number of masked cells multiplied by the cell area, so it is a grid-based approximation of polygon area.

The baseline layout is a square grid with edge heads assigned preset arc angles. The implementation evaluates three candidate radii and nine grid offsets using the legacy AR score. The same cached baseline is reused across modes when the geometry and configuration match.

## Sprinkler field

Each sprinkler contributes a stylized relative depth field. For distance (d) from a head and throw radius (r), the radial profile inside the radius and sector is:

[
q(d) = 1.5\left(1 - 0.5\frac{d}{r}\right), \qquad 0 \le d \le r
]

Overlapping fields are added. The profile is a placeholder, not a calibrated manufacturer precipitation curve. Radius and arc angle are optimization parameters; there is no hydraulic flow, pressure, or weather model.

## Legacy single-objective metric

Let (n) be the number of lawn cells, (LQ) the mean depth of the driest 25% of those cells, and (W) the sum of the modelled field over the full simulated grid, including the surrounding area. The reported legacy AR metric is:

[
AR = \frac{W}{n\,LQ}
]

Lower AR is preferred by the single-objective optimizer. A penalty is added when the share of lawn cells below the configured fraction of that layout's own mean depth exceeds the dry-area limit.

The reported AR-based saving metric is (1 - AR_{optimized}/AR_{baseline}). It is a comparison of this model-specific score, not a direct calculation of the change in total discharge. The optimized total field can increase even when AR improves.

## Pareto objectives

The Pareto modes normalize the objectives against the standard-grid baseline for the same site:

- (W_0): total baseline field over the entire simulation grid.
- (T): configured target factor multiplied by the baseline mean depth on lawn cells.
- (f_1): water outside the polygon divided by (W_0).
- (f_2): mean over lawn cells of the relative shortfall below (T).
- (D): share of lawn cells whose depth is below the configured dry threshold times (T).

In formula form:

[
f_1 = \frac{W_{outside}}{W_0}
]

[
f_2 = \frac{1}{n}\sum_{i=1}^{n}\max\left(0, 1 - \frac{d_i}{T}\right)
]

[
D = \frac{\#\{i : d_i < \tau T\}}{n}
]

where (d_i) is the depth at lawn cell (i) and (	au) is `dry_thresh_frac`. Only candidate states satisfying (D \le D_{max}) are offered to the Pareto archive. The weighted objective used during simulated annealing is a search mechanism; it is not presented as a combined final score.

The Pareto archive is approximate: points within the configured objective tolerance may be discarded to control archive size. The final front is thinned before CSV/plot generation.

## Reported secondary metrics

- **Overspray share of own water:** outside-field total divided by that layout's own total field. This is not the same denominator as (f_1).
- **CU:** a Christiansen-style uniformity statistic computed over lawn cells.
- **Dry-area fraction:** share of lawn cells below the selected threshold.
- **Placeholder economics:** annual water volume, annual cost savings, retrofit cost, and payback are computed from placeholder tariff, irrigation-depth, and retrofit-cost assumptions. They are not estimates suitable for a real property.

## Baselines and comparisons

The standard-grid/preset-arc layout is the main baseline for AR and Pareto normalization. The full-circle reference uses the same baseline head positions and radii but changes every arc to a full circle. It is a deliberately naive reference, not a measured existing installation. Results against that reference must not be described as improvements over a real installed system.

## Known omissions

The current implementation does not model:

- Wind, spray drift, evaporation, or weather variation.
- Pressure loss, hydraulic network behavior, flow-rate curves, or manufacturer-specific precipitation profiles.
- Terrain slope, soil infiltration, runoff, or plant response.
- Survey uncertainty, sensor noise, parameter uncertainty, or measured field validation.

All results are synthetic and model-dependent. Do not use them as construction instructions, operating schedules, procurement specifications, or guaranteed savings claims.
