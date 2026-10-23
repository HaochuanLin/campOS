# Field validation protocol (planned workflow)

The purpose of this protocol is to prevent a plausible-looking heat map from being mistaken for evidence of accurate irrigation performance. This is a proposed process for future authorized campus pilots; no field validation is claimed by the current repository.

## 1. Define the question before measuring

Choose one irrigation zone and state the question in advance, for example:

- Does the model reproduce the spatial pattern of collected water under the tested configuration?
- Does it identify the same low-application areas as the field audit?
- Does a proposed layout improve a pre-registered metric without violating installation constraints?

Do not combine several zones, sprinkler types, pressures, and weather conditions into one undifferentiated dataset. Record the exact sprinkler/nozzle model, arc setting, pressure, run duration, zone boundaries, and whether all heads were operating as intended.

## 2. Capture the as-built baseline

Before changing anything:

1. Survey or digitize the lawn boundary and document the local coordinate frame.
2. Record every sprinkler centre, head/nozzle model, nominal throw, arc direction and width, and zone/valve membership where known.
3. Record observed defects, blocked heads, leakage, visible pressure problems, slope, nearby pavement, and relevant obstacles.
4. Photograph the test arrangement only with permission and without exposing sensitive site details.
5. Preserve the raw files and record their provenance; never overwrite raw measurements with corrected values.

## 3. Measure applied water

A catch-can test is a practical way to sample actual application. Use identical, level collectors placed in a documented grid or other justified layout, including positions near heads, between heads, and in suspected dry or overspray areas. Use enough collectors to represent the zone; extension guidance commonly describes at least 16 collectors for some tests, while lawn-specific procedures may call for more depending on zone size and head spacing. Follow an appropriate local or professional protocol rather than treating one collector count as universal.

Run the system at its normal operating pressure and record start/end time. Measure the water depth or volume in each collector, its location, and the operating conditions. Avoid interpreting a windy, obstructed, or unstable-pressure test as a clean measurement of nominal sprinkler behaviour. If feasible, repeat the test to quantify repeatability.

References for practical methods:
- [University of Maryland Extension: Irrigation System Check-ups](https://www.extension.umd.edu/resource/irrigation-system-check-ups)
- [University of Minnesota Extension: Auditing home lawn irrigation systems](https://extension.umn.edu/garden-and-home/yard-and-garden/lawns-and-landscapes-in-minnesota/auditing-home-lawn-irrigation-systems)
- [UF/IFAS: Measuring uniformity of water application](https://ask.ifas.ufl.edu/publication/AE194)

## 4. Separate calibration from validation

Do not use the same observations both to tune a model and to claim independent validation.

- **Calibration set:** data used to estimate radial-profile parameters or other model parameters.
- **Validation set:** separate runs, collectors, or zones held out from parameter fitting.
- **Test conditions:** document whether pressure, nozzle, arc, weather, and runtime match the calibration conditions.

For a first prototype, a simple split across repeated runs or zones may be more practical than a complex statistical scheme. State exactly how the split was made. If the dataset is too small for a holdout, report the result as calibration / exploratory fit, not independent validation.

## 5. Compare the model with observations

Compare predictions and measurements at matching coordinates and units. Report at least:

- mean application depth and total measured volume where the measurement method supports it;
- spatial error (for example MAE and RMSE in mm) at collector locations;
- distribution-uniformity metrics computed with a clearly specified formula;
- low-application locations and whether the model identifies the same regions;
- repeatability across runs;
- the number of measurements, missing observations, and any excluded points with reasons.

Do not compare only a smoothed plot. Publish a machine-readable table of observed and predicted values, the metric definitions, and a plot with the same spatial reference. If absolute flow or depth cannot be measured reliably, do not report water savings in litres or cubic metres.

## 6. Evaluate a proposed layout safely

Before an actual layout change, have a qualified irrigation professional review the candidate against as-built pipe routes, valves, pressure/flow limits, manufacturer instructions, accessibility, utility locations, maintenance practices, and applicable requirements. A simulation cannot infer these constraints from a lawn polygon alone.

If an authorized pilot proceeds, use a pre/post or matched-zone design where feasible. Keep run time, operating pressure, nozzle configuration, and weather as comparable as possible. Record all changes. Do not claim that an optimized layout saved water solely because a dimensionless score or simulated field value decreased.

## 7. Release decision gates

A real-site result should not be called validated until the repository contains:

- a documented data source and permission status;
- input schemas and units;
- code version and run metadata;
- the calibration/validation split;
- measured-versus-predicted data and metrics;
- known limitations and an independent technical review.

Until then, use the terms *synthetic experiment*, *simulation candidate*, or *preliminary comparison*. No current repository result establishes field performance or guaranteed water savings.
