# campOS Project Charter

## One-sentence definition

campOS is an open, reproducible decision-support prototype for comparing sprinkler-layout options on irregular lawns, with explicit assumptions and a staged path toward measurement-based validation.

## The problem it is meant to investigate

Irregular lawn boundaries make sprinkler layout a trade-off problem. A layout can apply water beyond the lawn while still leaving some interior cells below a model-defined target. Moving heads may improve the search space but can imply retrofit work; keeping heads fixed is a different and often more constrained decision. A single aggregate score can hide these trade-offs.

campOS is intended to help users compare these alternatives under the same documented scenario, inspect the resulting coverage metrics, and understand which conclusions are supported by the model—and which still require measurements.

## The primary question

> Given a specified lawn geometry, sprinkler layout, and documented set of model assumptions, how do candidate layouts compare in modelled outside-lawn application, interior deficit, and distribution uniformity?

This is deliberately narrower than asking how much water a real property will save. That broader question requires a calibrated volume model, measured operating conditions, and appropriate field evidence.

## Intended users and decisions

The prototype is aimed at researchers, students, and landscape or irrigation practitioners exploring layout alternatives. It can support early-stage questions such as:

- Is a fixed-position retrofit worth comparing with a fully movable layout?
- How does the apparent trade-off change when the objective or dry-area constraint changes?
- Are results sensitive to random initialization, grid resolution, or assumed radial distribution?
- Which inputs and measurements are needed before a simulated result can be trusted for a real site?

It is not currently intended to issue construction-ready designs, control irrigation equipment, prescribe irrigation schedules, or certify regulatory or agronomic compliance.

## Product principles

1. **Compare decisions, not just scores.** Show the baseline, candidate layout, assumptions, and multiple relevant metrics.
2. **Keep comparisons fair.** Matched scenarios should share geometry, grid, random seed, radial assumptions, and measurement inputs unless the experiment explicitly studies one of those factors.
3. **Make provenance inspectable.** Preserve configuration, input hashes where available, software environment, and raw machine-readable outputs.
4. **Separate software correctness from model validity.** Passing tests establishes specified code behavior; it does not establish that the physics represents a real sprinkler installation.
5. **Treat measurements as evidence, not decoration.** Record how observations were collected, which data were used for calibration, and which were held out for independent evaluation.
6. **Do not convert proxy metrics into claims they cannot support.** AR improvement is not water savings. A manufacturer performance chart is not a measured radial spray profile. Synthetic sensitivity is not field validation.
7. **Prefer a small number of reproducible case studies over a large number of unsupported features.**

## Current capability boundary

### Available in the prototype

- Synthetic lawn geometries and imported polygon/layout CSV inputs.
- Fixed-position and movable-head optimization modes.
- Legacy AR optimization and Pareto exploration of modelled overspray versus interior deficit.
- Configurable runs, matched scenario comparisons, parameter sensitivity checks, and run metadata.
- Radial-profile preparation, optional pressure-performance tables, shareable HTML/Markdown reports, and descriptive paired-observation error metrics.
- Automated tests for selected numerical, input-validation, and workflow behaviors.

### Important limitations

- Built-in site shapes are synthetic, not surveyed properties.
- A user-supplied input file is not automatically verified or representative.
- The radial distribution can remain an assumed placeholder even when aggregate flow/throw data are supplied.
- Wind, drift, evaporation, pressure losses across a real network, soil response, and other operational effects are not comprehensively represented.
- Grid discretization and stochastic optimization introduce numerical/search limitations.
- Error metrics are meaningful only when measured/predicted pairs and calibration/holdout separation are methodologically sound.
- Water-volume savings, financial savings, and payback are not established by the current model.

## Evidence ladder

Use these levels when describing results. Do not skip a level merely because the codebase or test suite has grown.

1. **Software behavior:** unit tests, regression tests, CLI smoke tests, input validation, and reproducible runs.
2. **Numerical consistency:** dimensional checks, area/flow conservation, grid-resolution studies, and optimizer-seed sensitivity.
3. **Component calibration:** documented manufacturer or laboratory data for the exact relevant nozzle, pressure, flow, throw, and radial distribution, with assumptions stated.
4. **Independent predictive evaluation:** surveyed geometry and operating conditions, observations not used for tuning, predeclared error metrics and acceptance criteria, and repeatable collection procedures.
5. **Decision usefulness:** only after the earlier levels are adequate, evaluate whether results support a real installation choice, water-volume estimate, or economic conclusion.

Current work primarily strengthens levels 1 and 2 and prepares workflows for levels 3 and 4. It must not be described as completed field validation.

## Recommended development sequence

### Phase A — Establish a trustworthy research artifact

- Keep the README centered on the problem, workflow, capabilities, and limitations.
- Publish a small set of synthetic case studies with raw CSVs, run metadata, plots, and reproduction commands.
- Make metric definitions, denominators, baselines, and objective differences easy to find.
- Keep all benchmark comparisons matched and explain when objectives differ.

### Phase B — Strengthen physical consistency

- Add an explicit surveyed protected-surface mask (e.g. sidewalk/road polygons) so the objective can distinguish protected hardscape from other outside-lawn areas; report both total outside-lawn water and protected-surface water separately.
- Validate protected-surface geometry and predictions with catch-can observations before describing results as road/sidewalk-specific.
- Trace pressure-performance input through flow, throw, radial distribution, and applied-depth calculation.
- Make units and conversions explicit at each boundary.
- Test full-circle and sector-flow conservation and verify that pressure interpolation is restricted to measured input ranges.
- Distinguish aggregate sprinkler performance from the spatial radial profile; one does not replace the other.

### Phase C — Validate predictions

- Define a measurement protocol before collecting data.
- Separate calibration observations from independent holdout observations at the collection/design stage.
- Predeclare error metrics and acceptance thresholds before viewing holdout results.
- Report failed as well as successful cases and state the conditions to which conclusions apply.

### Phase D — Consider real-world decision support

Only after measured validation should the project consider credible water-volume estimates, economic analysis, or site-specific recommendations. Any such extension needs documented operating schedules, absolute flow, baseline use, prices, costs, and uncertainty—not an AR percentage conversion.

## Definition of done for a meaningful change

A change should normally include:

- a clear user or research question it answers;
- explicit inputs, units, assumptions, and expected behavior;
- a regression test or a reproducible experiment;
- machine-readable outputs where appropriate;
- documentation of what the result does and does not demonstrate;
- no stronger validity claim than the evidence supports.

## Recommended public description

> campOS is an open research prototype for exploring sprinkler-layout decisions on irregular lawns. It compares fixed and movable layouts, exposes trade-offs between modelled overspray and interior coverage deficit, and produces reproducible reports with input provenance. Its current cases are synthetic and its physics is only partially calibrated; the project focuses on transparent comparison and a path to independent validation rather than claiming guaranteed water savings or installation-ready designs.
