"""Tests for the place_object tool, driven by hand-made tool calls that mimic the model.

No Anthropic API calls — these exercise PlacementSession (the deterministic handler) and
the prompt builders directly.
"""

from pathlib import Path

from generator.geometry import Interval, regions_overlap
from generator.layout_agent import build_room_prompt, build_system_prompt
from generator.placement_tool import PLACE_OBJECT_TOOL, PlacementSession
from generator.presets import get_preset
from generator.schema import load_room

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _session(preset="medium"):
    return PlacementSession(get_preset(preset))


# --- xy modes ---------------------------------------------------------------

def test_grid_placement_uses_cell_center_plus_offset():
    s = _session("small")  # cell_d=100, cell_w=50 -> cell(0,0) center (50,25)
    fb = s.place({"object_id": "a", "shape": "rect", "d": 40, "w": 40, "height": 60,
                  "xy_mode": "grid", "cell": [0, 0], "offset": [10, -5], "z_anchor": "floor"})
    assert fb["status"] == "placed"
    assert fb["center"] == [60, 20]
    assert fb["z"] == [0, 60]
    assert fb["nudged"] is False


def test_against_wall_is_flush_and_in_bounds():
    s = _session("small")  # depth 400
    fb = s.place({"object_id": "bed", "shape": "rect", "d": 200, "w": 100, "height": 60,
                  "xy_mode": "against_wall", "wall": "back", "along": 100, "z_anchor": "floor"})
    assert fb["status"] == "placed"
    # Back wall is x=0; flush means the near edge sits at 0, so center x = depth/2 = 100.
    assert fb["center"] == [100, 100]


def test_beside_adjacency_offsets_and_does_not_collide():
    s = _session("medium")
    s.place({"object_id": "bed", "shape": "rect", "d": 200, "w": 140, "height": 60,
             "xy_mode": "against_wall", "wall": "left", "along": 180, "z_anchor": "floor"})
    fb = s.place({"object_id": "nightstand", "shape": "rect", "d": 40, "w": 45, "height": 55,
                  "xy_mode": "beside", "target": "bed", "side": "right", "gap": 5, "z_anchor": "floor"})
    assert fb["status"] == "placed"
    bed = s.by_id["bed"].region
    ns = s.by_id["nightstand"].region
    assert not regions_overlap(bed, ns)


def test_centered_on_under_rug_matches_target_center():
    s = _session("medium")
    s.place({"object_id": "table", "shape": "circle", "r": 55, "height": 75,
             "xy_mode": "grid", "cell": [1, 1], "offset": [0, 0], "z_anchor": "floor"})
    table_c = s.by_id["table"].region.footprint
    fb = s.place({"object_id": "rug", "shape": "rect", "d": 150, "w": 150, "height": 2,
                  "xy_mode": "centered_on", "target": "table", "offset": [0, 0],
                  "role": "floorCovering", "z_anchor": "floor"})
    assert fb["status"] == "placed"
    assert fb["center"] == [table_c.cx, table_c.cy]  # rug centered under the table


# --- z anchors --------------------------------------------------------------

def test_support_stacks_on_surface():
    s = _session("medium")
    s.place({"object_id": "table", "shape": "rect", "d": 120, "w": 120, "height": 75,
             "xy_mode": "grid", "cell": [1, 1], "z_anchor": "floor"})
    fb = s.place({"object_id": "cup", "shape": "circle", "r": 5, "height": 12,
                  "xy_mode": "centered_on", "target": "table", "offset": [20, 10],
                  "z_anchor": "on", "support": "table"})
    assert fb["status"] == "placed"
    assert fb["z"] == [75, 87]  # rests exactly on the 75 cm table top
    assert fb["nudged"] is False  # sitting on top is not a collision


def test_wall_mount_and_ceiling_anchors():
    s = _session("medium")  # ceiling 260
    p = s.place({"object_id": "painting", "shape": "rect", "d": 4, "w": 50, "height": 70,
                 "xy_mode": "against_wall", "wall": "back", "along": 180,
                 "z_anchor": "wall", "mount_center": 150})
    c = s.place({"object_id": "chandelier", "shape": "circle", "r": 30, "height": 50,
                 "xy_mode": "grid", "cell": [1, 1], "z_anchor": "ceiling"})
    assert p["z"] == [115, 185]
    assert c["z"] == [210, 260]  # hung from the 260 cm ceiling


