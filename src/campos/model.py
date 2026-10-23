"""Synthetic lawn geometry, sprinkler field, and base metric functions.

These functions define the current simplified research model; they are not a
calibrated representation of real-world irrigation hydraulics.
"""
import csv
import numpy as np
from matplotlib.path import Path

# ----------------------------------------------------------- synthetic sites
def site_rect():
    return np.array([[0, 0], [40, 0], [40, 25], [0, 25]], float)

def site_lshape():
    return np.array([[0, 0], [40, 0], [40, 14], [18, 14], [18, 32], [0, 32]], float)

def site_kidney():
    t = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    x = 24 * np.cos(t)
    y = 12 * np.sin(t) - 7 * np.exp(-((t - np.pi / 2) ** 2) / 0.25)
    p = np.c_[x, y]
    return p - p.min(axis=0)

def site_wedge():
    return np.array([[0, 0], [50, 0], [12, 30]], float)

def site_strip():
    return np.array([[0, 0], [60, 0], [60, 7], [35, 9.5], [0, 6]], float)

SITES = {
    "A Rectangle": site_rect,
    "B L-shape": site_lshape,
    "C Kidney": site_kidney,
    "D Wedge": site_wedge,
    "E Roadside strip": site_strip,
}

# ------------------------------------------------------------- water model
def load_radial_profile_csv(path):
    """Load and area-normalize a measured radial catch-can profile CSV.

    Required columns: radius_fraction, relative_rate. The first radius must be
    0, the last 1, and radii must increase strictly. Rates are relative values;
    normalization makes the area-weighted mean over the swept disk equal 1.
    This does not establish absolute flow or precipitation in mm/h.
    """
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"radius_fraction", "relative_rate"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("profile CSV must contain radius_fraction,relative_rate columns")
        rows = list(reader)
    if len(rows) < 3:
        raise ValueError("profile CSV must contain at least three data rows")
    try:
        profile = np.array([[float(row["radius_fraction"]), float(row["relative_rate"])] for row in rows])
    except (TypeError, ValueError) as exc:
        raise ValueError("profile CSV values must be numeric") from exc
    radius, rate = profile.T
    if not np.all(np.isfinite(profile)):
        raise ValueError("profile CSV values must be finite")
    if not np.isclose(radius[0], 0.0) or not np.isclose(radius[-1], 1.0):
        raise ValueError("radius_fraction must start at 0 and end at 1")
    if np.any(np.diff(radius) <= 0) or np.any(rate <= 0):
        raise ValueError("radii must increase strictly and relative rates must be positive")
    # Axisymmetric area-weighted mean: integral(q*r dr) / integral(r dr).
    mean_rate = 2.0 * np.sum(0.5 * (rate[1:] * radius[1:] + rate[:-1] * radius[:-1]) * np.diff(radius))
    if not np.isfinite(mean_rate) or mean_rate <= 0:
        raise ValueError("profile has an invalid area-weighted mean")
    profile[:, 1] /= mean_rate
    return profile


