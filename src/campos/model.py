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


def head_field(X, Y, h, radial_profile=None, flow_lpm=None):
    """Return a relative field, or estimated precipitation in mm/h if flow is set.

    Head tuple h = (x, y, r, a0, w): position [m], throw radius [m], sector
    start angle [degrees CCW from +x], and sector width [degrees].
    The default radial profile is an analytic placeholder; a supplied profile
    is normalized to area-weighted mean 1. When flow_lpm is provided, its
    shape is scaled using flow divided by swept sector area.
    Wind, pressure loss, evaporation, drift, and network hydraulics are omitted.
    """
    x, y, r, a0, w = h
    dx, dy = X - x, Y - y
    s = np.hypot(dx, dy) / r
    inr = s <= 1.0
    if w < 359.99:
        ang = (np.degrees(np.arctan2(dy, dx)) - a0) % 360.0
        inr &= ang <= w
    if radial_profile is None:
        # Neutral mass-conserving null model: constant precipitation per unit
        # area inside the wetted sector. Do not invent a radial gradient when
        # no nozzle-specific catch-can profile is available.
        rate = np.ones_like(s, dtype=float)
    else:
        rate = np.interp(s, radial_profile[:, 0], radial_profile[:, 1])
    if flow_lpm is not None:
        arc_fraction = min(float(w), 360.0) / 360.0
        mean_mm_h = 60.0 * float(flow_lpm) / (np.pi * r * r * arc_fraction)
        rate = rate * mean_mm_h
    return np.where(inr, rate, 0.0)


class Site:
    def __init__(self, poly, cfg):
        self.poly = poly
        self.radial_profile = cfg.get("radial_profile")
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
            t += head_field(self.X, self.Y, h, self.radial_profile, self.flow_lpm)
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
