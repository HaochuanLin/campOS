#!/usr/bin/env python3
"""campOS: a synthetic sprinkler-layout optimization research prototype.

The simulator compares sprinkler layouts on generated, irregular lawn polygons.
It supports four modes:

- movable: optimize position, throw radius, and sector angles using the legacy
  AR objective.
- fixed: keep head coordinates fixed and optimize radius and sector angles.
- pareto-movable: explore overspray/interior-deficit trade-offs with movable
  heads.
- pareto-fixed: explore the same trade-off without relocating heads.

Quick examples::

    python campos_sim.py --mode movable --quick --sites A --outdir out/demo
    python campos_sim.py --mode fixed --sites A C --outdir out/fixed
    python campos_sim.py --mode pareto-fixed --quick --sites C --outdir out/pareto

All built-in lawns are synthetic. Sprinkler precipitation, throw range, water
tariffs, and retrofit costs include placeholders. The model does not include
wind, pressure loss, evaporation, drift, slope, soil, or field validation.
Reported savings and payback values are exploratory model outputs, not
engineering recommendations or guarantees.

The default seed and optimization settings are part of the baseline behavior.
Generated outputs include CSV summaries, plots, and run metadata.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import time
from pathlib import Path as FilePath

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path

# ------------------------------------------------------------ mode labels
# Every CSV row / plot title carries one of these so the two families of
# results can never be confused.
MODE_MOVABLE = dict(
    key="movable",
    csv="MOVABLE-HEADS (legacy single-objective mode)",
    plot="MOVABLE-HEADS mode (xy AND r,a0,w tuned)",
)
MODE_FIXED = dict(
    key="fixed",
    csv="FIXED-POSITION (retrofit single-objective mode)",
    plot="FIXED-POSITION mode (xy fixed; only r,a0,w tuned)",
)
MODES = {"movable": MODE_MOVABLE, "fixed": MODE_FIXED}

# ----------------------------------------------------------------- config
CFG = dict(
    cell=0.5,               # grid resolution [m]
    margin=14.0,            # surrounding pavement/non-lawn area simulated [m]
    base_radius=6.0,        # baseline head throw radius [m]   PLACEHOLDER (data sheet)
    base_spacing=6.0,       # head-to-head spacing, = radius   (common practice)
    r_min=3.5, r_max=9.0,   # adjustable throw range [m]       PLACEHOLDER (data sheet)
    sa_iters=12000,         # simulated-annealing steps per restart (single objective)
    restarts=2,
    seed=7,
    dry_frac_limit=0.02,    # allowed share of lawn below dry_thresh_frac of reference depth
    # --- bi-objective / Pareto settings (search device, not physics) ---
    dry_thresh_frac=0.3,    # a lawn cell is "dry" if depth < 0.3 x reference depth
    target_factor=1.0,      # PLACEHOLDER: target depth T = factor x baseline mean lawn depth
    pareto_weights=(0.02, 0.10, 0.25, 0.50, 0.75, 0.92),  # weight on overspray in the sweep
    pareto_iters=8000,      # SA steps per (weight, start)
    pareto_T0=0.30, pareto_T1=0.004,   # SA temperature in normalised-objective units
    obj_scale=0.05,         # objectives divided by this inside the SA score (search only)
    dry_pen_w=30.0,         # SA penalty slope for dry_frac above the limit (search only)
    archive_eps=0.002,      # archive resolution: points within eps of an existing one are dropped
    pareto_max_points=40,   # thin the final front to this many points for CSV/plot
    cu_drop_budget=0.03,    # PLACEHOLDER: "accept this much CU loss vs. the most uniform
                            # Pareto point to buy lower overspray" -> marked as 'selected'
    # --- economics: ALL PLACEHOLDERS, replace with real numbers ---
    price_per_m3=5.0,       # water tariff [CNY/m3]
    annual_depth_mm=450.0,  # seasonal irrigation depth the lawn needs [mm/yr]
    cost_adjust_head=300.0, # re-aim / change nozzle per head [CNY]
    cost_move_head=1500.0,  # relocate a head per head [CNY]
    move_threshold_m=1.0,   # moved farther than this counts as relocation
    changed_tol_r=0.05,     # [m]   a head counts as "changed" in fixed mode if |dr| > this
    changed_tol_deg=3.0,    # [deg] ... or |da0| / |dw| > this
)

# TODO(vendor-profile): replace the assumed radial profile in head_field() with
#   the manufacturer's catch-can / precipitation distribution (radius vs rate,
#   per nozzle and per operating pressure; import from CSV) and the real
#   throw-vs-pressure table for r_min/r_max.  Until then every depth below is
#   a stylised placeholder.
# TODO(wind): add a wind / pressure sensitivity module: wind speed + direction
#   (throw shortening upwind, drift downwind), pressure +-X% on r and flow,
#   Monte-Carlo over those, and report whether each Pareto point stays on the
#   front (robustness).  Currently NO wind, NO pressure loss, NO evaporation.

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

# ------------------------------------------------------- baseline layouts
def preset_arc(site, x, y, r):
    """Installer-style head: full circle in the open, otherwise the preset arc
    (90/180/270) aimed to keep water on the lawn."""
    dirs = np.arange(0, 360, 10) + 5.0
    px = x + 0.9 * r * np.cos(np.radians(dirs))
    py = y + 0.9 * r * np.sin(np.radians(dirs))
    inside = site.path.contains_points(np.c_[px, py])
    best, best_s = (0.0, 360.0), -1e9
    for w in (90, 180, 270, 360):
        for a0 in (range(0, 360, 15) if w < 360 else [0]):
            cov = ((dirs - a0) % 360.0) <= w
            sc = inside[cov].sum() - 2 * (~inside[cov]).sum()
            if sc > best_s:
                best_s, best = sc, (float(a0), float(w))
    return (x, y, r, best[0], best[1])


def near_inside(site, x, y, tol=0.6):
    """Inside the lawn, or on its edge (within tol m), where installers put
    perimeter heads."""
    if site.path.contains_point((x, y)):
        return True
    for a in range(0, 360, 45):
        if site.path.contains_point((x + tol * np.cos(np.radians(a)),
                                     y + tol * np.sin(np.radians(a)))):
            return True
    return False


def baseline_layout(site, cfg):
    """Square grid at spacing = radius, edge heads set to preset arcs.
    Best of 3 radii x 9 grid offsets (scored with the same metric as the
    optimizer), so the baseline is a competent installer, not a straw man."""
    (minx, miny), (maxx, maxy) = site.bbox
    best, best_sc = None, np.inf
    for r in (4.0, 5.0, cfg["base_radius"]):
        sp = r
        for fx in (0.0, 0.33, 0.66):
            for fy in (0.0, 0.33, 0.66):
                heads = []
                for x in np.arange(minx + fx * sp, maxx + 1e-9, sp):
                    for y in np.arange(miny + fy * sp, maxy + 1e-9, sp):
                        if near_inside(site, x, y):
                            heads.append(preset_arc(site, x, y, r))
                if not heads:
                    continue
                sc, _ = score(site, site.total(heads), cfg)
                if sc < best_sc:
                    best_sc, best = sc, heads
    return np.array(best, float)


_SITE_CACHE = {}


def get_site_and_baseline(name, poly, cfg):
    """Build and cache a baseline for this exact site geometry and config.

    The cache key includes the polygon and every config value so callers that
    compare multiple resolutions or parameter sets cannot accidentally reuse
    a stale grid or baseline from an earlier run.
    """
    polygon = np.asarray(poly, dtype=float)
    key = (
        name,
        tuple(polygon.shape),
        tuple(polygon.ravel()),
        tuple(sorted((k, repr(v)) for k, v in cfg.items())),
    )
    if key not in _SITE_CACHE:
        site = Site(polygon, cfg)
        _SITE_CACHE[key] = (site, baseline_layout(site, cfg))
    return _SITE_CACHE[key]


def naive_full_circle(heads0):
    """REFERENCE ONLY: same grid, same radii, but every head left as a full
    circle (no arc presets).  Stands for the 'nobody tuned the arcs' pain
    point; used as a marker in the Pareto plots, never as the baseline."""
    h = heads0.copy()
    h[:, 3] = 0.0
    h[:, 4] = 360.0
    return h

# ------------------------------------------------- shared SA move proposal
def _propose(site, heads, rng, cfg, frac, fixed_xy):
    """Pick one head and perturb one of its parameters.
    move 0: shift head position (x,y)          -> only in MOVABLE mode
    move 1: throw radius r   (new nozzle / pressure trim)
    move 2: arc width w      (re-set the arc stop)
    move 3: start angle a0   (re-set the other stop)
    Step sizes shrink as the annealing proceeds (frac 0 -> 1).
    Returns (head index, new head tuple or None if the move is invalid).
    RNG call order is identical to v1 for the movable mode (regression-safe)."""
    n = len(heads)
    sc = 0.3 + 0.7 * (1 - frac)
    i = rng.integers(n)
    h = heads[i].copy()
    m = rng.integers(1, 4) if fixed_xy else rng.integers(4)
    if m == 0:
        h[0] += rng.normal(0, 1.5 * sc)
        h[1] += rng.normal(0, 1.5 * sc)
        if not site.path.contains_point((h[0], h[1])):
            return i, None
    elif m == 1:
        h[2] = np.clip(h[2] + rng.normal(0, 0.7 * sc), cfg["r_min"], cfg["r_max"])
    elif m == 2:
        h[4] = np.clip(h[4] + rng.normal(0, 30 * sc), 30.0, 360.0)
    else:
        h[3] = (h[3] + rng.normal(0, 35 * sc)) % 360.0
    return i, h

# ------------------------------------------- single objective (legacy AR)
def optimize(site, heads0, cfg, seed, fixed_xy=False):
    """Simulated annealing on the legacy AR score.
    fixed_xy=True  -> head coordinates never change (retrofit mode)."""
    rng = np.random.default_rng(seed)
    heads = heads0.copy()
    fields = [head_field(site.X, site.Y, h) for h in heads]
    total = np.sum(fields, axis=0)
    cur, _ = score(site, total, cfg)
    best, best_h = cur, heads.copy()
    T0, T1 = 0.03, 0.0004
    iters = cfg["sa_iters"]
    for it in range(iters):
        frac = it / iters
        T = T0 * (T1 / T0) ** frac
        i, h = _propose(site, heads, rng, cfg, frac, fixed_xy)
        if h is None:
            continue
        newf = head_field(site.X, site.Y, h)
        new_total = total - fields[i] + newf
        new, _ = score(site, new_total, cfg)
        if new < cur or rng.random() < np.exp((cur - new) / T):
            heads[i], fields[i], total, cur = h, newf, new_total, new
            if cur < best:
                best, best_h = cur, heads.copy()
    return best_h


def run_site(name, poly, cfg, fixed_xy=False):
    """Single-objective (AR) run on one site.  fixed_xy selects the mode."""
    mode = MODE_FIXED if fixed_xy else MODE_MOVABLE
    site, h0 = get_site_and_baseline(name, poly, cfg)
    _, m0 = score(site, site.total(h0), cfg)
    best_h, best_sc = None, np.inf
    for k in range(cfg["restarts"]):
        h = optimize(site, h0, cfg, cfg["seed"] + 17 * k, fixed_xy=fixed_xy)
        sc, _ = score(site, site.total(h), cfg)
        if sc < best_sc:
            best_sc, best_h = sc, h
    _, m1 = score(site, site.total(best_h), cfg)
    saving_frac = 1.0 - m1["AR"] / m0["AR"]
    # economics (placeholders!)
    annual_m3 = cfg["annual_depth_mm"] / 1000.0 * site.area * (m0["AR"] - m1["AR"])
    annual_cny = annual_m3 * cfg["price_per_m3"]
    if fixed_xy:
        # hard guarantee of the mode: coordinates untouched
        assert np.array_equal(best_h[:, :2], h0[:, :2]), "fixed mode moved a head!"
        moved = 0
        d_ang = np.abs(best_h[:, 3] - h0[:, 3])
        d_ang = np.minimum(d_ang, 360.0 - d_ang)
        both_full = (h0[:, 4] >= 359.99) & (best_h[:, 4] >= 359.99)  # a0 meaningless
        changed_mask = ((np.abs(best_h[:, 2] - h0[:, 2]) > cfg["changed_tol_r"])
                        | (np.abs(best_h[:, 4] - h0[:, 4]) > cfg["changed_tol_deg"])
                        | ((d_ang > cfg["changed_tol_deg"]) & ~both_full))
        changed = int(changed_mask.sum())
        cost = changed * cfg["cost_adjust_head"]          # no digging, no relocation
    else:
        moved = int(np.sum(np.hypot(*(best_h[:, :2] - h0[:, :2]).T) > cfg["move_threshold_m"]))
        changed = len(h0)       # v1 cost model: every head is re-aimed / re-nozzled
        cost = len(h0) * cfg["cost_adjust_head"] + moved * cfg["cost_move_head"]
    return dict(
        name=name, mode=mode, site=site, heads0=h0, heads1=best_h, m0=m0, m1=m1,
        n_heads=len(h0), moved=moved, changed=changed, area=site.area,
        water_saving=saving_frac, annual_m3=annual_m3, annual_cny=annual_cny,
        cost=cost, payback=cost / annual_cny if annual_cny > 0 else np.inf,
    )

# ----------------------------------------------- bi-objective (Pareto)
def reference_levels(site, heads0, cfg):
    """Normalisers taken from the baseline layout of this site:
    W0 = total water applied (inside + outside), T = target depth."""
    total0 = site.total(heads0)
    lawn0 = total0.ravel()[site.idx]
    return dict(W0=float(total0.sum()), T=float(cfg["target_factor"] * lawn0.mean()))


def bi_eval(site, total, ref, cfg):
    """(f1 overspray_ratio, f2 deficit, dry_frac) for a depth field.
    f1: water outside the polygon / W0 (physical loss, relative to baseline).
    f2: mean relative shortfall below the target depth T over the lawn.
    dry_frac: share of lawn cells with depth < dry_thresh_frac * T."""
    lawn = total.ravel()[site.idx]
    outside = total.sum() - lawn.sum()
    f1 = max(0.0, outside / ref["W0"])   # clip float noise (-0.0)
    f2 = float(np.mean(np.clip(1.0 - lawn / ref["T"], 0.0, None)))
    dry = float(np.mean(lawn < cfg["dry_thresh_frac"] * ref["T"]))
    return float(f1), f2, dry


def bi_report(site, heads, ref, cfg):
    """Full metric set for one layout (objectives + legacy metrics)."""
    total = site.total(heads)
    f1, f2, dry = bi_eval(site, total, ref, cfg)
    _, m = score(site, total, cfg)
    return dict(f1=f1, f2=f2, dry=dry, CU=float(m["CU"]), AR=float(m["AR"]),
                over_own=float(m["overspray"]), water_rel=float(total.sum() / ref["W0"]),
                heads=heads)


class ParetoArchive:
    """Running set of non-dominated (f1, f2) points with their head arrays.
    Points within `eps` of an existing point in BOTH objectives are dropped,
    which keeps the archive small (resolution of the front)."""

    def __init__(self, eps):
        self.eps = eps
        self.f = np.empty((0, 2))
        self.h = []

    def add(self, f1, f2, heads):
        if len(self.h):
            if np.any((self.f[:, 0] <= f1 + self.eps) & (self.f[:, 1] <= f2 + self.eps)):
                return
            keep = ~((self.f[:, 0] >= f1) & (self.f[:, 1] >= f2))   # drop what we dominate
            if not keep.all():
                self.f = self.f[keep]
                self.h = [x for x, k in zip(self.h, keep) if k]
        self.f = np.vstack([self.f, [f1, f2]])
        self.h.append(heads.copy())


def pareto_search(site, heads0, cfg, fixed_xy, seed, ref, warm=None):
    """Sweep the overspray weight lam in the SA score
        J = lam*f1/s + (1-lam)*f2/s + dry_pen_w*max(0, dry - limit)
    (J is ONLY a search device).  Every accepted state that satisfies the
    dry-fraction constraint is offered to the non-dominated archive, so the
    result is the Pareto set of (f1, f2), not a collection of weighted optima.
    Each weight is run from the baseline layout AND (if given) from `warm`
    (a good single-objective layout) - a warm start keeps the front from
    being dominated by solutions we already know.  fixed_xy keeps head
    coordinates fixed."""
    lim = cfg["dry_frac_limit"]
    s = cfg["obj_scale"]
    arch = ParetoArchive(cfg["archive_eps"])
    iters = cfg["pareto_iters"]
    starts = [(heads0, 1.0)] + ([(warm, 0.35)] if warm is not None else [])
    runs = [(st, tf, lam) for st, tf in starts for lam in cfg["pareto_weights"]]
    for wi, (start, tfac, lam) in enumerate(runs):
        rng = np.random.default_rng(seed + 101 * wi)
        T0, T1 = cfg["pareto_T0"] * tfac, cfg["pareto_T1"]
        heads = start.copy()
        fields = [head_field(site.X, site.Y, h) for h in heads]
        total = np.sum(fields, axis=0)

        def J(tot):
            f1, f2, dry = bi_eval(site, tot, ref, cfg)
            pen = cfg["dry_pen_w"] * max(0.0, dry - lim)
            return lam * f1 / s + (1.0 - lam) * f2 / s + pen, f1, f2, dry

        cur, f1, f2, dry = J(total)
        if dry <= lim:
            arch.add(f1, f2, heads)
        for it in range(iters):
            frac = it / iters
            T = T0 * (T1 / T0) ** frac
            i, h = _propose(site, heads, rng, cfg, frac, fixed_xy)
            if h is None:
                continue
            newf = head_field(site.X, site.Y, h)
            new_total = total - fields[i] + newf
            new, f1, f2, dry = J(new_total)
            if new < cur or rng.random() < np.exp((cur - new) / T):
                heads[i], fields[i], total, cur = h, newf, new_total, new
                if dry <= lim:
                    arch.add(f1, f2, heads)
    return arch.h


def select_tradeoff(front, budget):
    """Index of the 'accept a slight uniformity loss for less overspray'
    point: the lowest-overspray Pareto point whose CU is within `budget` of
    the most uniform point on the front.  (All front points already satisfy
    the dry-fraction constraint.)"""
    cu_best = max(p["CU"] for p in front)
    ok = [i for i, p in enumerate(front) if p["CU"] >= cu_best - budget]
    return min(ok, key=lambda i: front[i]["f1"])


def run_pareto(name, poly, cfg, fixed_xy, refs=None):
    """Bi-objective run on one site; returns the thinned Pareto front plus
    reference layouts (baseline, naive full-circle, optional single-AR optima)."""
    mode = MODE_FIXED if fixed_xy else MODE_MOVABLE
    site, h0 = get_site_and_baseline(name, poly, cfg)
    ref = reference_levels(site, h0, cfg)
    warm = None
    if refs:                                   # reuse the single-objective AR optimum
        warm = next(iter(refs.values()))
    else:                                      # otherwise compute one (1 restart)
        warm = optimize(site, h0, cfg, cfg["seed"], fixed_xy=fixed_xy)
        refs = {f"AR-optimum ({'fixed' if fixed_xy else 'movable'}, legacy)": warm}
    cand = pareto_search(site, h0, cfg, fixed_xy, cfg["seed"] + 5, ref, warm=warm)
    if fixed_xy:
        for h in cand:
            assert np.array_equal(h[:, :2], h0[:, :2]), "fixed mode moved a head!"
    # thin evenly along the front before the (more expensive) full evaluation
    order = sorted(range(len(cand)), key=lambda i: bi_eval(site, site.total(cand[i]), ref, cfg)[0])
    if len(order) > cfg["pareto_max_points"]:
        pick = np.unique(np.round(np.linspace(0, len(order) - 1, cfg["pareto_max_points"])).astype(int))
        order = [order[j] for j in pick]
    front = [bi_report(site, cand[i], ref, cfg) for i in order]
    front.sort(key=lambda p: p["f1"])
    sel = select_tradeoff(front, cfg["cu_drop_budget"]) if front else None
    refs_out = {"Baseline (standard grid)": bi_report(site, h0, ref, cfg),
                "Naive full-circle (reference only)": bi_report(site, naive_full_circle(h0), ref, cfg)}
    for label, heads in (refs or {}).items():
        refs_out[label] = bi_report(site, heads, ref, cfg)
    # sanity check: no feasible reference layout may dominate a front point
    # (if one does, the search under-converged and the front is not trustworthy)
    for label, p in refs_out.items():
        if p["dry"] <= cfg["dry_frac_limit"]:
            bad = [q for q in front if p["f1"] < q["f1"] - 1e-9 and p["f2"] < q["f2"] - 1e-9]
            if bad:
                print(f"   WARNING {name}: reference '{label}' dominates {len(bad)} front point(s) "
                      f"- search under-converged", flush=True)
    return dict(name=name, mode=mode, site=site, ref=ref, front=front, selected=sel,
                refs=refs_out, heads0=h0)

# ------------------------------------------------------------------ output
def _tag(mode):
    return mode["key"]


def write_results_csv(results, fn):
    rows = sorted(results, key=lambda r: r["payback"])
    with open(fn, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["mode", "rank", "site", "area_m2", "sprinkler_count", "heads_moved",
                    "heads_changed", "baseline_AR", "optimized_AR",
                    "baseline_overspray_pct_of_own_water", "optimized_overspray_pct_of_own_water",
                    "baseline_CU", "optimized_CU", "baseline_dry_area_pct", "optimized_dry_area_pct",
                    "AR_based_saving_metric_pct", "annual_water_saving_m3_placeholder",
                    "annual_cost_saving_CNY_placeholder", "retrofit_cost_CNY_placeholder",
                    "payback_years_placeholder"])
        for i, r in enumerate(rows, 1):
            w.writerow([r["mode"]["csv"], i, r["name"], f"{r['area']:.0f}", r["n_heads"],
                        r["moved"], r["changed"],
                        f"{r['m0']['AR']:.3f}", f"{r['m1']['AR']:.3f}",
                        f"{r['m0']['overspray']*100:.1f}", f"{r['m1']['overspray']*100:.1f}",
                        f"{r['m0']['CU']:.3f}", f"{r['m1']['CU']:.3f}",
                        f"{r['m0']['dry']*100:.1f}", f"{r['m1']['dry']*100:.1f}",
                        f"{r['water_saving']*100:.1f}", f"{r['annual_m3']:.0f}",
                        f"{r['annual_cny']:.0f}", f"{r['cost']:.0f}", f"{r['payback']:.1f}"])
    return rows


def plot_layouts(results, cfg, fn, tag=""):
    fig, axes = plt.subplots(len(results), 2, figsize=(12, 3.8 * len(results) + 0.6),
                             constrained_layout=True, squeeze=False)
    for row, r in zip(axes, results):
        s = r["site"]
        for ax, heads, m, side in ((row[0], r["heads0"], r["m0"], "Baseline (standard grid)"),
                                   (row[1], r["heads1"], r["m1"], "Optimized")):
            t = s.total(heads)
            ax.imshow(np.where(s.mask, t, np.nan), origin="lower", extent=s.extent,
                      cmap="Blues", vmin=0, vmax=4)
            ax.imshow(np.where((~s.mask) & (t > 0), t, np.nan), origin="lower",
                      extent=s.extent, cmap="Reds", vmin=0, vmax=4)
            ax.plot(*np.vstack([s.poly, s.poly[:1]]).T, "k-", lw=1.5)
            ax.plot(heads[:, 0], heads[:, 1], "k.", ms=6)
            ax.set_aspect("equal")
            ax.set_title(f"{r['name']} · {side}\nAR={m['AR']:.2f}  overspray={m['overspray']*100:.0f}%  "
                         f"CU={m['CU']:.2f}  dry={m['dry']*100:.1f}%", fontsize=9)
    fig.suptitle(f"[{tag}]  blue = water on lawn, red = overspray  (SYNTHETIC lawns, "
                 f"PLACEHOLDER sprinkler profile)", fontsize=11)
    fig.savefig(fn, dpi=110)
    plt.close(fig)


def plot_ranking(rows, fn, tag=""):
    fig, ax = plt.subplots(figsize=(7.5, 3.9), constrained_layout=True)
    names = [r["name"] for r in rows]
    vals = [r["payback"] if np.isfinite(r["payback"]) else 0.0 for r in rows]
    bars = ax.barh(names[::-1], vals[::-1], color="#3b7ddd")
    for b, r in zip(bars, rows[::-1]):
        if not np.isfinite(r["payback"]):
            ax.text(0.2, b.get_y() + b.get_height() / 2, "no saving", va="center", fontsize=8)
    ax.set_xlabel("Payback [years]  (PLACEHOLDER costs / prices)")
    ax.set_title(f"[{tag}] renovation priority: shorter payback first", fontsize=10)
    fig.savefig(fn, dpi=110)
    plt.close(fig)


def write_comparison_csv(by_mode, fn):
    """Long-format table: baseline vs each single-objective mode, per site."""
    with open(fn, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["mode", "site", "AR", "overspray_pct_of_own_water", "CU", "dry_area_pct",
                    "AR_based_saving_metric_pct", "heads_moved", "heads_changed",
                    "retrofit_cost_CNY_placeholder", "payback_years_placeholder"])
        names = [r["name"] for r in next(iter(by_mode.values()))]
        for nm in names:
            first = True
            for key, res in by_mode.items():
                r = next(x for x in res if x["name"] == nm)
                if first:
                    w.writerow(["BASELINE (standard grid)", nm, f"{r['m0']['AR']:.3f}",
                                f"{r['m0']['overspray']*100:.1f}", f"{r['m0']['CU']:.3f}",
                                f"{r['m0']['dry']*100:.1f}", "0.0", 0, 0, 0, ""])
                    first = False
                w.writerow([r["mode"]["csv"], nm, f"{r['m1']['AR']:.3f}",
                            f"{r['m1']['overspray']*100:.1f}", f"{r['m1']['CU']:.3f}",
                            f"{r['m1']['dry']*100:.1f}", f"{r['water_saving']*100:.1f}",
                            r["moved"], r["changed"], f"{r['cost']:.0f}", f"{r['payback']:.1f}"])


def write_pareto_csv(results, fn, cfg):
    with open(fn, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["mode", "site", "point_type", "point_index", "selected_tradeoff",
                    "overspray_pct_of_baseline_total_water_f1", "interior_deficit_pct_f2",
                    f"dry_area_pct_constraint_le_{cfg['dry_frac_limit'] * 100:.0f}",
                    "CU", "AR_legacy", "overspray_pct_of_own_water", "total_water_relative_to_baseline"])
        for r in results:
            def row(kind, i, p, selected=""):
                w.writerow([r["mode"]["csv"], r["name"], kind, i, selected,
                            f"{p['f1']*100:.2f}", f"{p['f2']*100:.2f}", f"{p['dry']*100:.2f}",
                            f"{p['CU']:.3f}", f"{p['AR']:.3f}", f"{p['over_own']*100:.2f}",
                            f"{p['water_rel']:.3f}"])
            for label, p in r["refs"].items():
                row("reference: " + label, "", p)
            for i, p in enumerate(r["front"]):
                row("PARETO", i, p, "YES" if i == r["selected"] else "")


def plot_pareto(results, fn, cfg):
    """Rows: (1) deficit f2 [objective 2], (2) CU [uniformity], (3) dry fraction
    [constraint].  X axis in every panel: overspray ratio f1 (% of the
    baseline's total applied water)."""
    n = len(results)
    mode = results[0]["mode"]
    fig, axes = plt.subplots(3, n, figsize=(4.6 * n, 10.5), constrained_layout=True, squeeze=False)
    styles = {"Baseline (standard grid)": ("s", "black", 70),
              "Naive full-circle (reference only)": ("X", "#d62728", 80)}
    for c, r in enumerate(results):
        fr = r["front"]
        x = np.array([p["f1"] for p in fr]) * 100
        series = [("f2", "Interior deficit f2 [% of target]", 100),
                  ("CU", "Uniformity CU  (higher = better)", 1),
                  ("dry", "Dry-zone fraction [% of lawn]", 100)]
        for rr, (key, ylab, mult) in enumerate(series):
            ax = axes[rr][c]
            y = np.array([p[key] for p in fr]) * mult
            ax.plot(x, y, "-o", color="#1f77b4", ms=4, lw=1.2, label="Pareto front", zorder=3)
            for label, p in r["refs"].items():
                if label in styles:
                    mk, col, sz = styles[label]
                else:
                    mk, col, sz = "*", "#2ca02c", 130
                ax.scatter([p["f1"] * 100], [p[key] * mult], marker=mk, c=col, s=sz,
                           label=label, zorder=4, edgecolors="k", linewidths=0.5)
            if r["selected"] is not None:
                p = fr[r["selected"]]
                ax.scatter([p["f1"] * 100], [p[key] * mult], s=220, facecolors="none",
                           edgecolors="#ff7f0e", linewidths=2.2, zorder=5,
                           label=f"selected: CU within {cfg['cu_drop_budget']:.2f} of best")
            if key == "dry":
                ax.axhline(cfg["dry_frac_limit"] * 100, color="gray", ls="--", lw=1,
                           label="dry-fraction limit")
            if rr == 0:
                ax.set_title(r["name"], fontsize=11)
            if rr == 2:
                ax.set_xlabel("Overspray ratio f1 [% of baseline total water]")
            if c == 0:
                ax.set_ylabel(ylab)
            ax.grid(alpha=0.3)
        if c == n - 1:
            axes[0][c].legend(fontsize=7, loc="upper right")
    fig.suptitle(f"[{mode['plot']}]  Pareto trade-off: overspray vs interior deficit / uniformity\n"
                 f"SYNTHETIC lawns, PLACEHOLDER sprinkler profile, no wind/pressure model - "
                 f"not field-validated", fontsize=11)
    fig.savefig(fn, dpi=110)
    plt.close(fig)

# -------------------------------------------------------------------- main
ALL_MODES = ["movable", "fixed", "pareto-fixed", "pareto-movable"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="campOS irrigation simulation prototype (v2)")
    ap.add_argument("--mode", nargs="+", default=["movable"],
                    choices=ALL_MODES + ["all"],
                    help="which run modes to execute (default: movable = original v1 behaviour)")
    ap.add_argument("--sites", nargs="+", default=None,
                    help="site letters to run, e.g. --sites A C (default: all five)")
    ap.add_argument("--outdir", default="out", help="output directory (default: out)")
    ap.add_argument("--quick", action="store_true", help="fewer SA iterations (smoke test)")
    args = ap.parse_args(argv)

    cfg = dict(CFG)
    if args.quick:
        cfg.update(sa_iters=2500, restarts=1, pareto_iters=1200)
    modes = ALL_MODES if "all" in args.mode else [m for m in ALL_MODES if m in args.mode]
    sites = {k: f for k, f in SITES.items()
             if args.sites is None or k.split()[0] in [s.upper() for s in args.sites]}
    if not sites:
        raise SystemExit("no sites selected")
    os.makedirs(args.outdir, exist_ok=True)
    out = lambda f: os.path.join(args.outdir, f)

    # Persist the exact run configuration and software versions beside outputs.
    # This adds provenance metadata without changing the simulation algorithm.
    metadata = {
        "schema_version": 1,
        "project": "campOS",
        "project_version": "0.1.0",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "matplotlib_version": matplotlib.__version__,
        "source_sha256": hashlib.sha256(FilePath(__file__).read_bytes()).hexdigest(),
        "arguments": vars(args),
        "selected_modes": modes,
        "selected_sites": list(sites.keys()),
        "config": cfg,
    }
    with open(out("run_metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, sort_keys=True)
        fh.write("\n")

    t0 = time.time()
    single = {}                                   # key -> list of run_site results

    for key in ("movable", "fixed"):
        if key not in modes:
            continue
        fixed = key == "fixed"
        res = []
        for name, f in sites.items():
            r = run_site(name, f(), cfg, fixed_xy=fixed)
            res.append(r)
            print(f"[{key:7s}] {name}: heads={r['n_heads']} moved={r['moved']} changed={r['changed']} "
                  f"AR {r['m0']['AR']:.2f}->{r['m1']['AR']:.2f} "
                  f"overspray {r['m0']['overspray']*100:.1f}->{r['m1']['overspray']*100:.1f}% "
                  f"CU {r['m0']['CU']:.2f}->{r['m1']['CU']:.2f}  [{time.time()-t0:.0f}s]", flush=True)
        single[key] = res
        rows = write_results_csv(res, out(f"results_{key}.csv"))
        plot_layouts(res, cfg, out(f"layouts_{key}.png"), tag=MODES[key]["plot"])
        plot_ranking(rows, out(f"ranking_{key}.png"), tag=MODES[key]["plot"])
        print(f"   -> results_{key}.csv, layouts_{key}.png, ranking_{key}.png", flush=True)
    if len(single) == 2:
        write_comparison_csv(single, out("comparison_single_objective.csv"))
        print("   -> comparison_single_objective.csv", flush=True)

    for key in ("pareto-fixed", "pareto-movable"):
        if key not in modes:
            continue
        fixed = key == "pareto-fixed"
        base_key = "fixed" if fixed else "movable"
        res = []
        for name, f in sites.items():
            refs = None
            if base_key in single:                # mark the single-objective AR optimum
                r1 = next(x for x in single[base_key] if x["name"] == name)
                refs = {f"AR-optimum ({MODES[base_key]['key']}, legacy)": r1["heads1"]}
            pr = run_pareto(name, f(), cfg, fixed_xy=fixed, refs=refs)
            res.append(pr)
            fr = pr["front"]
            sel = fr[pr["selected"]] if pr["selected"] is not None else None
            base = pr["refs"]["Baseline (standard grid)"]
            print(f"[{key:14s}] {name}: front={len(fr)} pts  "
                  f"f1 {fr[0]['f1']*100:.1f}..{fr[-1]['f1']*100:.1f}%  "
                  f"f2 {fr[0]['f2']*100:.1f}..{fr[-1]['f2']*100:.1f}%  "
                  f"baseline(f1={base['f1']*100:.1f}%,f2={base['f2']*100:.1f}%)  "
                  + (f"selected(f1={sel['f1']*100:.1f}%,f2={sel['f2']*100:.1f}%,CU={sel['CU']:.2f})"
                     if sel else "no feasible point")
                  + f"  [{time.time()-t0:.0f}s]", flush=True)
        write_pareto_csv(res, out(f"pareto_{key.split('-')[1]}.csv"), cfg)
        plot_pareto(res, out(f"pareto_{key.split('-')[1]}.png"), cfg)
        print(f"   -> pareto_{key.split('-')[1]}.csv, pareto_{key.split('-')[1]}.png", flush=True)
    print(f"done in {time.time()-t0:.0f}s -> {args.outdir}/", flush=True)


if __name__ == "__main__":
    main()
