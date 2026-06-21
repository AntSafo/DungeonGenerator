"""Tests for the step-5 image-prompt assembly (no API)."""

import json
from pathlib import Path

from generator.imageprompt import build_system_prompt, build_user_prompt, build_view_summary
from generator.layout_oneshot import apply_placements
from generator.presets import get_preset
from generator.schema import load_room

FX = Path(__file__).parent / "fixtures"


def _room_and_placed():
    room = load_room(FX / "fixture-04-drowned-tide-shrine.json")
    placements = json.loads((FX / "fixture-04-placements.json").read_text(encoding="utf-8"))
    placed, feedbacks = apply_placements(get_preset(room.size_preset), placements)
    return room, placed, feedbacks


def test_locked_layout_applies_cleanly():
    _, placed, feedbacks = _room_and_placed()
    assert all(f["status"] == "placed" for f in feedbacks)
    assert len(placed) == 11


def test_system_prompt_loads():
    sp = build_system_prompt()
    assert "{{" not in sp
    assert "image-generation prompt" in sp


def test_view_summary_places_objects_in_frame():
    room, placed, _ = _room_and_placed()
    bounds = get_preset(room.size_preset).bounds
    by_name = {name: phrase for _id, name, _desc, phrase in build_view_summary(room, placed, bounds)}
    assert "background" in by_name["Tide-Altar"]                       # far backdrop
    assert "mounted on the wall" in by_name["Relief of the Drowned Saint"]
    assert "hanging from the ceiling" in by_name["Tide-Censer"]
    assert "resting on the Tide-Altar" in by_name["Bronze Brine-Basin"]
    assert "flat on the floor" in by_name["Kelp Prayer-Mat"]


def test_user_prompt_includes_tone_and_every_object():
    room, placed, _ = _room_and_placed()
    up = build_user_prompt(room, placed)
    assert room.identity.tone in up
    for o in room.objects:
        assert o.name in up