def load_performance_curve_csv(path, pressure_kpa):
    """Interpolate flow and throw from a measured pressure-performance CSV."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"pressure_kpa", "flow_lpm", "throw_m"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("performance CSV must contain pressure_kpa,flow_lpm,throw_m columns")
        rows = list(reader)
    if len(rows) < 2:
        raise ValueError("performance CSV must contain at least two data rows")
    try:
        data = np.array([[float(row["pressure_kpa"]), float(row["flow_lpm"]), float(row["throw_m"])] for row in rows])
    except (TypeError, ValueError) as exc:
        raise ValueError("performance CSV values must be numeric") from exc
    pressure, flow, throw = data.T
    if not np.all(np.isfinite(data)):
        raise ValueError("performance CSV values must be finite")
    if np.any(np.diff(pressure) <= 0):
        raise ValueError("performance pressure_kpa values must increase strictly")
    if np.any(flow <= 0) or np.any(throw <= 0):
        raise ValueError("flow_lpm and throw_m must be positive")
    p = float(pressure_kpa)
    if not np.isfinite(p) or p < pressure[0] or p > pressure[-1]:
        raise ValueError(f"pressure {p:g} kPa is outside measured range {pressure[0]:g}..{pressure[-1]:g} kPa")
    return {"pressure_kpa": p, "flow_lpm": float(np.interp(p, pressure, flow)), "throw_m": float(np.interp(p, pressure, throw))}


def orifice_flow_lpm(pressure_kpa, diameter_mm, discharge_coefficient=0.62, water_density_kg_m3=998.0):
    """Estimate idealized nozzle flow from Bernoulli/orifice theory.

    Q = Cd * A * sqrt(2 * delta_p / rho). This is a theoretical estimate for
    a simple orifice, not a substitute for a rotor's measured flow curve;
    use the manufacturer's coefficient/geometry only when known.
    """
    pressure = float(pressure_kpa)
    diameter = float(diameter_mm)
    cd = float(discharge_coefficient)
    density = float(water_density_kg_m3)
    values = np.array([pressure, diameter, cd, density], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("orifice inputs must be finite")
    if pressure <= 0 or diameter <= 0 or density <= 0 or not (0 < cd <= 1):
        raise ValueError("pressure, diameter, density must be positive and discharge_coefficient in (0, 1]")
    area_m2 = np.pi * (diameter / 1000.0) ** 2 / 4.0
    velocity_m_s = np.sqrt(2.0 * pressure * 1000.0 / density)
    return float(cd * area_m2 * velocity_m_s * 60000.0)


def spacing_precipitation_mm_h(flow_lpm, spacing_m, arrangement="square", arc_fraction=0.5):
    """Estimate application rate from flow and sprinkler-grid cell area.

    Flow is L/min, spacing is m, and arc_fraction is the fraction of a full
    circle operated. This is a layout-level mass-balance estimate, not the
    local radial distribution from a single sprinkler. For triangular spacing,
    the idealized cell area is sqrt(3)/2 * spacing**2.
    """
    q = float(flow_lpm)
    spacing = float(spacing_m)
    fraction = float(arc_fraction)
    if not np.isfinite(q) or q <= 0:
        raise ValueError("flow_lpm must be finite and positive")
    if not np.isfinite(spacing) or spacing <= 0:
        raise ValueError("spacing_m must be finite and positive")
    if not np.isfinite(fraction) or fraction <= 0 or fraction > 1:
        raise ValueError("arc_fraction must be in (0, 1]")
    if arrangement == "square":
        cell_area = spacing * spacing
    elif arrangement == "triangular":
        cell_area = (np.sqrt(3.0) / 2.0) * spacing * spacing
    else:
        raise ValueError("arrangement must be 'square' or 'triangular'")
    return 60.0 * q / (cell_area * fraction)


def head_field(X, Y, h, radial_profile=None, flow_lpm=None, radial_slope=0.0):
    """Return a relative field, or estimated precipitation in mm/h if flow is set.

    Head tuple h = (x, y, r, a0, w): position [m], throw radius [m], sector
    start angle [degrees CCW from +x], and sector width [degrees].
    Without a measured profile, radial_slope defines a sensitivity family
    q(s) = (1 + radial_slope*s) / (1 + 2*radial_slope/3), where s is radius
    divided by throw radius and radial_slope > -1. This has unit area-weighted
    mean over a disk. The default slope 0 is uniform; nonzero values are
    scenarios, not inferred nozzle physics. A supplied measured profile takes
    precedence. If flow_lpm is provided, the shape is scaled by flow / sector
    area. Wind, pressure loss, evaporation, drift, and network hydraulics are omitted.
    """
    x, y, r, a0, w = h
    dx, dy = X - x, Y - y
    s = np.hypot(dx, dy) / r
    inr = s <= 1.0
    if w < 359.99:
        ang = (np.degrees(np.arctan2(dy, dx)) - a0) % 360.0
        inr &= ang <= w
    if radial_profile is None:
        slope = float(radial_slope)
        if not np.isfinite(slope) or slope <= -1.0:
            raise ValueError("radial_slope must be finite and greater than -1")
        # A normalized linear radial family for explicit sensitivity studies.
        # Its area-weighted mean is 1 because the area-weighted mean of s is 2/3.
        rate = (1.0 + slope * s) / (1.0 + 2.0 * slope / 3.0)
    else:
        rate = np.interp(s, radial_profile[:, 0], radial_profile[:, 1])
    if flow_lpm is not None:
        arc_fraction = min(float(w), 360.0) / 360.0
        mean_mm_h = 60.0 * float(flow_lpm) / (np.pi * r * r * arc_fraction)
        rate = rate * mean_mm_h
    return np.where(inr, rate, 0.0)



def load_polygon_csv(path):
    """Load a site boundary from local metric coordinates in a CSV.

    Required columns: x_m,y_m. Coordinates must already be in a local,
    projected Cartesian coordinate system measured in metres; longitude and
    latitude degrees are not accepted as a metric coordinate system.
    Vertices are ordered around one simple polygon. A repeated final copy of
    the first vertex is accepted and removed.
    """
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"x_m", "y_m"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("polygon CSV must contain x_m,y_m columns")
        rows = list(reader)
    if len(rows) < 3:
        raise ValueError("polygon CSV must contain at least three vertices")
    try:
        polygon = np.array([[float(row["x_m"]), float(row["y_m"])] for row in rows], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("polygon CSV coordinates must be numeric") from exc
    if not np.all(np.isfinite(polygon)):
        raise ValueError("polygon CSV coordinates must be finite")
    if len(polygon) > 3 and np.allclose(polygon[0], polygon[-1]):
        polygon = polygon[:-1]
    if len(np.unique(polygon, axis=0)) < 3:
        raise ValueError("polygon CSV must contain at least three unique vertices")
    x, y = polygon[:, 0], polygon[:, 1]
    area = abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2.0
    if not np.isfinite(area) or area <= 1e-9:
        raise ValueError("polygon CSV must describe a non-zero-area polygon")
    return polygon


def load_heads_csv(path):
    """Load a baseline sprinkler layout.

    Required columns: x_m,y_m,throw_m,start_angle_deg,arc_width_deg. Angles
    are degrees counter-clockwise from +x in the same local metric coordinate
    system as the polygon. This loader validates numeric ranges, not whether
    the supplied heads are physically installable or hydraulically compatible.
    """
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"x_m", "y_m", "throw_m", "start_angle_deg", "arc_width_deg"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(
                "heads CSV must contain x_m,y_m,throw_m,start_angle_deg,arc_width_deg columns"
            )
        rows = list(reader)
    if not rows:
        raise ValueError("heads CSV must contain at least one sprinkler")
    try:
        heads = np.array(
            [[float(row["x_m"]), float(row["y_m"]), float(row["throw_m"]),
              float(row["start_angle_deg"]), float(row["arc_width_deg"])] for row in rows],
            dtype=float,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("heads CSV values must be numeric") from exc
    if not np.all(np.isfinite(heads)):
        raise ValueError("heads CSV values must be finite")
    if np.any(heads[:, 2] <= 0):
        raise ValueError("throw_m must be positive")
    if np.any(heads[:, 4] <= 0) or np.any(heads[:, 4] > 360):
        raise ValueError("arc_width_deg must be in (0, 360]")
    heads[:, 3] %= 360.0
    return heads


class Site:
    def __init__(self, poly, cfg):
        self.poly = poly
        self.radial_profile = cfg.get("radial_profile")
        self.radial_slope = cfg.get("radial_slope", 0.0)
        self.flow_lpm = cfg.get("flow_lpm")
        self.path = Path(poly)
        c = cfg["cell"]
        m = cfg["margin"]
        x0, y0 = poly.min(axis=0) - m
        x1, y1 = poly.max(axis=0) + m
        xs = np.arange(x0, x1, c) + c / 2
        ys = np.arange(y0, y1, c) + c / 2
        self.X, self.Y = np.meshgrid(xs, ys)
        pts = np.c_[self.X.ravel(), self.Y.ravel()]
        self.mask = self.path.contains_points(pts).reshape(self.X.shape)
        self.idx = np.flatnonzero(self.mask.ravel())
        self.extent = (x0, x1, y0, y1)
        self.area = self.mask.sum() * c * c
        self.bbox = (poly.min(axis=0), poly.max(axis=0))

    def total(self, heads):
        t = np.zeros_like(self.X)
        for h in heads:
            t += head_field(self.X, self.Y, h, self.radial_profile, self.flow_lpm, self.radial_slope)
        return t


def score(site, total, cfg):
    """LEGACY single objective (lower is better) plus metrics.
    AR = water that must be applied so the driest 25% of the lawn reaches the
    target depth; a penalty forbids dry spots (dry = share of lawn cells below
    30% of THIS layout's own mean depth)."""
    lawn = total.ravel()[site.idx]
    n = lawn.size
    k = max(1, int(0.25 * n))
    lq = np.partition(lawn, k - 1)[:k].mean()
    if lq <= 1e-9:
        return 1e6, dict(AR=np.inf, overspray=1.0, CU=0.0, dry=1.0)
    mean = lawn.mean()
    ar = total.sum() / (lq * n)
    dry = float(np.mean(lawn < cfg["dry_thresh_frac"] * mean))
    pen = 5.0 * max(0.0, dry - cfg["dry_frac_limit"])
    over = 1.0 - lawn.sum() / total.sum()          # overspray share of OWN total water
    cu = 1.0 - np.mean(np.abs(lawn - mean)) / mean  # Christiansen-style uniformity
    return ar + pen, dict(AR=ar, overspray=over, CU=cu, dry=dry)
