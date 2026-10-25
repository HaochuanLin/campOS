# campOS scorecard and one-conversation delivery plan

Live application: https://campos-optimizer.streamlit.app/  
Repository: https://github.com/HaochuanLin/campOS

## Why tasks are intentionally small

Each delivery stage is one independently verifiable outcome, sized for one focused work session. A stage is not complete because code was written: its acceptance checks must pass or its unresolved blocker must be explicitly recorded with evidence. Do not silently roll an unfinished stage into the next one.

## Current scorecard (2026-10-25)

Scores are engineering assessments of the evidence currently available, not measured product performance. They should be revised when new test or field evidence appears.

| Dimension | Current | Near-term target | Reason |
|---|---:|---:|---|
| Product direction and scope | 7.0/10 | 8.0/10 | The core problem and limits are now explicit; first-use guidance can still be simpler. |
| UI and first-run experience | 6.0/10 | 7.5/10 | The hosted landing page renders in a user-provided screenshot; contrast changes have not yet been visually re-verified after deployment. |
| Software tests and regression safety | 7.0/10 | 8.0/10 | CI covers the Python suite, AppTest flows, CLI entry points, and artifact integrity; the latest main-branch result must be checked per change. |
| Deployment and hosted reliability | 4.5/10 | 7.0/10 | A screenshot proves the page rendered for one browser session, while the hosted monitor observed redirects to authentication paths. The discrepancy remains unresolved. |
| Optimization objective and numerical validity | 5.5/10 | 7.5/10 | Multiple modes and trade-off metrics exist, but the objective semantics and edge cases need a focused code-and-test audit. |
| Physical-model validity | 3.5/10 | 6.0/10 | Inputs and model assumptions are documented, but measured sprinkler calibration and independent holdout evidence are not established here. |
| AI value and generalization | 2.5/10 | 5.0/10 | An experimental residual-correction workflow exists; no evidence yet establishes generalization to new sites. |
| Real-world evidence for less overspray / water use | 1.0/10 | 4.0/10 | No real-site measurement evidence has been provided, so no real-world reduction claim is established. |

**Overall engineering maturity: 5.0/10 (provisional).** This is a weighted judgement, not an average of all rows: software/product readiness is materially ahead of scientific validation. The previous rough estimate of 5.8/10 was too generous if interpreted as end-to-end readiness, because it underweighted hosted-access uncertainty and the absence of field evidence.

## Delivery stages

Complete these in order unless new evidence changes the priority. Every stage below is intentionally narrow.

### Stage A — Scorecard and bounded task plan
**Status: COMPLETE in this commit.**

Acceptance:
- [x] Record a dimension-based score and explain the evidence/unknowns.
- [x] Separate software maturity from physical and field validity.
- [x] Define small, independently testable stages.
- [x] State that incomplete stages cannot be called complete.

### Stage B — Verify the sidebar contrast fix
**Status: COMPLETE on 2026-10-25, verified against main CSS commit `589217105e4435b2fb2726fca4864e7cf76be3b3`.**

