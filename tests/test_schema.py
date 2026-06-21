"""Tests for the room schema loader/validator against the hand-authored fixtures."""

import json
from pathlib import Path

import pytest

from generator.schema import SchemaError, WALL_NAMES, load_room, room_from_dict

FIXTURE_DIR = Path(__file__).parent / "fixtures"
# Room fixtures only — exclude layout/placement fixtures (not room.json documents).
FIXTURES = sorted(p for p in FIXTURE_DIR.glob("*.json") if "placements" not in p.stem)


def test_all_fixtures_present():
    assert len(FIXTURES) == 6


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_loads_and_validates(path):
    room = load_room(path)
    assert room.objects
    # Every object has exactly one placement note (the "all objects included" rule).
    assert {n.object_id for n in room.placement_notes} == room.object_ids
    # Per-wall surfaces present.
    assert set(room.surfaces.walls) == set(WALL_NAMES)


def _load_raw(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_scholars_study_merge_and_under():
    room = load_room(FIXTURE_DIR / "fixture-02-scholars-study.json")
    # One groupable set: round table + 4 chairs.
    assert len(room.groupable_sets) == 1
    assert len(room.groupable_sets[0].member_ids) == 5
    # The rug uses `under` targeting the table (obj_01).
    rug_note = next(n for n in room.placement_notes if n.object_id == "obj_10")
    assert ("under", "obj_01") in [(r.type, r.target_id) for r in rug_note.relationships]


def test_wardens_cell_support_and_covering():
    room = load_room(FIXTURE_DIR / "fixture-01-wardens-cell.json")
    # Lamp (obj_03) is supported by the nightstand (obj_02).
    lamp = next(n for n in room.placement_notes if n.object_id == "obj_03")
    assert ("support", "obj_02") in [(r.type, r.target_id) for r in lamp.relationships]
    # The rug is a floor covering.
    rug = next(o for o in room.objects if o.id == "obj_04")
    assert rug.role == "floorCovering"


def test_object_target_relationship_with_null_rejected():
    data = _load_raw("fixture-01-wardens-cell.json")
    # `support` requires an object target; null must fail.
    data["placementNotes"][2]["relationships"] = [{"type": "support", "targetId": None}]
    with pytest.raises(SchemaError):
        room_from_dict(data)


def test_structure_relationship_with_target_rejected():
    data = _load_raw("fixture-01-wardens-cell.json")
    # `onWall` must have a null target; giving it an object must fail.
    data["placementNotes"][0]["relationships"] = [{"type": "onWall", "targetId": "obj_02"}]
    with pytest.raises(SchemaError):
        room_from_dict(data)


def test_missing_wall_rejected():
    data = _load_raw("fixture-02-scholars-study.json")
    del data["surfaces"]["walls"]["front"]
    with pytest.raises(SchemaError):
        room_from_dict(data)


def test_object_without_placement_note_rejected():
    data = _load_raw("fixture-01-wardens-cell.json")
    data["placementNotes"] = data["placementNotes"][:-1]  # drop one note
    with pytest.raises(SchemaError):
        room_from_dict(data)


def test_bad_groupable_member_rejected():
    data = _load_raw("fixture-02-scholars-study.json")
    data["groupableSets"][0]["memberIds"].append("obj_999")
    with pytest.raises(SchemaError):
        room_from_dict(data)