# --- collision / restructuring ----------------------------------------------

def test_overlapping_second_object_is_nudged():
    s = _session("medium")
    s.place({"object_id": "a", "shape": "rect", "d": 80, "w": 80, "height": 50,
             "xy_mode": "grid", "cell": [1, 1], "z_anchor": "floor"})
    fb = s.place({"object_id": "b", "shape": "rect", "d": 80, "w": 80, "height": 50,
                  "xy_mode": "grid", "cell": [1, 1], "z_anchor": "floor"})  # same cell
    assert fb["status"] == "placed" and fb["nudged"] is True
    assert not regions_overlap(s.by_id["a"].region, s.by_id["b"].region)


def test_replacing_same_id_moves_it():
    s = _session("medium")
    s.place({"object_id": "a", "shape": "rect", "d": 40, "w": 40, "height": 50,
             "xy_mode": "grid", "cell": [0, 0], "z_anchor": "floor"})
    fb = s.place({"object_id": "a", "shape": "rect", "d": 40, "w": 40, "height": 50,
                  "xy_mode": "grid", "cell": [3, 3], "z_anchor": "floor"})
    assert fb["status"] == "placed"
    assert len(s.placed) == 1  # moved, not duplicated


def test_covering_does_not_block_object_on_top():
    s = _session("medium")
    s.place({"object_id": "rug", "shape": "rect", "d": 150, "w": 100, "height": 2,
             "xy_mode": "grid", "cell": [1, 1], "role": "floorCovering", "z_anchor": "floor"})
    rug_c = s.by_id["rug"].region.footprint
    fb = s.place({"object_id": "chest", "shape": "rect", "d": 60, "w": 40, "height": 45,
                  "xy_mode": "grid", "cell": [1, 1], "z_anchor": "floor"})
    assert fb["status"] == "placed" and fb["nudged"] is False  # sits on the rug, not nudged


# --- errors -----------------------------------------------------------------

def test_unknown_target_returns_error():
    s = _session("medium")
    fb = s.place({"object_id": "x", "shape": "rect", "d": 40, "w": 40, "height": 50,
                  "xy_mode": "beside", "target": "ghost", "side": "right", "z_anchor": "floor"})
    assert fb["status"] == "error" and "ghost" in fb["reason"]


def test_support_before_placement_errors():
    s = _session("medium")
    fb = s.place({"object_id": "cup", "shape": "circle", "r": 5, "height": 12,
                  "xy_mode": "grid", "cell": [1, 1], "z_anchor": "on", "support": "table"})
    assert fb["status"] == "error"


# --- group merge in finalized layout ----------------------------------------

def test_group_members_merge_in_layout():
    s = _session("medium")
    s.place({"object_id": "table", "shape": "circle", "r": 55, "height": 75,
             "xy_mode": "grid", "cell": [1, 1], "group_id": "g1", "z_anchor": "floor"})
    s.place({"object_id": "chair", "shape": "rect", "d": 45, "w": 45, "height": 90,
             "xy_mode": "beside", "target": "table", "side": "left", "gap": -20,
             "group_id": "g1", "z_anchor": "floor"})
    placed = s.layout()
    composites = [p for p in placed if p.member_ids]
    assert len(composites) == 1
    assert set(composites[0].member_ids) == {"table", "chair"}
    assert composites[0].region.z == Interval(0, 90)


# --- prompt builders (no API) -----------------------------------------------

def test_system_prompt_has_key_rules():
    sp = build_system_prompt()
    for token in ["place_object", "+x points toward the viewer", "floorCovering", "yardstick"]:
        assert token in sp


def test_room_prompt_lists_every_object():
    room = load_room(FIXTURE_DIR / "fixture-02-scholars-study.json")
    prompt = build_room_prompt(room)
    for o in room.objects:
        assert o.id in prompt
    assert "depth(x)=360" in prompt  # medium preset dimensions


def test_tool_schema_required_fields():
    req = PLACE_OBJECT_TOOL["input_schema"]["required"]
    assert set(req) == {"object_id", "shape", "height", "xy_mode", "z_anchor"}
