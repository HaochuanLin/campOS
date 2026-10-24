# Importing a custom site and existing sprinkler layout

campOS can accept a site polygon and an optional initial sprinkler layout as CSV inputs. This makes coordinates reproducible and avoids relying on the built-in synthetic site shapes. It does **not** make the model field-validated.

## Polygon CSV

Required header: `x_m,y_m`. Each row is a polygon vertex in metres, in boundary order (clockwise or counter-clockwise). Do not include self-intersecting boundaries. A repeated final copy of the first vertex is accepted and removed. At least three distinct vertices and nonzero polygon area are required.

Template: `data/templates/site_polygon_template.csv`.

## Sprinkler-layout CSV

Required header: `x_m,y_m,radius_m,start_angle_deg,arc_width_deg`. An optional `flow_lpm` column can store measured flow per head for the field-evaluation workflow; the optimizer ignores this extra column. If the value is blank, `campos-field-evaluate` requires a `--flow-lpm` fallback.

- `x_m,y_m`: initial sprinkler centre in the same metre-based coordinate system as the polygon.
- `radius_m`: initial throw radius; it must be within the optimizer's configured radius range.
- `start_angle_deg`: sector start angle in degrees counter-clockwise from +x, normalized modulo 360.
- `arc_width_deg`: sector width in (0, 360].

All initial sprinkler centres must be inside the supplied polygon. Boundary-mounted heads are currently rejected; represent actual head positions consistently and inspect the site coordinate system before optimizing. The file provides the initial/baseline layout: `fixed` and `pareto-fixed` keep its x/y coordinates, while movable modes may move heads.

Template/example: `data/templates/sprinkler_layout_template.csv`. The example coordinates and radii are illustrative only and are not an installation recommendation.

## Run

```bash
python campos_sim.py --mode fixed --quick \
  --polygon-csv data/templates/site_polygon_template.csv \
  --heads-csv data/templates/sprinkler_layout_template.csv \
  --outdir out/custom-site

python scripts/build_design_report.py --input-dir out/custom-site
```

Omit `--heads-csv` if you want campOS to generate a baseline layout for the custom polygon. `--heads-csv` requires `--polygon-csv`. Custom geometry is a single-site run and cannot be combined with `--sites`; use `--sites` for built-in synthetic sites.

The run metadata records the input paths, SHA-256 hashes, coordinate units, polygon vertex count, initial head count, and whether geometry/layout were user supplied. Keep the original CSVs with the report: hashes establish which bytes were used, but the report does not copy or reconstruct the source files.

## Validation limits

Input validation checks columns, numeric finite values, duplicate consecutive vertices, nonzero polygon area, and initial head positions/ranges. It is not a complete GIS topology validator; inspect the polygon for self-intersections, holes, obstacles, slope, and coordinate reference issues before using it. The current geometry model supports one simple polygon only: no holes, islands, terrain, or obstacles. Wind, pressure loss, evaporation, drift, and network hydraulics remain outside the model. A successful run is not an engineering approval or evidence of water savings.


## Optional protected-surface polygon (road/sidewalk objective)

For a surveyed custom site, an additional CSV can describe a road, sidewalk, or other surface whose received water should be minimized. It uses the same metre-based vertex format as the lawn polygon:

    x_m,y_m
    40,0
    40,25
    43,25
    43,0

Example invocation (replace paths with surveyed inputs):

    python campos_sim.py --mode pareto-fixed --quick \
      --polygon-csv data/site_polygon.csv \
      --heads-csv data/sprinkler_layout.csv \
      --protected-surface-csv data/sidewalk_polygon.csv \
      --outdir out/protected-surface

When supplied, Pareto f1 becomes modelled water on the protected polygon divided by baseline total modelled water. CSV output also reports outside-lawn water separately. The polygon must be valid and must not overlap the lawn interior; a shared boundary is allowed. Identical polygons and polygons with coincident edges whose interiors overlap are rejected. The grid uses cell-centre inclusion, so results depend on grid resolution; if no grid-cell centre falls inside the protected polygon, the run now fails fast instead of reporting a misleading zero-water objective. Reduce `--cell-size` or correct the surveyed polygon. This is not a runoff or drift model and is not field validation; compare resolutions and validate with catch-can observations.


### Check protected-surface grid resolution before interpreting results

Run the area diagnostic before optimization to quantify how cell-centre rasterization approximates the surveyed road/sidewalk polygon's area:

```bash
python scripts/check_protected_surface_resolution.py \
  --polygon-csv data/site_polygon.csv \
  --protected-surface-csv data/sidewalk_polygon.csv \
  --heads-csv data/sprinkler_layout.csv \
  --cell-sizes 2,1,0.5,0.25 \
  --max-relative-error 0.05 \
  --out out/protected-surface-resolution.csv
```

The optional `--max-relative-error` limit applies to the finest requested grid; the command exits non-zero if its rasterized protected area exceeds that relative error. If `--heads-csv` is supplied, the script also applies the **same fixed sprinkler layout** at every grid size and reports integrated modelled water on the protected surface as a share of total modelled water. This isolates grid effects from optimizer/layout changes. You can optionally set `--max-water-share-spread 1.0` to require the max-minus-min share across all tested grids to stay within 1 percentage point; this option requires `--heads-csv` and the tolerance must be chosen for the decision context. Neither threshold simulates drift or proves real road wetting; compare resolutions and validate with field measurements.
