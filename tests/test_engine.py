"""Tests for the placement engine, using tiny ad-hoc setups (no full rooms)."""

import pytest

from generator.engine import (
    Placed,
    PlacementSpec,
    apply_merges,
    merge_regions,
    place_all,
    resolve_collision,
)
from generator.geometry import (
    CircleFootprint,
    Interval,
    RectFootprint,
    Region,
    RoomBounds,
    regions_overlap,
)

BOUNDS = RoomBounds(d=400, w=400, h=300)


def _rect(cx, cy, d, w):
    return RectFootprint(cx, cy, d, w)


# --- collision resolution ---------------------------------------------------

def test_non_overlapping_objects_keep_position():
    a = PlacementSpec("a", _rect(100, 100, 40, 40), height=50, z_anchor="floor")
    b = PlacementSpec("b", _rect(300, 300, 40, 40), height=50, z_anchor="floor")
    placed = place_all([a, b], BOUNDS)
    centers = {p.object_id: (p.region.footprint.cx, p.region.footprint.cy) for p in placed}
    assert centers["a"] == (100, 100)
    assert centers["b"] == (300, 300)


def test_overlapping_objects_get_nudged_apart():
    a = PlacementSpec("a", _rect(200, 200, 80, 80), height=50, z_anchor="floor")
    b = PlacementSpec("b", _rect(210, 200, 80, 80), height=50, z_anchor="floor")  # overlaps a
    placed = place_all([a, b], BOUNDS)
    pa = next(p for p in placed if p.object_id == "a")
    pb = next(p for p in placed if p.object_id == "b")
    assert pa.region.footprint.cx == 200  # first object stays put
    assert not regions_overlap(pa.region, pb.region)  # second moved clear


def test_unplaceable_raises():
    tiny = RoomBounds(d=100, w=100, h=100)
    a = PlacementSpec("a", _rect(50, 50, 100, 100), height=50, z_anchor="floor")  # fills room
    b = PlacementSpec("b", _rect(50, 50, 100, 100), height=50, z_anchor="floor")
    with pytest.raises(ValueError):
        place_all([a, b], tiny)


# --- z anchors / stacking ---------------------------------------------------

def test_cup_on_table_stacks_without_collision():
    table = PlacementSpec("table", _rect(200, 200, 120, 120), height=75, z_anchor="floor")
    cup = PlacementSpec("cup", CircleFootprint(210, 205, 5), height=12,
                        z_anchor="on", support_id="table")
    placed = place_all([table, cup], BOUNDS)
    cup_p = next(p for p in placed if p.object_id == "cup")
    table_p = next(p for p in placed if p.object_id == "table")
    assert cup_p.region.z == Interval(75, 87)          # rests on the 75 cm table top
    assert not regions_overlap(table_p.region, cup_p.region)  # touch only, no collision
    assert (cup_p.region.footprint.cx, cup_p.region.footprint.cy) == (210, 205)  # not nudged


def test_wall_and_ceiling_anchors():
    painting = PlacementSpec("p", _rect(200, 5, 4, 50), height=70,
                             z_anchor="wall", mount_center=150)
    chandelier = PlacementSpec("c", CircleFootprint(200, 200, 30), height=50, z_anchor="ceiling")
    placed = place_all([painting, chandelier], BOUNDS)
    p = next(x for x in placed if x.object_id == "p")
    c = next(x for x in placed if x.object_id == "c")
    assert p.region.z == Interval(115, 185)
    assert c.region.z == Interval(250, 300)  # hung from the 300 cm ceiling


# --- coverings (no-collide) -------------------------------------------------

def test_covering_does_not_block_and_is_not_nudged():
    rug = PlacementSpec("rug", _rect(200, 200, 150, 100), height=2,
                        z_anchor="floor", no_collide=True)
    chest = PlacementSpec("chest", _rect(200, 200, 60, 40), height=45, z_anchor="floor")
    placed = place_all([rug, chest], BOUNDS)
    rug_p = next(p for p in placed if p.object_id == "rug")
    chest_p = next(p for p in placed if p.object_id == "chest")
    # The chest sits on the rug's footprint and is NOT nudged away.
    assert (chest_p.region.footprint.cx, chest_p.region.footprint.cy) == (200, 200)


# --- merge ------------------------------------------------------------------

def test_merge_regions_bounding_box():
    a = Region(_rect(100, 100, 40, 40), Interval(0, 75))   # x[80,120] y[80,120]
    b = Region(_rect(140, 100, 40, 40), Interval(0, 75))   # x[120,160] y[80,120]
    m = merge_regions([a, b])
    assert m.footprint == RectFootprint(cx=120, cy=100, d=80, w=40)
    assert m.z == Interval(0, 75)


def test_group_members_merge_into_one_region():
    # A round table + two overlapping chairs in one group.
    specs = [
        PlacementSpec("table", CircleFootprint(200, 200, 55), height=75, z_anchor="floor", group_id="g1"),
        PlacementSpec("chairL", _rect(150, 200, 45, 45), height=90, z_anchor="floor", group_id="g1"),
        PlacementSpec("chairR", _rect(250, 200, 45, 45), height=90, z_anchor="floor", group_id="g1"),
    ]
    placed = place_all(specs, BOUNDS)
    assert len(placed) == 1                       # collapsed to one composite
    comp = placed[0]
    assert comp.object_id == "g1"
    assert set(comp.member_ids) == {"table", "chairL", "chairR"}
    assert comp.region.z == Interval(0, 90)       # spans tallest member


def test_group_keeps_non_overlapping_member_separate():
    specs = [
        PlacementSpec("t", _rect(100, 100, 40, 40), height=75, z_anchor="floor", group_id="g1"),
        PlacementSpec("c", _rect(130, 100, 40, 40), height=90, z_anchor="floor", group_id="g1"),  # overlaps t
        PlacementSpec("far", _rect(350, 350, 40, 40), height=90, z_anchor="floor", group_id="g1"),  # alone
    ]
    placed = place_all(specs, BOUNDS)
    # One merged composite (t+c) plus the lone member.
    composites = [p for p in placed if p.member_ids]
    singles = [p for p in placed if not p.member_ids]
    assert len(composites) == 1 and set(composites[0].member_ids) == {"t", "c"}
    assert len(singles) == 1 and singles[0].object_id == "far"
