# JSON configuration and matched scenario comparisons

## One reproducible run

The simulator accepts a JSON object via `--config`. The example `configs/run.example.json` lists supported settings:

- `mode`, `sites`, `polygon_csv`, `heads_csv`, `outdir`, `quick`
- `seed`, `cell_size`, `profile_csv`, `radial_slope`
- `performance_csv`, `pressure_kpa`
- `dry_fraction_limit`, `target_factor`, `cu_drop_budget`, `pareto_weights`

The configuration file uses the simulator's existing argument names (for example, `cell_size`, not `cell-size`). CSV paths are resolved from the current working directory, not automatically relative to the JSON file. A list is accepted for `mode`, `sites`, and `pareto_weights`.

```bash
python campos_sim.py --config configs/run.example.json
```

Explicit command-line flags override values from the JSON file. If a setting is not present in either place, the existing built-in default remains in effect. The simulator records the config file hash and a per-parameter source map (`command_line`, `config_file`, or `built_in_default`) in `run_metadata.json`. Measured radial-profile and hydraulic-performance inputs are separately identified and hashed; absent measurements are not inferred.

## Compare multiple designs fairly

Use a comparison specification with shared inputs and at least two named scenarios. See `configs/design_comparison.example.json`.

```bash
python scripts/compare_design_configs.py \
  --spec configs/design_comparison.example.json \
  --outdir out/design-comparison
```

All scenarios inherit the same `shared` settings. Scenario-specific overrides are restricted to the selected mode and optimization policy (`dry_fraction_limit`, `target_factor`, `cu_drop_budget`, `pareto_weights`). Geometry, starting sprinkler layout, seed, grid cell size, radial model/profile, hydraulic-performance curve, operating pressure, and quick/full setting cannot be changed inside an individual scenario. Each scenario gets its own output directory and exact effective configuration; combined rows are written to `design_comparison.csv`, with a manifest and Markdown summary alongside them.

The comparison script checks recorded shared settings when they are explicitly declared in `shared`. To make a comparison interpretable, declare all scientifically relevant shared inputs rather than relying on defaults. For the strongest reproducibility, set a seed, grid size, radial profile/slope, site inputs, and any available measured performance files explicitly. This is a matched model comparison, not proof that a scenario is better in the field.

## Provenance vocabulary

- **User supplied:** polygon/layout CSVs and measurement CSVs provided for the run; hashes are recorded.
- **Measured profile / measured performance:** a measurement file was supplied and loaded. This describes file provenance, not independent verification of measurement quality.
- **Illustrative assumption:** built-in synthetic geometry, default uniform radial null model, or a user-selected radial-slope sensitivity scenario without a measured profile.
- **Not configured / placeholder:** hydraulic or economic quantities that have not been supplied or calibrated.

A measured input does not validate the full model. Reports should not claim field validation, actual water savings, or economic payback without independent evidence.
