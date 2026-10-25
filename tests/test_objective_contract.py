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
