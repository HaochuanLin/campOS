# Phase 1 acceptance checklist

This checklist separates repository-level automation from checks that require the deployed Streamlit app.

## Automated checks

Open [UI smoke workflow runs](https://github.com/HaochuanLin/campOS/actions/workflows/ui-smoke.yml) and verify the latest run for the current `main` commit is green. The workflow is expected to check:

- dependency installation, `pip check`, and all six installed CLI entry points;
- the Python regression suite, including catch-can observation QC and artifact-manifest integrity tests;
- a packaged synthetic Quickstart run that generates an HTML page and manifest, then verifies recorded file sizes and SHA-256 digests;
- Python compilation of the Streamlit entry points;
- rendering of the app with Streamlit AppTest;
- a synthetic simulation and presence of the complete-run ZIP download control;
- surveyed-site mode and presence of the starter-template ZIP download control;
- presence of all six CSV templates in `data/templates/`;
- a successful local HTTP response from Streamlit's health endpoint.

A green workflow proves only that these automated code paths passed in the CI environment. It does not prove the hosted app is reachable, that browser downloads work on every device, or that model outputs match a real site.

## Hosted-app checks

Open the [hosted Streamlit demo](https://campos-optimizer.streamlit.app/) in a fresh browser session.

- [ ] The page renders fully; no blank screen or uncaught startup error.
- [ ] Sidebar and main-page controls respond to interaction.
- [ ] The default synthetic scenario runs and produces result metrics and plots.
- [ ] The complete-run ZIP downloads and can be opened as a ZIP archive.
- [ ] Enabling **Use surveyed site CSVs** shows the input guidance and template downloads.
- [ ] The starter-template ZIP downloads and contains the six expected CSV templates.
- [ ] An invalid or incomplete custom input produces an actionable message instead of a blank page.
- [ ] Refreshing the page does not leave the app stuck in a non-interactive state.

Record the date, browser, deployed commit/version if visible, and any error text. If a check fails, retain the Streamlit Community Cloud logs and a screenshot of the visible error.

## Release gate

Phase 1 is not complete until the latest CI run is green and the hosted-app checks above have been observed. Do not mark it complete based on code commits alone. Keep synthetic-demo results separate from field-validation evidence; this checklist is not evidence of water savings or field accuracy.
