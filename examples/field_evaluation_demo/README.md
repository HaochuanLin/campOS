# Synthetic field-evaluation workflow smoke example

**This folder contains synthetic software-test inputs only. It is not field data, is not a calibration dataset, and must not be cited as evidence of model validity or water savings.**

The polygon, sprinkler layout, flow, and observations are deliberately chosen to exercise the end-to-end command. The observation values are consistent with the simplified uniform radial model at 1 L/min per head for a 600-second collection period.

From the repository root after installing the project (`python -m pip install -e ".[dev]"`), run:

```bash
campos-field-evaluate \
  --polygon-csv examples/field_evaluation_demo/site_polygon.csv \
  --heads-csv examples/field_evaluation_demo/sprinkler_layout.csv \
  --observations examples/field_evaluation_demo/catch_can_observations.csv \
  --flow-lpm 1.0 \
  --outdir out/field-evaluation-demo
```

Expected outputs:

- `out/field-evaluation-demo/paired_predictions.csv`
- `out/field-evaluation-demo/field_evaluation_metrics.json`

Use these files to confirm that the command and output schema work. Replace every synthetic input with documented surveyed geometry, measured sprinkler layout, measured per-head flow, and actual catch-can observations before doing any real-site evaluation.
