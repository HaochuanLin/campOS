# Legacy Objective Audit

## Scope

This note records an implementation audit of the current single-objective optimizer. It is a code review of the model as implemented, not evidence of real-world sprinkler performance. No optimization behavior is changed by this document.

## Findings confirmed in source

### 1. The movable and fixed modes optimize the legacy AR score

`optimize()` in `src/campos/campos_sim.py` accepts a candidate when it improves the value returned by `score()` (or through simulated-annealing acceptance). The score is:

```text
J = AR + 5 * max(0, dry_fraction - dry_fraction_limit)
AR = W_total_grid / (number_of_lawn_cells * mean_depth_of_driest_quarter)
```

The dry-area fraction is computed relative to the current layout's own mean lawn depth. This is a scale-free diagnostic; it is not a constraint on absolute application depth.

### 2. Overspray is reported, but is not an independent single-objective target

`score()` returns overspray share, CU, and dry-area fraction as metrics, but the optimizer compares only the returned score. There is no separate overspray penalty or hard overspray limit in this objective. Since total water outside the lawn contributes to `W_total_grid`, overspray is not completely invisible to AR, but the optimizer can still accept a trade-off in which AR improves while overspray increases.

This explains the sensitivity-run pattern without implying that the optimizer is malfunctioning: the legacy objective is not designed to minimize overspray independently.

### 3. The AR improvement column is not water savings

The code computes `1 - AR_optimized / AR_baseline`. AR is dimensionless, so this is a change in the legacy metric, not a ratio of measured or calibrated water volumes. The implementation correctly leaves annual water savings, annual cost savings, and payback unestimated.

### 4. A multi-objective mode already exists

The Pareto modes search two different quantities:

- `f1`: water outside the lawn divided by baseline total modelled water.
- `f2`: average relative shortfall below a target depth derived from the baseline mean lawn depth.

Candidate points are archived only when the dry-area constraint is satisfied. CU is reported and used for selecting a displayed trade-off, but is not one of the two Pareto objectives. The front is approximate because of archive tolerance, finite search iterations, and thinning before output.

### 5. The baseline and model inputs remain synthetic or provisional

The built-in lawns are synthetic. The default radial field is a uniform-depth null model; the slope family is an illustrative sensitivity assumption unless replaced by a measured radial profile. The manufacturer-chart benchmark checks aggregate flow/spacing consistency, but does not validate the local radial spray pattern or a real property layout.

## Decision from Step 1

Do not replace the entire optimizer or rename AR improvement as water savings. The first change should make objective intent explicit and measurable:

1. Preserve the legacy mode as a reproducible comparison baseline.
2. Evaluate the existing Pareto mode against fixed, shared test cases and report its trade-offs.
3. Define acceptance criteria for overspray, dry area, CU, and sprinkler count before choosing a default objective.
4. Add regression tests for the chosen criteria before changing the default search behavior.

The next step should be an evidence-led objective redesign, not a claim that the current AR optimizer is universally better or worse. Any final objective weights or hard limits are product/design choices that should be justified by a stated use case and then tested for sensitivity.

## Regression guards added after the audit

The test suite now guards two important semantics of the existing Pareto workflow:

- The overspray objective f1 is calculated from water outside the lawn polygon divided by the baseline total modelled water.
- A displayed trade-off must not increase overspray relative to the baseline and must keep CU within the configured absolute loss budget relative to baseline CU. If no Pareto point satisfies both conditions, the tool reports no selected trade-off rather than silently accepting more overspray.

These tests protect the meaning of the existing metrics and selection policy; they do not demonstrate that a particular layout is physically accurate or that a real site will save water. The optimizer remains a synthetic research prototype until its assumptions are calibrated and its predictions are assessed against independent field observations.


## Baseline-aware Pareto selection

A roadside-strip benchmark exposed a policy failure in the earlier selector: it measured CU loss from the most uniform point on the searched front, not from the installed baseline, and could select a solution with much more overspray than baseline. The selector now applies two explicit guardrails to displayed recommendations:

1. CU must be at least baseline CU minus the configured absolute CU-loss budget.
2. The modelled overspray ratio must not exceed baseline overspray plus the explicit `max_overspray_increase` tolerance (default zero; configured as a fraction of baseline total modelled water).
3. Mean interior deficit must be no worse than baseline.

If the approximate Pareto front contains no candidate satisfying all three, no candidate is labelled as selected. The matched benchmark script accepts `--max-overspray-increase` and records it in its summary and run metadata so any allowed regression is explicit and reproducible. This does not mean the baseline meets the dry-area constraint; it means the current search did not find a solution satisfying all reported constraints. The roadside-strip synthetic run is a useful regression case because its baseline overspray is low but its dry-zone fraction violates the Pareto feasibility threshold.
