"""Tests for the prompt loader and the step-3 one-shot layout helpers."""

import pytest

from generator.layout_oneshot import apply_placements, build_system_prompt
from generator.presets import get_preset
from generator.prompts import load_prompt


def test_loader_errors_on_unfilled_placeholder():
    with pytest.raises(ValueError):
        load_prompt("step3_layout_oneshot_system")  # template needs substitutions


def test_step2_prompt_file_has_no_sentinels():
    assert "{{" not in load_prompt("step2_creative_system")


def test_oneshot_prompt_substituted_and_complete():
    sp = build_system_prompt()
    assert "{{" not in sp
    assert "55-gallon steel drum" in sp           # reference ladder substituted
    assert "painting / portrait" in sp            # mount heights substituted
    for token in ["xy_mode", "z_anchor", "against_wall", "JSON array", "floorCovering"]:
        assert token in sp


def test_apply_placements_runs_through_session():
    placed, feedbacks = apply_placements(get_preset("medium"), [
        {"object_id": "table", "shape": "rect", "d": 120, "w": 120, "height": 75,
         "xy_mode": "grid", "cell": [1, 1], "z_anchor": "floor"},
        {"object_id": "cup", "shape": "circle", "r": 5, "height": 12,
         "xy_mode": "centered_on", "target": "table", "offset": [10, 0],
         "z_anchor": "on", "support": "table"},
    ])
    assert all(f["status"] == "placed" for f in feedbacks)
    assert len(placed) == 2
