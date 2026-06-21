"""Tests for geometry primitives, using tiny ad-hoc setups (no full room designs)."""

import pytest

from generator.geometry import (
    CircleFootprint,
    Interval,
    RectFootprint,
    Region,
    RoomBounds,
    footprint_within,
    footprints_overlap,
    region_within_bounds,
    regions_overlap,
)


# --- Interval ---------------------------------------------------------------

def test_interval_touching_is_not_overlap():
    # A cup's [75, 85] resting on a table's [0, 75] only touch at 75.
    assert not Interval(0, 75).overlaps(Interval(75, 85))


def test_interval_real_overlap():
    assert Interval(0, 75).overlaps(Interval(70, 85))


def test_interval_contains():
    assert Interval(0, 100).contains(Interval(10, 90))
    assert not Interval(0, 100).contains(Interval(10, 110))


def test_interval_rejects_inverted():
    with pytest.raises(ValueError):
        Interval(50, 10)


# --- footprint overlap ------------------------------------------------------

def test_rects_flush_side_by_side_do_not_overlap():
    a = RectFootprint(cx=100, cy=100, d=100, w=100)  # x in [50, 150]
    b = RectFootprint(cx=200, cy=100, d=100, w=100)  # x in [150, 250]
    assert not footprints_overlap(a, b)


def test_rects_overlapping():
    a = RectFootprint(cx=100, cy=100, d=100, w=100)
    b = RectFootprint(cx=190, cy=100, d=100, w=100)  # x in [140, 240], overlaps [50,150]
    assert footprints_overlap(a, b)


def test_circles_touch_then_overlap_then_apart():
    a = CircleFootprint(cx=0, cy=0, r=10)
    assert footprints_overlap(a, CircleFootprint(cx=15, cy=0, r=10))      # distance 15 < 20
    assert not footprints_overlap(a, CircleFootprint(cx=20, cy=0, r=10))  # distance 20 == 20 (touch)
    assert not footprints_overlap(a, CircleFootprint(cx=21, cy=0, r=10))  # apart


def test_rect_circle_overlap_uses_nearest_edge():
    rect = RectFootprint(cx=0, cy=0, d=20, w=20)  # edges x,y in [-10, 10]
    # nearest edge is at x=10; circle center at x=15 -> gap 5
    assert not footprints_overlap(rect, CircleFootprint(cx=15, cy=0, r=4))  # 5 > 4
    assert footprints_overlap(rect, CircleFootprint(cx=15, cy=0, r=6))      # 5 < 6


def test_rect_circle_overlap_is_symmetric():
    rect = RectFootprint(cx=0, cy=0, d=20, w=20)
    circ = CircleFootprint(cx=15, cy=0, r=6)
    assert footprints_overlap(rect, circ) == footprints_overlap(circ, rect)


def test_odd_extents_stay_exact():
    # Odd depth (d=101) gives half-cm edges; the 2x math must still be exact.
    a = RectFootprint(cx=0, cy=0, d=101, w=100)   # x edges +/- 50.5
    b = RectFootprint(cx=101, cy=0, d=101, w=100)  # x edges 50.5..151.5 -> flush, no overlap
    assert not footprints_overlap(a, b)
    c = RectFootprint(cx=100, cy=0, d=101, w=100)  # one cm closer -> overlap
    assert footprints_overlap(a, c)


# --- 3D region overlap ------------------------------------------------------

def test_cup_resting_on_table_does_not_collide():
    table = Region(RectFootprint(cx=200, cy=200, d=120, w=120), Interval(0, 75))
    cup = Region(CircleFootprint(cx=210, cy=205, r=4), Interval(75, 85))  # sits on top
    assert footprints_overlap(table.footprint, cup.footprint)  # footprints do overlap
    assert not regions_overlap(table, cup)                     # but z only touches


def test_cup_sunk_into_table_collides():
    table = Region(RectFootprint(cx=200, cy=200, d=120, w=120), Interval(0, 75))
    cup = Region(CircleFootprint(cx=210, cy=205, r=4), Interval(70, 85))  # z overlaps table top
    assert regions_overlap(table, cup)


def test_stacked_footprints_apart_in_z_do_not_collide():
    a = Region(RectFootprint(cx=100, cy=100, d=50, w=50), Interval(0, 40))
    b = Region(RectFootprint(cx=100, cy=100, d=50, w=50), Interval(60, 100))
    assert not regions_overlap(a, b)


# --- bounds -----------------------------------------------------------------

BOUNDS = RoomBounds(d=400, w=300, h=250)


def test_footprint_within_bounds():
    assert footprint_within(RectFootprint(cx=200, cy=150, d=100, w=100), BOUNDS)
    assert footprint_within(CircleFootprint(cx=200, cy=150, r=50), BOUNDS)


def test_footprint_flush_against_wall_is_within():
    # Rect pushed flush to the far x wall (x_hi == 400).
    assert footprint_within(RectFootprint(cx=350, cy=150, d=100, w=100), BOUNDS)


def test_footprint_out_of_bounds():
    assert not footprint_within(RectFootprint(cx=380, cy=150, d=100, w=100), BOUNDS)  # x_hi 430
    assert not footprint_within(CircleFootprint(cx=390, cy=150, r=20), BOUNDS)        # x_hi 410


def test_region_z_within_bounds():
    fp = RectFootprint(cx=200, cy=150, d=100, w=100)
    assert region_within_bounds(Region(fp, Interval(0, 250)), BOUNDS)
    assert not region_within_bounds(Region(fp, Interval(0, 260)), BOUNDS)  # ceiling exceeded
