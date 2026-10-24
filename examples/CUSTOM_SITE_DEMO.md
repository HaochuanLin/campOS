# Custom-site CSV demo

The files beside this note are illustrative geometry/layout inputs for exercising the custom-site CLI. They are not a survey, a recommended installation, or field-validation data.

```bash
python campos_sim.py --mode fixed --quick --cell-size 1.0 \
  --polygon-csv examples/custom_site_demo_polygon.csv \
  --heads-csv examples/custom_site_demo_heads.csv \
  --outdir out/custom-site-demo
```

The polygon uses `x_m,y_m`; the sprinkler file uses `x_m,y_m,radius_m,start_angle_deg,arc_width_deg`. Replace the example coordinates and head settings with documented site measurements before evaluating a real site. See [custom-site input rules](../docs/CUSTOM_SITE_INPUTS.md) and the [real-site validation protocol](../docs/REAL_SITE_VALIDATION_PROTOCOL.md).
