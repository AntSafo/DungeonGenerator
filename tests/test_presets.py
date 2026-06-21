"""Tests for room-size presets and the placement grid."""

import pytest

from generator.presets import GRID_CELLS, ROOM_PRESETS, get_preset


def test_four_presets():
    assert set(ROOM_PRESETS) == {"small", "medium", "large", "grand"}


@pytest.mark.parametrize("name", list(ROOM_PRESETS))
def test_cell_sizes_are_even_and_divide_room(name):
    p = ROOM_PRESETS[name]
    assert p.grid.cells == GRID_CELLS
    assert p.grid.cell_d * GRID_CELLS == p.bounds.d
    assert p.grid.cell_w * GRID_CELLS == p.bounds.w
    # Even cell sizes guarantee integer cell centers (the divisible-by-8 invariant).
    assert p.grid.cell_d % 2 == 0
    assert p.grid.cell_w % 2 == 0


def test_expected_dimensions():
    assert get_preset("small").bounds.d == 400 and get_preset("small").bounds.w == 200
    assert get_preset("grand").bounds.w == 648 and get_preset("grand").bounds.h == 340


@pytest.mark.parametrize("name", list(ROOM_PRESETS))
def test_all_cell_centers_are_integers_and_in_bounds(name):
    p = ROOM_PRESETS[name]
    for ix in range(GRID_CELLS):
        for iy in range(GRID_CELLS):
            cx, cy = p.grid.cell_center(ix, iy)
            assert isinstance(cx, int) and isinstance(cy, int)
            assert 0 < cx < p.bounds.d and 0 < cy < p.bounds.w


def test_small_cell_centers_values():
    g = get_preset("small").grid  # cell_d=100, cell_w=50
    assert g.cell_center(0, 0) == (50, 25)
    assert g.cell_center(3, 3) == (350, 175)


def test_cell_out_of_range_raises():
    g = get_preset("small").grid
    with pytest.raises(IndexError):
        g.cell_center(4, 0)


def test_get_unknown_preset_raises():
    with pytest.raises(KeyError):
        get_preset("colossal")
