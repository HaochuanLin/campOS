# campOS model development roadmap

This roadmap prioritizes evidence and decision quality over feature count. The repository's current detailed scope and acceptance contracts are maintained in [the project charter](PROJECT_CHARTER.md), [the objective audit](OBJECTIVE_AUDIT.md), [the validation plan](VALIDATION_PLAN.md), and [the real-site validation protocol](REAL_SITE_VALIDATION_PROTOCOL.md).

## Current foundation

Implemented in the current branch:
- Synthetic polygon generation and grid-based sprinkler-field calculations.
- Fixed-position and movable-head optimization, plus a two-objective Pareto search.
- Optional custom lawn, sprinkler-layout, protected-surface, radial-profile, and pressure-performance CSV inputs.
- Provenance metadata, matched comparisons, resolution diagnostics, and baseline-relative guardrails.
- Pointwise catch-can prediction with calibration/holdout separation and an experimental Gaussian-process residual corrector.
- One-command quickstart, local UI, artifact checksums, and regression/CI coverage.

These are software capabilities, not evidence of field accuracy.

## Next stages

1. **Software and numerical verification:** keep geometry, mass-balance, grid sensitivity, output provenance, and configuration contracts under regression tests.
2. **Physical calibration:** replace assumed radial distribution and flow/throw inputs with documented measurements for the actual sprinkler/nozzle and pressure.
3. **Independent validation:** pre-register acceptance thresholds and assess predictions on held-out runs, dates, or sites without tuning against holdout data.
4. **Practical constraints:** represent obstacles, no-spray zones, valve zones, allowed installation corridors, and hydraulic limits only when the required inputs and defensible models exist.
5. **Decision support:** report feasibility, uncertainty, assumptions, and validation status before any installation or savings claims.

## Evidence rule

Never silently convert a missing measurement into a measured value. Label every parameter as measured, manufacturer-published, inferred, assumed, or unavailable. A more sophisticated optimizer cannot compensate for untrustworthy inputs.
