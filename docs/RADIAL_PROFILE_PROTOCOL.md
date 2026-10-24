# Radial profile measurement and preparation protocol

## Purpose and limits

A radial profile describes the *shape* of a sprinkler's application rate with distance from the head. It does not by itself establish absolute flow, the overlap field of multiple heads, or field performance. Use measurements for the exact sprinkler/nozzle, operating pressure, and arc mode you intend to model.

The current loader expects \`radius_fraction,relative_rate\` where the normalized radius runs from 0 to 1. This preparation workflow converts raw catch-can depth readings into that format. It does not turn manufacturer flow/throw tables into a radial profile.

## Suggested measurement record

Record, at minimum:

- Manufacturer, sprinkler model, nozzle identifier, nozzle trajectory, and full/part-circle setting.
- Measured operating pressure at the sprinkler while running; pressure gauge location and any pressure fluctuation.
- Catch-can geometry and opening area, measurement method (depth or mass), test duration, and units.
- Actual throw radius used to normalize distance; note how the endpoint was determined.
- Measurement date, test location, wind speed/direction, temperature if relevant, and whether the test was indoors or outdoors.
- Multiple radial transects / directions and repeated runs. Retain the raw readings; do not publish only a smoothed profile.

A standard-style single-sprinkler radial test commonly places catch cans along one or more radial lines and derives application rates from collected depth and elapsed time. Test design and uncertainty matter; see Saretta et al. (2018), [Test methods for characterising the water distribution from irrigation sprinklers](https://doi.org/10.1016/j.biosystemseng.2018.01.011). Follow applicable safety guidance and formal test standards for any engineering use.

## Raw CSV format

Start from \`data/templates/catch_can_observations_template.csv\`. Required columns:

- \`radius_fraction\`: measured distance from the sprinkler centre divided by the measured throw radius, in [0, 1].
- \`depth_mm\`: collected water depth in millimetres for that reading.
- \`run_minutes\`: duration for that reading, in minutes.

Include repeated rows at the same normalized radius for different transects or repetitions. The utility converts each reading to mm/h, averages rates at each radius, and expresses the result relative to the arithmetic mean across the measured radius nodes. The simulator then applies its own area-weighted normalization when loading the profile.

The utility requires at least three distinct radius values, including 0 and 1, positive depths and durations, and finite numeric values. It deliberately rejects missing endpoints rather than silently inventing extrapolated values. In practice, a catch can may not be placeable at the exact sprinkler centre. If the center endpoint is estimated from a nearby measurement or another method, document that estimation in the test record; do not label it as a direct measurement. Likewise, the outer endpoint should correspond to the observed throw boundary, not an arbitrary catalog radius.

## Prepare and use a profile

\`\`\`bash
python scripts/prepare_radial_profile.py \\
  data/my_test/catch_can_observations.csv \\
  data/my_test/radial_profile.csv

python campos_sim.py --mode pareto-fixed --quick --sites A \\
  --profile-csv data/my_test/radial_profile.csv \\
  --outdir out/measured-profile
\`\`\`

The example is a workflow template, not a real dataset. Do not use an empty template or fabricated values as a measured profile. Keep the original readings and test conditions with the derived profile so another person can reproduce the transformation.

## What this does not validate

- The manufacturer pressure/flow/throw curve and the radial catch-can profile are different evidence. The former constrains total discharge and reach; the latter describes spatial distribution.
- Area-normalization removes the absolute rate scale. Supply a separate measured performance curve with \`--performance-csv\` and \`--pressure-kpa\` if you want the model to estimate precipitation in mm/h.
- Wind, evaporation, pressure loss in the pipe network, sector-specific flow behavior, soil response, and multiple-head field measurements remain outside the current model.
- Comparing a fitted profile with the same catch-can data used to create it is calibration, not independent validation. Reserve separate conditions or measurements for validation and report uncertainty.

## Public benchmark already included

\`data/benchmarks/rainbird_5000_standard_1_5.csv\` transcribes published aggregate performance-chart data. Its mass-balance check is useful for units and total application rate, but the manufacturer chart does not provide the local radial catch-can profile needed here. See \`data/benchmarks/README.md\` for source and limitations.
