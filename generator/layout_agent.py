"""Claude-driven spatial layout (step 3, phase 5).

Builds the system + room prompts, then runs a manual tool-use loop where Claude calls
`place_object` and the deterministic PlacementSession resolves each call. Uses
claude-opus-4-8 with adaptive thinking. The API key is read from the environment
(ANTHROPIC_API_KEY, loaded from .env) - never hardcoded.

`run_layout` performs the actual API calls; it is intentionally NOT exercised by tests
(to avoid spending tokens). The prompt builders and the tool/session are unit-tested.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from generator.placement_tool import PLACE_OBJECT_TOOL, PlacementSession
from generator.presets import get_preset
from generator.reference_data import MOUNT_HEIGHTS, REFERENCE_LADDER
from generator.schema import Room

MODEL = "claude-opus-4-8"


def build_system_prompt() -> str:
    ladder = "\n".join(f"  - {name}: {size}" for name, size in REFERENCE_LADDER)
    mounts = "\n".join(f"  - {k}: center ~{v} cm" for k, v in MOUNT_HEIGHTS.items())
    return f"""You are a spatial layout designer for a dungeon-room generator. You place each
object of one room into a 3D coordinate system by calling the `place_object` tool, one
object per call, reacting to the feedback it returns.

COORDINATE SYSTEM (all integer centimeters):
- Origin is the back-left floor corner. +x points toward the viewer (depth), +y points
  right (width), +z points up (height). The camera sits near the front (max x) at eye
  height and looks toward the back wall at x=0. Keep the floor near the front wall
  (the entry/camera) clear of large objects so they don't block the view.
- Each object is a box (rect footprint) or cylinder (circle footprint) plus a height.

GRID: the floor is a 4x4 grid (cells indexed 0-3 on each axis). For free-standing
placement, pick a cell and a per-axis cm offset. ALWAYS vary the offset so rooms don't
look like everything snapped to grid centers.

SIZING - reference yardsticks (do NOT copy these as object sizes; they are a measuring
stick). Size each object RELATIVELY and with variety ("an ornate chest about chest-high
on a person, ~3 bricks deep"):
{ladder}

WALL-MOUNT reference center heights (apply a small vertical offset so heights vary):
{mounts}

PLACEMENT ORDER (place in this order; always place a relationship's target before the
object that references it):
  1. floor coverings (rugs) - pass role="floorCovering"
  2. large floor anchors (bed, table, dresser)
  3. smaller floor objects placed relative to anchors
  4. objects resting on surfaces
  5. wall-mounted objects
  6. ceiling-hung objects

MAPPING the room's placement-note relationships to tool calls:
- nearWall  -> xy_mode "against_wall" (wall + along), z_anchor "floor"
- onWall    -> xy_mode "against_wall", z_anchor "wall" with mount_center near the reference
- onCeiling -> xy_mode "grid"/"centered_on", z_anchor "ceiling"
- support   -> xy_mode "centered_on"/"grid" on the surface, z_anchor "on" (support = the surface id)
- adjacency -> xy_mode "beside" (target + side + gap, slide for variety)
- under (a covering centered under an object) -> xy_mode "centered_on", role="floorCovering"
- no relationship -> xy_mode "grid"

GROUPS: for objects in a groupable set, pass their group_id. Group members may overlap
(they will be merged into one region later) - don't fight overlaps between them.

REACTING TO FEEDBACK: if a call returns status "error" (e.g. it couldn't fit), try a
different cell/offset or size, OR re-call `place_object` for an EARLIER object to move it
and make room - then continue. Keep objects inside the room bounds.

Place every object exactly once (re-place only to fix problems). When all objects are
placed, end your turn with a one-line confirmation."""


def build_room_prompt(room: Room) -> str:
    preset = get_preset(room.size_preset)
    b = preset.bounds
    lines = [
        f"ROOM (preset '{room.size_preset}'): depth(x)={b.d}, width(y)={b.w}, ceiling(z)={b.h} cm. "
        f"4x4 grid: cells are {preset.grid.cell_d} deep x {preset.grid.cell_w} wide.",
        f"\nType: {room.identity.location_type}",
        f"Tone: {room.identity.tone}",
        f"Characteristics: {room.identity.characteristics}",
        "\nGroupable sets:",
    ]
    lines += [f"  - {g.id}: {', '.join(g.member_ids)}" for g in room.groupable_sets] or ["  (none)"]
    lines.append("\nArrangement:")
    lines.append(room.arrangement_prose)
    notes = {n.object_id: n for n in room.placement_notes}
    lines.append("\nObjects (place each one):")
    for o in room.objects:
        n = notes[o.id]
        rels = "; ".join(f"{r.type}->{r.target_id}" if r.target_id else r.type
                         for r in n.relationships) or "none"
        role = f" [role={o.role}]" if o.role else ""
        grp = f" [group={o.groupable_set_id}]" if o.groupable_set_id else ""
        lines.append(f"  {o.id}: {o.name}{role}{grp} - {o.description}")
        lines.append(f"      placement: {n.note}  (relationships: {rels})")
    return "\n".join(lines)


def run_layout(room: Room, client=None, max_turns: int = 60):
    """Drive Claude through the placement tool to lay out `room`. Returns placed regions.

    Makes live API calls - not covered by tests. Requires ANTHROPIC_API_KEY in the env.
    """
    import anthropic  # imported lazily so the tool/session can be tested without the SDK

    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") == "your-key-here":
        raise SystemExit("ANTHROPIC_API_KEY is not set - add your real key to .env")

    client = client or anthropic.Anthropic()
    session = PlacementSession(get_preset(room.size_preset))
    system = build_system_prompt()
    messages = [{"role": "user", "content": build_room_prompt(room)}]

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=system,
            tools=[PLACE_OBJECT_TOOL],
            messages=messages,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("layout request was refused")
        if response.stop_reason == "end_turn":
            break

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "place_object":
                feedback = session.place(block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(feedback),
                    "is_error": feedback.get("status") == "error",
                })
        if not results:
            break
        messages.append({"role": "user", "content": results})

    return session.layout()
