# campOS run artifact integrity

## Generate and verify a synthetic run

Install campOS, run the no-data-required demo, then verify its output files:

```bash
python -m pip install -e .
campos-start --outdir out/campos-quickstart
python scripts/verify_run_artifacts.py \
  --manifest out/campos-quickstart/quickstart_manifest.json
```

The quickstart manifest records the Python version, platform, run mode, limitations, and each generated artifact's byte size and SHA-256 digest. The verifier checks that every listed artifact still exists and matches both recorded values. It exits with status 2 if a file is missing, has changed, or the manifest is malformed.

## What this proves—and what it does not

- A successful check provides evidence that the listed files have not changed since their checksums were recorded.
- It helps detect accidental edits, incomplete transfers, and mismatched output bundles.
- It does not prove that the simulation is physically accurate, that an optimization is globally optimal, or that the output is safe to install.
- The HTML report and manifest are excluded from the manifest's own artifact checksum list to avoid self-referential hashing. Verify the CSV, image, and run metadata files listed in `artifact_checksums`.
- SHA-256 checksums provide integrity checking, not authenticity: a person able to replace both an artifact and its manifest can recompute the digest.

The built-in quickstart remains a synthetic demonstration. Real-site conclusions still require surveyed geometry, measured sprinkler inputs, and independent catch-can holdout observations.
