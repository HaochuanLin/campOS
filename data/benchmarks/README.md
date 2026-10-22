# Public benchmark data provenance

File: `rainbird_5000_standard_1_5.csv`

The six rows transcribe the Rain Bird 5000 Series standard-angle nozzle performance chart for nozzle 1.5 at 2.0–4.5 bar. Pressure is converted to kPa (1 bar = 100 kPa); flow is copied from the chart's L/min column; throw radius is copied from its radius column. Square/triangular precipitation columns are the chart's published mm/h values.

Source: Rain Bird, *5000 Series Rotor Nozzle Performance Chart*, official PDF:
https://www.rainbird.com/sites/default/files/media/documents/2020-09/5000-series-rotor-nozzle-performance-chart.pdf

The manufacturer notes that precipitation rates are based on half-circle operation and that square and triangular spacing use 50% of throw diameter; the performance data are reported for zero-wind conditions and according to ASABE S398.1. These values are manufacturer performance-chart data, not raw catch-can measurements or an independent validation dataset.

The benchmark compares the chart's nominal precipitation rates with a simple flow/spacing-area mass-balance estimate. A tolerance of 1 mm/h accounts for the chart's integer rounding. Passing this check verifies consistency with the published table at this coarse level; it does not validate the spatial radial pattern, overlap field, wind response, or field performance.
