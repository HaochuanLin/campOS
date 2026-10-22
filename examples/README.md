# Example runs

Run these commands from the repository root after installing dependencies:

```bash
# Fast smoke run: one synthetic rectangle, movable-head mode
python campos_sim.py --mode movable --quick --sites A --outdir out/demo

# Fixed-position retrofit exploration on two synthetic shapes
python campos_sim.py --mode fixed --sites A C --outdir out/fixed

# Pareto trade-off for a synthetic kidney-shaped lawn
python campos_sim.py --mode pareto-fixed --quick --sites C --outdir out/pareto

# Full run across all modes and synthetic sites (can take substantially longer)
python campos_sim.py --mode all --outdir out/full
```

Each run writes CSV summaries and PNG plots to the selected output directory. Generated outputs are ignored by Git by default; copy only reviewed, reproducible artifacts into the repository when you want to publish them.

All sites are synthetic and all sprinkler/economic assumptions remain placeholders. See the root [README](../README.md) for metric definitions and limitations.
