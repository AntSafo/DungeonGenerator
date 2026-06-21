"""Step 3 — one-shot layout (manual-testing variant).

Instead of the live tool-use loop (layout_agent.run_layout), this asks the model to emit
ALL placements at once as a JSON array of place_object arguments. We then run them through
the deterministic PlacementSession and render. Useful for testing the layout reasoning +
renderer by hand, without the API. The trade-off: no per-step collision feedback (the
engine still nudges overlaps, just without the model correcting).
"""

from __future__ import annotations

from generator.engine import Placed
from generator.layout_agent import build_room_prompt
from generator.placement_tool import PlacementSession
from generator.presets import Preset
from generator.prompts import load_prompt
from generator.reference_data import MOUNT_HEIGHTS, REFERENCE_LADDER

__all__ = ["build_system_prompt", "build_room_prompt", "apply_placements"]


def build_system_prompt() -> str:
    ladder = "\n".join(f"  - {name}: {size}" for name, size in REFERENCE_LADDER)
    mounts = "\n".join(f"  - {kind}: center ~{cm} cm" for kind, cm in MOUNT_HEIGHTS.items())
    return load_prompt("step3_layout_oneshot_system", REFERENCE_LADDER=ladder, MOUNT_HEIGHTS=mounts)


def apply_placements(preset: Preset, placements: list[dict]) -> tuple[list[Placed], list[dict]]:
    """Run a list of place_object arg dicts through a session; return (regions, feedbacks)."""
    session = PlacementSession(preset)
    feedbacks = [session.place(p) for p in placements]
    return session.layout(), feedbacks
