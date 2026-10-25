# Contributing to campOS

Thanks for helping improve campOS. This is a research prototype for reproducible sprinkler-layout comparisons. Correctness, clear assumptions, and honest evidence matter more than making a result look favorable.

**Live demo:** https://campos-optimizer.streamlit.app/

## Before reporting a bug

Include, where possible:
- The exact command or UI action.
- Python version, operating system, and dependency versions.
- The smallest input/configuration that reproduces the issue.
- The error message and relevant generated metadata.
- Whether the run used synthetic inputs, measured inputs, or a mixture.

Remove private site details, credentials, and sensitive location information before sharing logs or datasets.

## Pull request expectations

- Keep user-facing documentation in English and keep it consistent with the current app.
- Explain the problem being solved and the behavior that should change.
- Add or update tests for bug fixes and numerical changes.
- Do not silently change default settings, random seeds, metric definitions, or optimization semantics.
- For algorithm changes, state units, assumptions, expected trade-offs, and possible changes to output files.
- Preserve reproducibility: record relevant configuration and update documentation when outputs change.
- Never present synthetic outputs, placeholder costs, or calibration-set fit as independent field evidence.
- Avoid committing generated output directories unless the artifacts are intentionally reviewed and required.

## Local development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python campos_sim.py --mode movable --quick --sites A --outdir out/demo
```

To run the web UI:

```bash
python -m pip install -e ".[ui]"
streamlit run streamlit_app.py
```

A quick run is a software smoke test, not scientific validation.

## Reviewing a result

When reporting or publishing results, include the command, seed, configuration, input provenance, relevant CSVs/figures, and `run_metadata.json`. State whether quick mode was used. For claims about real-world water distribution or savings, include the measurement protocol, acceptance criteria, and independent evaluation data.
