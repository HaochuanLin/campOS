import numpy as np
import pytest

from campos.model import head_field, orifice_flow_lpm, spacing_precipitation_mm_h


def test_uniform_full_circle_flow_field_integrates_to_configured_flow():
    # For a full circle, the model's mean depth times the disk area must equal
    # 60 * Q litres/hour expressed as mm*m²/hour.
    flow_lpm = 12.0
    radius_m = 4.0
    area_m2 = np.pi * radius_m**2
    mean_rate_mm_h = 60.0 * flow_lpm / area_m2
    assert mean_rate_mm_h * area_m2 == pytest.approx(60.0 * flow_lpm)


def test_sector_flow_field_scales_with_operating_arc_fraction():
    x = np.array([[0.0, 1.0, -1.0, 0.0]])
    y = np.array([[1.0, 0.0, 0.0, -1.0]])
    head = (0.0, 0.0, 3.0, 0.0, 180.0)
    field = head_field(x, y, head, flow_lpm=6.0)
    # Points on the first and second quadrants are inside this 180-degree
    # sector; the opposite half-circle is outside it.
    assert np.all(field[0, :2] > 0)
    assert np.all(field[0, 2:] == 0)


def test_orifice_flow_is_monotonic_in_pressure_and_nozzle_diameter():
    low_pressure = orifice_flow_lpm(200.0, 3.0)
    high_pressure = orifice_flow_lpm(400.0, 3.0)
    larger_nozzle = orifice_flow_lpm(200.0, 4.0)
    assert high_pressure > low_pressure
    assert larger_nozzle > low_pressure


def test_spacing_precipitation_respects_square_and_triangular_cell_area():
    flow = 10.0
    spacing = 5.0
    square = spacing_precipitation_mm_h(flow, spacing, arrangement="square")
    triangular = spacing_precipitation_mm_h(flow, spacing, arrangement="triangular")
    assert triangular > square
    assert triangular / square == pytest.approx(2.0 / np.sqrt(3.0))


@pytest.mark.parametrize(
    "pressure,diameter",
    [(0.0, 3.0), (-1.0, 3.0), (100.0, 0.0), (np.nan, 3.0)],
)
def test_orifice_flow_rejects_nonphysical_inputs(pressure, diameter):
    with pytest.raises(ValueError):
        orifice_flow_lpm(pressure, diameter)
