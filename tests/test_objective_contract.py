"""Contract tests for the Pareto overspray/coverage objective.

These tests use synthetic fields intentionally: they validate the implemented
mathematics and guardrails, not physical sprinkler accuracy.
"""
import numpy as np

from campos import campos_sim as sim


def _site_and_reference():
    lawn = np.asarray([(0, 0), (4, 0), (4, 4), (0, 4)], dtype=float)
    sidewalk = np.asarray([(4, 0), (6, 0), (6, 4), (4, 4)], dtype=float)
    cfg = dict(sim.CFG, cell=1.0, margin=2.0, protected_polygon=sidewalk)
    site = sim.Site(lawn, cfg)
    # W0 is deliberately fixed across candidate layouts, as reference_levels()
    # does for the baseline layout.
    ref = {"W0": 100.0, "T": 10.0}
    return site, ref, cfg


def test_pareto_objectives_separate_protected_water_from_lawn_deficit():
    site, ref, cfg = _site_and_reference()
    good_lawn = np.full(site.X.shape, 0.0)
    good_lawn[site.mask] = 10.0
    good_lawn[site.protected_mask] = 4.0
    poor_lawn = good_lawn.copy()
    poor_lawn[site.mask] = 2.0
    poor_lawn[site.protected_mask] = 0.5

    good_f1, good_f2, _ = sim.bi_eval(site, good_lawn, ref, cfg)
    poor_f1, poor_f2, _ = sim.bi_eval(site, poor_lawn, ref, cfg)

    # Less sidewalk water must not disguise a much worse lawn deficit.
    assert poor_f1 < good_f1
    assert poor_f2 > good_f2
    assert good_f2 == 0.0
    assert poor_f2 == 0.8


def test_pareto_f1_uses_surveyed_protected_polygon_not_all_surroundings():
    site, ref, cfg = _site_and_reference()
    field = np.zeros(site.X.shape, dtype=float)
    field[site.mask] = 10.0
    field[site.protected_mask] = 2.0
    field[~(site.mask | site.protected_mask)] = 30.0

    f1, _, _ = sim.bi_eval(site, field, ref, cfg)
    assert f1 == 2.0 * int(site.protected_mask.sum()) / ref["W0"]
    assert f1 < (field.sum() - field.ravel()[site.idx].sum()) / ref["W0"]


def test_pareto_f1_without_surveyed_protected_polygon_is_all_outside_lawn():
    lawn = np.asarray([(0, 0), (4, 0), (4, 4), (0, 4)], dtype=float)
    cfg = dict(sim.CFG, cell=1.0, margin=2.0)
    site = sim.Site(lawn, cfg)
    field = np.ones(site.X.shape, dtype=float)
    field[site.mask] = 3.0
    ref = {"W0": 100.0, "T": 3.0}

    f1, _, _ = sim.bi_eval(site, field, ref, cfg)
    expected = (field.sum() - field.ravel()[site.idx].sum()) / ref["W0"]
    assert np.isclose(f1, expected)


def test_grid_resolution_sensitivity_for_synthetic_sprinkler_integral():
    """Quantify raster integral error without assuming monotonic convergence."""
    lawn = np.asarray([(-4, -4), (4, -4), (4, 4), (-4, 4)], dtype=float)
    radius = 2.07
    head_x, head_y = 0.11, 0.27  # deliberately offset from every tested grid origin
    # For a unit relative field inside a full-circle throw, exact integral is pi*r^2.
    exact = np.pi * radius**2
    integrals = {}
    for cell in (0.5, 0.25, 0.125):
        cfg = dict(sim.CFG, cell=cell, margin=0.0)
        site = sim.Site(lawn, cfg)
        field = site.total([(head_x, head_y, radius, 0.0, 360.0)])
        integrals[cell] = float(field.sum() * cell**2)

    errors = {cell: abs(value - exact) for cell, value in integrals.items()}
    # A finer grid can plateau or briefly worsen due to centre classification;
    # the practical check is bounded error on this fixed non-aligned fixture.
    assert errors[0.125] / exact < 0.01
    assert len(set(integrals.values())) > 1


def test_grid_resolution_preserves_aligned_lawn_area():
    """For a grid-aligned rectangle, cell-centre rasterization preserves area."""
    lawn = np.asarray([(0, 0), (4, 0), (4, 3), (0, 3)], dtype=float)
    expected_area = 12.0
    for cell in (1.0, 0.5, 0.25):
        site = sim.Site(lawn, dict(sim.CFG, cell=cell, margin=1.0))
        assert np.isclose(site.area, expected_area)



def test_non_aligned_lawn_area_error_is_bounded_at_finest_tested_grid():
    """Quantify raster area sensitivity on a fixed non-grid-aligned lawn."""
    lawn = np.asarray([
        (0.13, 0.21), (4.27, 0.21), (4.27, 3.38),
        (2.12, 4.17), (0.13, 3.38),
    ], dtype=float)
    x, y = lawn.T
    exact_area = abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2
    raster_areas = {}
    for cell in (1.0, 0.5, 0.25, 0.125):
        site = sim.Site(lawn, dict(sim.CFG, cell=cell, margin=1.0))
        raster_areas[cell] = site.area

    errors = {cell: abs(area - exact_area) for cell, area in raster_areas.items()}
    # The sequence is intentionally not required to be monotonic: centre-sampled
    # rasterization can alias boundaries at intermediate resolutions.
    assert errors[0.125] / exact_area < 0.01
    assert len(set(raster_areas.values())) > 1