**Evidence:** [Hosted Playwright contrast run #21](https://github.com/HaochuanLin/campOS/actions/runs/40168541400) passed against the deployed app (HTTP 200), captured a screenshot, and measured computed styles after the final multi-select CSS adjustment:
- Number input text: **14.15:1**.
- Optimization-mode select text: **14.97:1**.
- Number-input stepper: **11.47:1**.
- Multi-select clear icon against the selected chip: **4.53:1**.
- Multi-select clear/dropdown icons against the light control surface: **14.97:1**.
- The screenshot confirms the sidebar labels and control contents are visually readable; automated report returned `failures: []`.
- [Python test matrix (3.10, 3.11, 3.12)](https://github.com/HaochuanLin/campOS/actions/runs/40168541387), [UI smoke test](https://github.com/HaochuanLin/campOS/actions/runs/40168541399), and [artifact integrity](https://github.com/HaochuanLin/campOS/actions/runs/40168541397) passed for the same CSS commit.
- Regression coverage was expanded in [the sidebar CSS contract test](https://github.com/HaochuanLin/campOS/blob/main/tests/test_ui_css_contract.py) and the [hosted visual workflow](https://github.com/HaochuanLin/campOS/blob/main/.github/workflows/hosted-sidebar-visual.yml) now checks the multi-select icons as well as the number input and ordinary select.

Acceptance:
- [x] Check main-branch CI after the CSS changes.
- [x] Inspect the deployed page after redeployment with Playwright and save a screenshot artifact.
- [x] Confirm number inputs, ordinary select controls, multi-select icons, and stepper buttons meet their automated contrast thresholds.
- [x] Visually inspect sidebar labels and control readability; fix the low-contrast multi-select icons and re-check the deployed screenshot.
- [x] Add regression checks so the multi-select icon contrast issue is caught in future changes.

### Stage C — Prove one synthetic run end to end
**Status: COMPLETE on 2026-10-25, verified by UI smoke run [#248](https://github.com/HaochuanLin/campOS/actions/runs/40168754046), commit `52cd5915470c307cf771c94dc7665942b431bb76`.**

**Evidence:** The hosted GitHub Actions job passed dependency checks, CLI entry-point checks, the regression suite, Python compilation, a packaged synthetic quickstart with artifact checksum verification, Streamlit AppTest, and the HTTP health endpoint. AppTest confirms the default synthetic run exposes the complete-run ZIP download; a mocked non-zero subprocess exit shows a visible error and does not leave a stale successful ZIP visible. The surveyed-site flow exposes the starter-template ZIP and checks all six source CSV files exist.

Acceptance:
- [x] Run the default synthetic scenario in AppTest.
- [x] Assert the run completes and the expected output control exists.
- [x] Assert a user-visible failure message appears for a simulated invalid process result and no stale success download remains.
- [x] Record the actual passing CI run and commit.

### Stage D — Verify ZIP contents, not just buttons
**Status: COMPLETE on 2026-10-25.** Verified by [Python matrix](https://github.com/HaochuanLin/campOS/actions/runs/40174064556), [UI smoke / AppTest](https://github.com/HaochuanLin/campOS/actions/runs/40174064581), and [artifact integrity](https://github.com/HaochuanLin/campOS/actions/runs/40174064618), all passing for commit `f493020f82345dc7a250920c35407edf717d7f5c`.

Evidence:
- [x] Open the generated result ZIP in tests; assert expected filenames, non-empty payloads, and ZIP CRC integrity.
- [x] Open the starter-template ZIP in tests and assert all six CSV templates are present and non-empty.
- [x] Reject unsafe archive paths.
- [x] Simulate a missing template and assert a clear UI warning; no missing file is silently invented.

### Stage E — Resolve hosted monitor versus browser discrepancy
**Status: BLOCKED by deployment configuration, diagnosed on 2026-10-25.** [Hosted monitor run](https://github.com/HaochuanLin/campOS/actions/runs/40170233526) captured repeated HTTP 303 redirects: `share.streamlit.io/-/auth/app` → app `/-/login` → app root, for both the root page and `/_stcore/health`. This is an authentication/access-visibility redirect cycle, not evidence of a Python simulation failure. A logged-in browser session may still render the page, so the earlier screenshot does not disprove the unauthenticated monitor result. The repository cannot change the app's Community Cloud visibility setting; an owner must verify the app is set to public in Streamlit Community Cloud. The hosted monitor now emits a targeted diagnostic when this redirect signature occurs, while correctly failing the reachability check rather than falsely passing it.

Acceptance:
- [x] Capture a hosted-smoke run and inspect sanitized response headers/statuses.
- [x] Compare the unauthenticated HTTP probe with the previously observed logged-in browser rendering, without exposing authentication tokens.
- [x] Identify the observed authentication redirect cycle.
- [x] Add explicit diagnosis to the monitor workflow.
- [ ] Confirm public-access setting in Streamlit Community Cloud and rerun the monitor; this requires deployment-owner access.

### Stage F — Audit the overspray/coverage objective
**Status: COMPLETE (2026-10-25).** Objective contract tests and all CI workflows passed on commit `3470c4bb5578cbccc12cef4235ddc9c98ee2a1c0`.

**Formula and units audit (implementation semantics, not validated field physics):**
- The Pareto reference is computed once from the baseline layout: (W_0=\sum_{\text{all grid cells}} D_0\), and (T=\text{target_factor}\times\operatorname{mean}(D_0\text{ on lawn})\). The simulator's default field is relative application intensity; with per-head flow/profile inputs it may represent estimated precipitation. It must not be interpreted as litres or water savings without calibrated flow and run-time assumptions.
- Pareto objective (f_1=W_{\text{selected outside}}/W_0\). If a surveyed protected-surface polygon is supplied, selected outside water is the sum of grid-cell field values in that polygon; otherwise it is all modelled water outside the lawn. Thus the polygon affects the Pareto objective only in the custom-geometry workflow where it is accepted. Grid cells are centre-classified; (W_0) is a baseline normalizer, not candidate total water.
- Pareto deficit (f_2=\operatorname{mean}_{i\in\text{lawn}}\max(0,1-D_i/T)\), dimensionless. The dry share is the fraction of lawn cells with (D_i<\text{dry\_thresh\_frac}\times T\). These are separate quantities: lower (f_1) does not cancel a higher (f_2); the selection policy applies its own explicit constraints.
- Legacy metrics are different: (AR=\sum D/(n\times\text{mean of driest 25% lawn cells})\), overspray (=1-\sum D_{\text{lawn}}/\sum D_{\text{all}}\), and CU (=1-\operatorname{mean}(|D_i-\bar D|)/\bar D\). AR and CU are dimensionless for the default relative field; the reported outside share is relative to the candidate's own total, unlike Pareto (f_1)'s fixed baseline denominator. If the driest-quartile mean is near zero, the implementation returns a high penalty and infinite AR.
- The road/sidewalk polygon is a *protected surface* proxy, not semantic road detection. The code rejects it when combined with built-in sites and requires a custom lawn polygon; overlap/touching is rejected. A protected polygon with no grid-cell centres at the selected resolution is rejected rather than silently scored as zero.

Acceptance:
- [x] Trace the formulas and distinguish fixed-baseline versus candidate-total normalization.
- [x] Verify that surveyed protected-surface geometry affects the supported custom-site Pareto mode, while built-in synthetic sites reject that input.
- [x] Add/run synthetic counterexamples where lower protected-surface water accompanies unacceptable lawn deficit; tests verify the lower protected-water objective can coexist with worse lawn deficit and must be treated as a trade-off.
- [x] CI passed: [Python matrix](https://github.com/HaochuanLin/campOS/actions/runs/40187230762), [UI smoke](https://github.com/HaochuanLin/campOS/actions/runs/40187230778), [artifact integrity](https://github.com/HaochuanLin/campOS/actions/runs/40187230741), [hosted sidebar visual](https://github.com/HaochuanLin/campOS/actions/runs/40187230717).

**Known limitation:** these are synthetic contract tests of mathematical semantics. They do not establish that the model's spray field is physically calibrated or that real water consumption falls.

### Stage G — Numerical sensitivity check
**Status: COMPLETE on 2026-10-25.** Verified on commit `1687d1d99bff391821f47000ab032302ea37fc30` by the [Python 3.10/3.11/3.12 matrix](https://github.com/HaochuanLin/campOS/actions/runs/40200987251), [UI smoke](https://github.com/HaochuanLin/campOS/actions/runs/40200987071), [artifact integrity](https://github.com/HaochuanLin/campOS/actions/runs/40200987023), and [hosted sidebar visual check](https://github.com/HaochuanLin/campOS/actions/runs/40200987003); all passed.

Evidence and interpretation:
- An axis-aligned 4 m × 3 m rectangle preserves its exact 12 m² raster area at cell sizes 1.0, 0.5, and 0.25 m.
- A fixed, non-grid-aligned lawn polygon is compared with its shoelace area across 1.0, 0.5, 0.25, and 0.125 m grids. In this fixture the 0.125 m grid is within 0.2% of the exact area.
- A uniform circular sprinkler field with an offset centre and 2.07 m radius is integrated against the analytic value `pi*r^2`. In this fixture the 0.125 m grid's integral error is below 0.1%, and the measured integral changes with resolution.
- **Resolution limit:** grid-cell-centre classification can alias boundaries, so errors need not decrease monotonically at every refinement step. The fine-grid result is evidence for these fixtures only, not a universal accuracy guarantee. For a new surveyed site, compare at least two resolutions and inspect the change in lawn area and objective values before relying on the optimization.

Acceptance:
- [x] Compare at least two grid resolutions on fixed synthetic geometries, including a non-aligned polygon and sprinkler field.
- [x] Check exact aligned-polygon area and compare non-aligned lawn area and sprinkler integral against analytic references.
- [x] Record the resolution sensitivity and its limit: centre-sampled raster errors can plateau or worsen at intermediate resolutions; no universal cell-size threshold is claimed.
- [x] Keep numerical consistency separate from physical calibration and field validation.

### Stage H — Physical-model input provenance
**Size:** one data contract and its validation tests.
Acceptance:
- [ ] Mark each required parameter as measured, manufacturer-published, derived, assumed, or unavailable.
- [ ] Reject or warn on missing critical units and non-finite values.
- [ ] Ensure illustrative defaults cannot be mistaken for measured data.
- [ ] Keep model calibration separate from holdout evaluation.

### Stage I — Field-evaluation readiness (not field validation)
**Size:** one checklist/template review.
Acceptance:
- [ ] Specify site boundary, head/nozzle, pressure, flow, weather/context, and catch-can fields.
- [ ] Define a split that preserves independent holdout observations.
- [ ] Specify error metrics and pre-registered acceptance thresholds before examining holdout results.
- [ ] State clearly that this stage prepares evaluation; it does not prove savings.

## Rules for reporting progress

1. Report the exact stage and its acceptance checklist.
2. Cite actual commit IDs and workflow runs when available.
3. Separate **implemented**, **automatically tested**, **visually checked**, and **field validated**.
4. If a check fails, the stage remains open until fixed or a concrete external blocker is documented.
5. Never mark a stage complete just to end a conversation.
6. Do not claim reduced road wetting or water savings without real measurements supporting that claim.
