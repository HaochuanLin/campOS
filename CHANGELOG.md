# Changelog

## [0.1.0] - Unreleased

### Added
- English-only project README with quick-start commands, mode descriptions, metric definitions, assumptions, and limitations.
- Model documentation covering the grid approximation, objective functions, and known omissions.
- Installable package metadata and the `campos-sim` command-line entry point.
- Per-run JSON metadata recording selected modes/sites, configuration, and software versions.
- English CSV column names for single-objective, comparison, and Pareto outputs.
- Regression tests for fixed-position invariance, cache correctness, dry-threshold behavior, Pareto archive behavior, metadata, and CLI output generation.
- CI matrix for Python 3.10, 3.11, and 3.12.

### Clarifications
- The default optimization parameters and random seed remain unchanged. The code changes in this iteration address cache correctness, metadata, and output labels rather than changing the optimization objective.
- Result CSVs and figures from the original project brief were not present in the source attachment. No result images have been fabricated.
- Site geometry and physical/economic inputs remain synthetic or placeholders; no field validation is claimed.
- Verify code ownership and third-party license compatibility before making a formal release.
