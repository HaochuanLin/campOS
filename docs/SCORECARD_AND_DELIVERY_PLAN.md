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
**Size:** one objective path and its tests; no new AI features.
Acceptance:
- [ ] Trace the exact formula and units for outside-lawn application, interior deficit, and uniformity.
- [ ] Verify road/sidewalk geometry actually affects the relevant supported mode.
- [ ] Add at least one synthetic counterexample where reducing overspray must not silently permit unacceptable interior deficit.
- [ ] Document the formula, normalization, constraints, and test result.

### Stage G — Numerical sensitivity check
**Size:** one small deterministic test set.
Acceptance:
- [ ] Compare at least two grid resolutions on a fixed synthetic geometry.
- [ ] Check area/depth/mass-balance invariants where the implementation supports them.
- [ ] Report which metrics change with resolution and set a justified warning/limit.
- [ ] Do not claim physical accuracy from numerical convergence alone.

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
