"""Step 5 — assemble the single image-generation prompt.

Combines the step-2 tonal/surface description with the step-3 layout: a deterministic
"view-relative placement summary" (where each object falls in the camera's frame) is
computed from the placed regions, then handed with the tone/surfaces/object descriptions
to the model, which writes one vivid image prompt. The geometry control image
(wireframe/depth) enforces shapes/positions; this text drives appearance.
"""

from __future__ import annotations

from dotenv import load_dotenv

from generator.engine import Placed
from generator.geometry import RoomBounds
from generator.presets import get_preset
from generator.prompts import load_prompt
from generator.render import camera_for, project
from generator.schema import Room

MODEL = "claude-opus-4-8"


def build_system_prompt() -> str:
    return load_prompt("step5_imageprompt_system")


def _placement_phrase(rel_types: set[str], region, support_name, px, dep_ratio, cam_w) -> str:
    horiz = "left" if px < cam_w / 3 else ("right" if px > 2 * cam_w / 3 else "center")
    depth = "foreground" if dep_ratio < 0.34 else ("background" if dep_ratio > 0.66 else "midground")
    if "onCeiling" in rel_types:
        return f"{horiz} of frame, hanging from the ceiling overhead"
    if "onWall" in rel_types:
        where = "the far wall" if depth == "background" else "a side wall"
        return f"{horiz} of {where}, mounted on the wall"
    if "support" in rel_types and support_name:
        return f"{horiz} {depth}, resting on the {support_name}"
    if region.z.hi - region.z.lo <= 4:
        return f"{horiz} {depth}, spread flat on the floor"
    return f"{horiz} {depth}, standing on the floor"


def build_view_summary(room: Room, placed: list[Placed], bounds: RoomBounds):
    """Return (object_id, name, description, placement_phrase) for every object, where the
    phrase says where the object falls in the camera's frame."""
    cam = camera_for(bounds)
    region_of = {}
    for p in placed:
        for oid in (p.member_ids or [p.object_id]):
            region_of[oid] = p.region
    notes = {n.object_id: n for n in room.placement_notes}
    name_of = {o.id: o.name for o in room.objects}

    summary = []
    for o in room.objects:
        region = region_of.get(o.id)
        if region is None:
            summary.append((o.id, o.name, o.description, "somewhere in the room"))
            continue
        fp = region.footprint
        cz = (region.z.lo + region.z.hi) / 2
        px, _ = project((fp.cx, fp.cy, cz), cam)
        dep_ratio = (cam.eye[0] - fp.cx) / cam.eye[0]
        rels = notes[o.id].relationships
        rel_types = {r.type for r in rels}
        support_name = next((name_of.get(r.target_id) for r in rels
                             if r.type == "support" and r.target_id), None)
        phrase = _placement_phrase(rel_types, region, support_name, px, dep_ratio, cam.width)
        summary.append((o.id, o.name, o.description, phrase))
    return summary


def build_user_prompt(room: Room, placed: list[Placed]) -> str:
    bounds = get_preset(room.size_preset).bounds
    s = room.surfaces
    lines = [
        f"TONE: {room.identity.tone}",
        f"LOCATION: {room.identity.location_type}",
        f"ATMOSPHERE: {room.identity.characteristics}",
        "",
        "SURFACES (the front wall is behind the viewer and not in frame):",
        f"  floor: {s.floor.material} - {s.floor.texture}",
        f"  ceiling: {s.ceiling.material} - {s.ceiling.texture}",
        f"  back wall: {s.walls['back'].material} - {s.walls['back'].texture}",
        f"  left wall: {s.walls['left'].material} - {s.walls['left'].texture}",
        f"  right wall: {s.walls['right'].material} - {s.walls['right'].texture}",
        "",
        "OBJECTS (appearance and where each sits in the view):",
    ]
    for _oid, name, desc, phrase in build_view_summary(room, placed, bounds):
        lines.append(f"  {name}: {desc}  [{phrase}]")
    return "\n".join(lines)


def run_imageprompt(room: Room, placed: list[Placed], client=None) -> str:
    """Live step-5 call -> the image prompt string. Not exercised by tests."""
    import anthropic

    load_dotenv()
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=build_system_prompt(),
        messages=[{"role": "user", "content": build_user_prompt(room, placed)}],
    )
    return next(b.text for b in response.content if b.type == "text").strip()
