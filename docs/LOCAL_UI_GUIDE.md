# campOS local UI guide

## Start the app

Install the optional UI dependency and launch the local app:

```bash
python -m pip install -e ".[ui]"
streamlit run src/campos/app.py
```

The app runs locally. It is a user interface for the research prototype, not a hosted service or a certified engineering tool.

## Synthetic mode

Leave **Use surveyed site CSVs** unchecked, select one or more built-in site shapes, choose an optimization mode, random seed, and grid cell size, then run. The comparison mode evaluates fixed-position and movable-head search on the same synthetic sites. A seed and cell size are displayed with the result and are forwarded to the simulator.

## Surveyed-site mode

Check **Use surveyed site CSVs** and upload two CSV files:

- Lawn polygon: `x_m,y_m` columns, at least three distinct vertices, coordinates in metres. An optional repeated closing vertex is accepted.
- Sprinkler layout: `x_m,y_m,radius_m,start_angle_deg,arc_width_deg` columns. Head coordinates must lie inside the polygon; radius must be within the optimizer's configured bounds; arc width must be in (0, 360].

The UI offers downloads of the repository's blank polygon and sprinkler-layout templates. Replace template values with surveyed measurements; do not use the template rows as real site data.

Choose a single mode in surveyed-site mode. The app runs the custom geometry and layout using the selected seed and grid resolution. In Pareto modes, you may also upload a separate road/sidewalk polygon. It must not overlap the lawn interior; sharing a boundary is allowed. The protected-surface objective is only active in Pareto modes.

## Reading results

Inspect all generated CSVs and plots, not just the first score. The run's seed and grid resolution are shown in the UI. Downloaded run metadata records input provenance when the underlying CLI supports it.

A successful run only means the simulation completed. It does not prove that the model predicts actual spray distribution, road wetting, water savings, or a safe installation. Wind/drift, pressure loss, evaporation, and network hydraulics remain incompletely modelled.

## Field measurements

The UI does not fabricate catch-can observations or treat synthetic example rows as field data. To compare predictions with measurements, use the field-evaluation workflow documented in [the real-site validation protocol](REAL_SITE_VALIDATION_PROTOCOL.md). Preserve raw observations, split complete runs into calibration or holdout, pre-register acceptance thresholds, and do not tune on holdout data.
