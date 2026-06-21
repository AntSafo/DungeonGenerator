"""Tests for the step-2 creative-pass prompt builders (no API)."""

import json

from generator.creative_agent import build_system_prompt, build_user_prompt


def test_system_prompt_covers_the_contract():
    sp = build_system_prompt()
    for token in ["sizePreset", "arrangementProse", "placementNotes", "floorCovering",
                  "groupableSets", "front wall", "onCeiling", "schemaVersion",
                  "requiredItems", "FULLNESS"]:
        assert token in sp
    for rel in ["adjacency", "support", "under", "nearWall", "onWall", "onCeiling"]:
        assert rel in sp
    for preset in ["small", "medium", "large", "grand"]:
        assert preset in sp


def test_user_prompt_embeds_input_as_json():
    prompt = build_user_prompt("a vast medieval castle",
                               required_items=["a treasure chest", "a throne"],
                               room_type="throne room", tone="grand but decaying")
    payload = json.loads(prompt[prompt.index("{"):])
    assert payload["location"] == "a vast medieval castle"
    assert payload["roomType"] == "throne room"
    assert payload["tone"] == "grand but decaying"
    assert "a throne" in payload["requiredItems"]


def test_user_prompt_omits_optional_fields():
    payload = json.loads(build_user_prompt("a damp sea cave")[build_user_prompt("a damp sea cave").index("{"):])
    assert payload == {"location": "a damp sea cave"}
