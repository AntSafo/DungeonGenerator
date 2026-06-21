"""Tests for placement helpers: anchor z-extents, cell+offset, role-layer ordering."""

from pathlib import Path

from generator.geometry import Interval
from generator.placement import (
    classify_layer,
    object_center,
    placement_order,
    z_extent_ceiling,
    z_extent_floor,
    z_extent_on,
    z_extent_wall,
)
from generator.presets import get_preset
from generator.schema import load_room

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# --- anchor -> z extent ------------------------------------------------------

def test_z_extent_floor():
    assert z_extent_floor(60) == Interval(0, 60)


def test_z_extent_on_surface():
    # A 12 cm goblet resting on a 75 cm table top.
    assert z_extent_on(75, 12) == Interval(75, 87)


def test_z_extent_ceiling():
    # A 50 cm chandelier hung from a 340 cm ceiling.
    assert z_extent_ceiling(340, 50) == Interval(290, 340)


def test_z_extent_wall_keeps_exact_height():
    assert z_extent_wall(150, 90) == Interval(105, 195)
    odd = z_extent_wall(170, 45)  # odd height -> still exactly 45 tall
    assert odd.hi - odd.lo == 45


# --- cell + offset -----------------------------------------------------------

def test_object_center_with_offset():
    g = get_preset("small").grid  # cell (0,0) center = (50, 25)
    assert object_center(g, 0, 0) == (50, 25)
    assert object_center(g, 0, 0, dx=10, dy=-5) == (60, 20)


# --- classify_layer ----------------------------------------------------------

def test_classify_layer_priorities():
    assert classify_layer("floorCovering", {"under"}) == 1   # role wins
    assert classify_layer(None, {"onCeiling"}) == 6
    assert classify_layer(None, {"onWall"}) == 5
    assert classify_layer(None, {"support"}) == 4
    assert classify_layer(None, {"adjacency"}) == 3
    assert classify_layer(None, {"nearWall"}) == 2
    assert classify_layer(None, set()) == 2


# --- placement_order on fixtures --------------------------------------------

def _order(name: str) -> list[str]:
    return placement_order(load_room(FIXTURE_DIR / name))


def test_order_supports_after_their_target():
    order = _order("fixture-01-wardens-cell.json")
    pos = {oid: i for i, oid in enumerate(order)}
    # cot before nightstand before lamp; chest after cot.
    assert pos["obj_01"] < pos["obj_02"] < pos["obj_03"]
    assert pos["obj_01"] < pos["obj_06"]


def test_order_under_rug_after_table_despite_layer():
    # The rug is layer 1, but `under` the table -> must come AFTER the table.
    order = _order("fixture-02-scholars-study.json")
    pos = {oid: i for i, oid in enumerate(order)}
    assert pos["obj_01"] < pos["obj_10"]          # table before rug
    assert pos["obj_01"] < pos["obj_02"]          # table before a chair
    assert pos["obj_01"] < pos["obj_06"]          # table before goblet (support)


def test_order_ceiling_hung_is_last():
    order = _order("fixture-03-ransacked-storeroom.json")
    pos = {oid: i for i, oid in enumerate(order)}
    assert pos["obj_01"] < pos["obj_02"]          # altar before idol (support)
    assert pos["obj_03"] < pos["obj_04"]          # first barrel before the one leaning on it
    assert order[-1] == "obj_08"                  # chandelier (onCeiling) placed last


def test_order_is_a_permutation_of_all_objects():
    for name in ["fixture-01-wardens-cell.json",
                 "fixture-02-scholars-study.json",
                 "fixture-03-ransacked-storeroom.json"]:
        room = load_room(FIXTURE_DIR / name)
        assert sorted(placement_order(room)) == sorted(o.id for o in room.objects)
