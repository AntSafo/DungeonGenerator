"""Room schema (the step-2 `room.json` slice) as typed Python structures.

This is the input contract for step 3 (spatial layout). See docs/room-schema.md.
`load_room` reads a `room.json`, parses it into these dataclasses, and validates
cross-references. Parsing maps the JSON's camelCase keys to snake_case fields.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Allowed enum-ish values (kept in sync with docs/room-schema.md).
SIZE_PRESETS = {"small", "medium", "large", "grand"}
OBJECT_ROLES = {"floorCovering"}  # None is also allowed (a normal object)
RELATIONSHIP_TYPES = {"adjacency", "support", "onWall", "onCeiling", "nearWall", "under"}
WALL_NAMES = ("back", "front", "left", "right")

# Relationship types whose target is another object vs. room structure (null target).
_OBJECT_TARGET_TYPES = {"adjacency", "support", "under"}
_NULL_TARGET_TYPES = {"onWall", "onCeiling", "nearWall"}


class SchemaError(ValueError):
    """Raised when a room dict is structurally invalid or fails validation."""


@dataclass(frozen=True)
class RoomInput:
    location: str
    room_type: str | None = None
    tone: str | None = None
    required_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class Identity:
    location_type: str
    characteristics: str
    tone: str


@dataclass(frozen=True)
class SurfaceFinish:
    material: str
    texture: str


@dataclass(frozen=True)
class Surfaces:
    floor: SurfaceFinish
    ceiling: SurfaceFinish
    walls: dict[str, SurfaceFinish]  # keyed by WALL_NAMES


@dataclass(frozen=True)
class RoomObject:
    id: str
    name: str
    description: str
    role: Optional[str] = None
    groupable_set_id: Optional[str] = None


@dataclass(frozen=True)
class GroupableSet:
    id: str
    member_ids: list[str]


@dataclass(frozen=True)
class Relationship:
    type: str
    target_id: Optional[str]  # None => relative to room structure (wall/ceiling/floor)


@dataclass(frozen=True)
class PlacementNote:
    object_id: str
    note: str
    relationships: list[Relationship]


@dataclass(frozen=True)
class Room:
    schema_version: int
    run_id: str
    input: RoomInput
    identity: Identity
    surfaces: Surfaces
    size_preset: str
    objects: list[RoomObject]
    groupable_sets: list[GroupableSet]
    arrangement_prose: str
    placement_notes: list[PlacementNote]

    @property
    def object_ids(self) -> set[str]:
        return {o.id for o in self.objects}


# --- parsing helpers ---------------------------------------------------------

def _req(d: dict, key: str, ctx: str):
    if not isinstance(d, dict):
        raise SchemaError(f"{ctx}: expected an object, got {type(d).__name__}")
    if key not in d:
        raise SchemaError(f"{ctx}: missing required key '{key}'")
    return d[key]


def _parse_surface_finish(d: dict, ctx: str) -> SurfaceFinish:
    return SurfaceFinish(material=str(_req(d, "material", ctx)),
                         texture=str(_req(d, "texture", ctx)))


def _parse_surfaces(d: dict, ctx: str) -> Surfaces:
    walls_d = _req(d, "walls", ctx)
    if not isinstance(walls_d, dict):
        raise SchemaError(f"{ctx}.walls: expected an object")
    walls = {w: _parse_surface_finish(_req(walls_d, w, f"{ctx}.walls"), f"{ctx}.walls.{w}")
             for w in WALL_NAMES}
    return Surfaces(
        floor=_parse_surface_finish(_req(d, "floor", ctx), f"{ctx}.floor"),
        ceiling=_parse_surface_finish(_req(d, "ceiling", ctx), f"{ctx}.ceiling"),
        walls=walls,
    )


def _parse_input(d: dict, ctx: str) -> RoomInput:
    # New shape is location-based; tolerate the legacy settingPrompt/keyLocations shape.
    location = d.get("location") or d.get("settingPrompt")
    if not location:
        raise SchemaError(f"{ctx}: missing required key 'location'")
    items = d.get("requiredItems") or []
    return RoomInput(
        location=str(location),
        room_type=(str(d["roomType"]) if d.get("roomType") else None),
        tone=(str(d["tone"]) if d.get("tone") else None),
        required_items=tuple(str(x) for x in items),
    )


def _parse_identity(d: dict, ctx: str) -> Identity:
    return Identity(location_type=str(_req(d, "locationType", ctx)),
                    characteristics=str(_req(d, "characteristics", ctx)),
                    tone=str(_req(d, "tone", ctx)))


def _parse_object(d: dict, ctx: str) -> RoomObject:
    role = d.get("role")
    grp = d.get("groupableSetId")
    return RoomObject(
        id=str(_req(d, "id", ctx)),
        name=str(_req(d, "name", ctx)),
        description=str(_req(d, "description", ctx)),
        role=None if role is None else str(role),
        groupable_set_id=None if grp is None else str(grp),
    )


def _parse_groupable_set(d: dict, ctx: str) -> GroupableSet:
    return GroupableSet(id=str(_req(d, "id", ctx)),
                        member_ids=[str(m) for m in _req(d, "memberIds", ctx)])


def _parse_relationship(d: dict, ctx: str) -> Relationship:
    target = d.get("targetId")
    return Relationship(type=str(_req(d, "type", ctx)),
                        target_id=None if target is None else str(target))


def _parse_placement_note(d: dict, ctx: str) -> PlacementNote:
    rels = _req(d, "relationships", ctx)
    return PlacementNote(
        object_id=str(_req(d, "objectId", ctx)),
        note=str(_req(d, "note", ctx)),
        relationships=[_parse_relationship(r, f"{ctx}.relationships[{i}]")
                       for i, r in enumerate(rels)],
    )


# --- public API --------------------------------------------------------------

def room_from_dict(d: dict) -> Room:
    """Parse and validate a room dict. Raises SchemaError on any problem."""
    ctx = "room"
    room = Room(
        schema_version=int(_req(d, "schemaVersion", ctx)),
        run_id=str(_req(d, "runId", ctx)),
        input=_parse_input(_req(d, "input", ctx), "room.input"),
        identity=_parse_identity(_req(d, "identity", ctx), "room.identity"),
        surfaces=_parse_surfaces(_req(d, "surfaces", ctx), "room.surfaces"),
        size_preset=str(_req(d, "sizePreset", ctx)),
        objects=[_parse_object(o, f"room.objects[{i}]")
                 for i, o in enumerate(_req(d, "objects", ctx))],
        groupable_sets=[_parse_groupable_set(g, f"room.groupableSets[{i}]")
                        for i, g in enumerate(_req(d, "groupableSets", ctx))],
        arrangement_prose=str(_req(d, "arrangementProse", ctx)),
        placement_notes=[_parse_placement_note(p, f"room.placementNotes[{i}]")
                         for i, p in enumerate(_req(d, "placementNotes", ctx))],
    )
    validate(room)
    return room


def validate(room: Room) -> None:
    """Check cross-references and enum values. Raises SchemaError on failure."""
    ids = [o.id for o in room.objects]
    id_set = set(ids)
    if len(ids) != len(id_set):
        raise SchemaError("duplicate object id(s)")
    if not ids:
        raise SchemaError("room has no objects")

    if room.size_preset not in SIZE_PRESETS:
        raise SchemaError(f"invalid sizePreset '{room.size_preset}'")

    set_ids = {g.id for g in room.groupable_sets}
    if len(set_ids) != len(room.groupable_sets):
        raise SchemaError("duplicate groupableSet id(s)")

    for o in room.objects:
        if o.role is not None and o.role not in OBJECT_ROLES:
            raise SchemaError(f"object {o.id}: invalid role '{o.role}'")
        if o.groupable_set_id is not None and o.groupable_set_id not in set_ids:
            raise SchemaError(f"object {o.id}: groupableSetId '{o.groupable_set_id}' not found")

    for g in room.groupable_sets:
        for m in g.member_ids:
            if m not in id_set:
                raise SchemaError(f"groupableSet {g.id}: member '{m}' is not an object")

    noted = [n.object_id for n in room.placement_notes]
    if len(noted) != len(set(noted)):
        raise SchemaError("duplicate placementNote object_id(s)")
    for n in room.placement_notes:
        if n.object_id not in id_set:
            raise SchemaError(f"placementNote references unknown object '{n.object_id}'")
        for rel in n.relationships:
            if rel.type not in RELATIONSHIP_TYPES:
                raise SchemaError(f"object {n.object_id}: invalid relationship type '{rel.type}'")
            if rel.type in _OBJECT_TARGET_TYPES:
                if rel.target_id is None or rel.target_id not in id_set:
                    raise SchemaError(
                        f"object {n.object_id}: relationship '{rel.type}' needs a valid object targetId")
            elif rel.type in _NULL_TARGET_TYPES:
                if rel.target_id is not None:
                    raise SchemaError(
                        f"object {n.object_id}: relationship '{rel.type}' must have a null targetId")

    missing = id_set - set(noted)
    if missing:
        raise SchemaError(f"objects without placement notes: {sorted(missing)}")


def load_room(path: str | Path) -> Room:
    """Load, parse, and validate a room.json file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return room_from_dict(data)
