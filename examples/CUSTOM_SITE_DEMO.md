# Custom-site CSV demo (synthetic only)

This example demonstrates the custom CSV input pathway. The rectangle and four sprinkler records are invented test geometry and **are not measurements from a campus or a real installed system**.

Run from the repository root:

```bash
python campos_sim.py --mode fixed --quick --cell-size 1.0 --polygon-csv examples/custom_site_demo_polygon.csv --heads-csv examples/custom_site_demo_heads.csv --outdir out/custom-site-demo
```

The run treats the four supplied heads as the baseline and keeps their x/y coordinates fixed in fixed mode. Throw, arc, and radial water distribution remain simplified assumptions. The output is a software demonstration, not an engineering design or water-saving estimate.

For a real case, follow [the data contract](../docs/REAL_SITE_DATA.md) and [validation protocol](../docs/VALIDATION_PROTOCOL.md). Do not commit private campus maps or unapproved field measurements to this public repository.
