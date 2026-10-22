"""Synthetic lawn geometry, sprinkler field, and base metric functions.

These functions define the current simplified research model; they are not a
calibrated representation of real-world irrigation hydraulics.
"""
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
def head_field(X, Y, h):
    """Relative precipitation rate of one rotary head (matched-precipitation
    nozzle: rate does not change with radius/arc, total flow ~ swept area).
    Head tuple h = (x, y, r, a0, w):
        x, y  head position [m]
        r     throw radius [m]
        a0    start angle of the swept sector [deg, CCW from +x]
        w     sector width [deg]; w >= 360 means a full circle
    Radial profile: 1.5*(1-0.5 s), s=d/r, normalised so the sector mean is 1.
    Wind, pressure loss, evaporation and drift are NOT modelled.
    (TODO(vendor-profile): see top of file.)"""
    x, y, r, a0, w = h
    dx, dy = X - x, Y - y
    s = np.hypot(dx, dy) / r
    inr = s <= 1.0
    if w < 359.99:
        ang = (np.degrees(np.arctan2(dy, dx)) - a0) % 360.0
        inr &= ang <= w
    return np.where(inr, 1.5 * (1.0 - 0.5 * s), 0.0)


class Site:
    def __init__(self, poly, cfg):
        self.poly = poly
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
            t += head_field(self.X, self.Y, h)
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
