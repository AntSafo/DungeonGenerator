"""Deterministic placement helpers for step 3.

Pure functions the (later) layout engine will call: anchor -> vertical extent,
cell + offset -> object center, and the role-layer placement ordering. No LLM here.
See docs/step3-spatial-layout-design.md and docs/room-presets-and-reference-sizes.md.
"""

from __future__ import annotations

import heapq

from generator.geometry import Interval
from generator.presets import Grid
from generator.schema import Room

# --- anchor -> vertical extent ----------------------------------------------
# Each returns the object's [z_bottom, z_top] for a given object height.

def z_extent_floor(height: int) -> Interval:
    """Object standing on the floor."""
    return Interval(0, height)


def z_extent_on(support_top: int, height: int) -> Interval:
    """Object resting on a surface (z_bottom = the support's z_top)."""
    return Interval(support_top, support_top + height)


def z_extent_ceiling(room_height: int, height: int) -> Interval:
    """Object hung flush to the ceiling, extending downward by its height.

    (A larger drop can be modeled later by folding chain length into `height`.)
    """
    return Interval(room_height - height, room_height)


def z_extent_wall(mount_center: int, height: int) -> Interval:
    """Wall-mounted object centered near `mount_center` (reference height + offset).

    z_top - z_bottom is exactly `height`; the center is approximate for odd heights.
    """
    z_bottom = mount_center - height // 2
    return Interval(z_bottom, z_bottom + height)


# --- cell + offset -> center -------------------------------------------------

def object_center(grid: Grid, ix: int, iy: int, dx: int = 0, dy: int = 0) -> tuple[int, int]:
    """Center of an object: the chosen cell center plus a per-axis discrete offset."""
    cx, cy = grid.cell_center(ix, iy)
    return cx + dx, cy + dy


# --- role-layer placement ordering ------------------------------------------

# Locked role layers (lower = placed earlier). Floor coverings nominally go first,
# but dependencies (e.g. a rug placed `under` a table) override layer order via the
# topological sort below; coverings never collide, so a later order is safe.
LAYER_FLOOR_COVERING = 1
LAYER_FLOOR_ANCHOR = 2
LAYER_FLOOR_DEPENDENT = 3
LAYER_SURFACE = 4
LAYER_WALL = 5
LAYER_CEILING = 6


def classify_layer(role: str | None, relationship_types: set[str]) -> int:
    if role == "floorCovering":
        return LAYER_FLOOR_COVERING
    if "onCeiling" in relationship_types:
        return LAYER_CEILING
    if "onWall" in relationship_types:
        return LAYER_WALL
    if "support" in relationship_types:
        return LAYER_SURFACE
    if "adjacency" in relationship_types or "under" in relationship_types:
        return LAYER_FLOOR_DEPENDENT
    return LAYER_FLOOR_ANCHOR  # nearWall or no relationship -> a free-standing anchor


def placement_order(room: Room) -> list[str]:
    """Return object IDs in placement order.

    Hard constraint: an object is placed after every object it references (so anchors
    and supports exist first). Soft preference among ready objects: lower role layer,
    then original order. Raises ValueError on a dependency cycle.
    """
    objs = {o.id: o for o in room.objects}
    notes = {n.object_id: n for n in room.placement_notes}
    index = {o.id: i for i, o in enumerate(room.objects)}

    layer: dict[str, int] = {}
    deps: dict[str, set[str]] = {oid: set() for oid in objs}
    dependents: dict[str, set[str]] = {oid: set() for oid in objs}
    for oid, obj in objs.items():
        rels = notes[oid].relationships
        layer[oid] = classify_layer(obj.role, {r.type for r in rels})
        for r in rels:
            if r.target_id is not None:
                deps[oid].add(r.target_id)
                dependents[r.target_id].add(oid)

    indeg = {oid: len(deps[oid]) for oid in objs}
    ready = [(layer[oid], index[oid], oid) for oid in objs if indeg[oid] == 0]
    heapq.heapify(ready)

    order: list[str] = []
    while ready:
        _, _, oid = heapq.heappop(ready)
        order.append(oid)
        for dep in dependents[oid]:
            indeg[dep] -= 1
            if indeg[dep] == 0:
                heapq.heappush(ready, (layer[dep], index[dep], dep))

    if len(order) != len(objs):
        raise ValueError("cycle in placement relationships")
    return order
