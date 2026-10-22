# Importing a custom site and existing sprinkler layout

campOS can accept a site polygon and an optional initial sprinkler layout as CSV inputs. This makes coordinates reproducible and avoids relying on the built-in synthetic site shapes. It does **not** make the model field-validated.

## Polygon CSV

Required header: `x_m,y_m`. Each row is a polygon vertex in metres, in boundary order (clockwise or counter-clockwise). Do not include self-intersecting boundaries. A repeated final copy of the first vertex is accepted and removed. At least three distinct vertices and nonzero polygon area are required.

Template: `data/templates/site_polygon_template.csv`.

## Sprinkler-layout CSV

Required header: `x_m,y_m,radius_m,start_angle_deg,arc_width_deg`.

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
