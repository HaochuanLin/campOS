import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campos.campos_sim import load_polygon_csv, polygons_overlap  # noqa: E402


def write_polygon(path: Path, points):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x_m", "y_m"])
        writer.writerows(points)
    return path


def test_polygon_loader_accepts_optional_closing_vertex(tmp_path):
    polygon = write_polygon(
        tmp_path / "closed.csv",
        [(0, 0), (4, 0), (4, 3), (0, 3), (0, 0)],
    )
    loaded = load_polygon_csv(polygon)
    assert loaded.shape == (4, 2)


def test_polygon_loader_rejects_self_intersection(tmp_path):
    polygon = write_polygon(
        tmp_path / "bowtie.csv",
        [(0, 0), (4, 4), (0, 3), (3, 0)],
    )
    with pytest.raises(ValueError, match="self-intersecting"):
        load_polygon_csv(polygon)


def test_adjacent_lawn_and_sidewalk_can_share_a_boundary():
    lawn = [(0, 0), (4, 0), (4, 3), (0, 3)]
    sidewalk = [(4, 0), (6, 0), (6, 3), (4, 3)]
    assert polygons_overlap(lawn, sidewalk) is False


@pytest.mark.parametrize(
    "protected",
    [
        [(3, 1), (5, 1), (5, 4), (3, 4)],  # positive-area intersection
        [(0, 0), (4, 0), (4, 3), (0, 3)],  # identical polygon
    ],
)
def test_protected_surface_rejects_positive_area_overlap(protected):
    lawn = [(0, 0), (4, 0), (4, 3), (0, 3)]
    assert polygons_overlap(lawn, protected) is True


def test_checked_in_example_polygons_are_valid_and_share_only_a_boundary():
    templates = ROOT / "data" / "templates"
    lawn = load_polygon_csv(templates / "site_polygon_template.csv")
    protected = load_polygon_csv(templates / "protected_surface_template.csv")
    assert polygons_overlap(lawn, protected) is False
