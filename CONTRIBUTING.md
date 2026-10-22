# Contributing to campOS

Thank you for considering a contribution. campOS is a research prototype, so clarity about assumptions and reproducibility is more important than making results look favorable.

## Before opening an issue

Include the command used, Python version, dependency versions, operating system, relevant output files, and the generated `run_metadata.json`. For suspected numerical bugs, provide the smallest configuration that reproduces the issue.

## Pull requests

- Keep documentation and user-facing output in English.
- Do not silently change default parameters, the default random seed, or optimization behavior.
- If a numerical change is necessary, explain the motivation and expected impact, add a regression test, and identify which outputs may change.
- Keep generated runs out of the repository unless the CSVs, figures, metadata, and provenance have been reviewed together.
- Do not present synthetic results as field measurements or placeholder costs as market data.
- Prefer small, focused changes that can be tested independently.

## Development setup

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python campos_sim.py --mode movable --quick --sites A --outdir out/demo
```

The quick run is a smoke test, not a scientific validation. Full runs may take substantially longer.

## Reporting results

When publishing a result, include the exact command, the generated `run_metadata.json`, CSV outputs, and figures. State whether `--quick` was used. If a claim depends on real-world performance, provide a documented validation protocol and the relevant measurements.
