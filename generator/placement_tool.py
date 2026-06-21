"""The `place_object` tool: a stateful session plus the Anthropic tool schema.

`PlacementSession` turns ONE model-issued placement instruction into a concrete
Region — resolving relational xy (grid / against_wall / beside / centered_on) and
anchor z (floor / wall / ceiling / on), running the deterministic collision nudge,
and recording it. It returns structured feedback the model reacts to. Calling
`place` again for an already-placed `object_id` moves it (supports restructuring).

No LLM here — generator/layout_agent.py drives this with Claude.
"""

from __future__ import annotations

import math
from typing import Optional

from generator.engine import Placed, apply_merges, resolve_collision
from generator.geometry import CircleFootprint, RectFootprint, Region
from generator.placement import (
    z_extent_ceiling,
    z_extent_floor,
    z_extent_on,
    z_extent_wall,
)
from generator.presets import Preset

WALLS = ("back", "front", "left", "right")
SIDES = ("left", "right", "front", "back")


class PlacementError(ValueError):
    """A malformed or unsatisfiable placement instruction (surfaced to the model)."""


def _arg_half_d(a: dict) -> float:
    return a["d"] / 2 if a["shape"] == "rect" else a["r"]


def _arg_half_w(a: dict) -> float:
    return a["w"] / 2 if a["shape"] == "rect" else a["r"]


def _fp_half_d(fp) -> float:
    return fp.d / 2 if isinstance(fp, RectFootprint) else fp.r


def _fp_half_w(fp) -> float:
    return fp.w / 2 if isinstance(fp, RectFootprint) else fp.r


class PlacementSession:
    def __init__(self, preset: Preset):
        self.preset = preset
        self.bounds = preset.bounds
        self.grid = preset.grid
        self.placed: list[Placed] = []
        self.by_id: dict[str, Placed] = {}

    # --- internals -----------------------------------------------------------

    def _target(self, oid: Optional[str]) -> Placed:
        if not oid:
            raise PlacementError("a relational placement needs a 'target'/'support' object id")
        if oid not in self.by_id:
            raise PlacementError(f"target '{oid}' is not placed yet; place it first")
        return self.by_id[oid]

    def _make_footprint(self, a: dict, cx: int, cy: int):
        shape = a.get("shape")
        if shape == "rect":
            return RectFootprint(cx, cy, a["d"], a["w"])
        if shape == "circle":
            return CircleFootprint(cx, cy, a["r"])
        raise PlacementError(f"shape must be 'rect' or 'circle', got {shape!r}")

    def _resolve_xy(self, a: dict) -> tuple[int, int]:
        mode = a.get("xy_mode")
        if mode == "grid":
            ix, iy = a["cell"]
            dx, dy = a.get("offset", [0, 0])
            cx, cy = self.grid.cell_center(ix, iy)
            return cx + dx, cy + dy
        if mode == "against_wall":
            wall, along = a["wall"], a["along"]
            hd, hw = math.ceil(_arg_half_d(a)), math.ceil(_arg_half_w(a))
            if wall == "back":
                return hd, along
            if wall == "front":
                return self.bounds.d - hd, along
            if wall == "left":
                return along, hw
            if wall == "right":
                return along, self.bounds.w - hw
            raise PlacementError(f"wall must be one of {WALLS}")
        if mode == "centered_on":
            t = self._target(a.get("target"))
            dx, dy = a.get("offset", [0, 0])
            return t.region.footprint.cx + dx, t.region.footprint.cy + dy
        if mode == "beside":
            t = self._target(a.get("target"))
            side = a.get("side")
            gap, slide = a.get("gap", 0), a.get("slide", 0)
            tfp = t.region.footprint
            hd, hw = _arg_half_d(a), _arg_half_w(a)
            thd, thw = _fp_half_d(tfp), _fp_half_w(tfp)
            if side == "right":
                return tfp.cx + slide, round(tfp.cy + thw + gap + hw)
            if side == "left":
                return tfp.cx + slide, round(tfp.cy - thw - gap - hw)
            if side == "front":
                return round(tfp.cx + thd + gap + hd), tfp.cy + slide
            if side == "back":
                return round(tfp.cx - thd - gap - hd), tfp.cy + slide
            raise PlacementError(f"side must be one of {SIDES}")
        raise PlacementError("xy_mode must be grid | against_wall | beside | centered_on")

    def _resolve_z(self, a: dict, height: int):
        za = a.get("z_anchor", "floor")
        if za == "floor":
            return z_extent_floor(height)
        if za == "wall":
            mc = a.get("mount_center")
            if mc is None:
                raise PlacementError("z_anchor 'wall' needs 'mount_center'")
            return z_extent_wall(mc, height)
        if za == "ceiling":
            return z_extent_ceiling(self.bounds.h, height)
        if za == "on":
            return z_extent_on(self._target(a.get("support")).region.z.hi, height)
        raise PlacementError("z_anchor must be floor | wall | ceiling | on")

    def _summary(self) -> list[str]:
        return [p.object_id for p in self.placed]

    # --- public API ----------------------------------------------------------

    def place(self, args: dict) -> dict:
        """Resolve and record one placement. Returns a feedback dict for the model."""
        oid = args.get("object_id")
        try:
            if not oid:
                raise PlacementError("object_id is required")
            height = args["height"]
            cx, cy = self._resolve_xy(args)
            z = self._resolve_z(args, height)
            footprint = self._make_footprint(args, cx, cy)
            region = Region(footprint, z)
            no_collide = args.get("role") == "floorCovering"
            group_id = args.get("group_id")

            self._remove(oid)  # re-placing an existing id moves it
            resolved = resolve_collision(region, self.placed, self.bounds, no_collide, group_id)
            if resolved is None:
                return {
                    "status": "error",
                    "object_id": oid,
                    "reason": "no non-colliding, in-bounds position found near the requested spot; "
                              "try a different location, a smaller size, or move an earlier object",
                    "placed_so_far": self._summary(),
                }

            p = Placed(oid, resolved, no_collide, group_id)
            self.placed.append(p)
            self.by_id[oid] = p
            rfp = resolved.footprint
            return {
                "status": "placed",
                "object_id": oid,
                "center": [rfp.cx, rfp.cy],
                "z": [resolved.z.lo, resolved.z.hi],
                "nudged": (rfp.cx, rfp.cy) != (cx, cy),
                "placed_count": len(self.placed),
            }
        except PlacementError as e:
            return {"status": "error", "object_id": oid, "reason": str(e)}
        except (KeyError, TypeError, ValueError) as e:
            return {"status": "error", "object_id": oid, "reason": f"invalid arguments: {e}"}

    def _remove(self, oid: str) -> None:
        if oid in self.by_id:
            self.placed.remove(self.by_id.pop(oid))

    def layout(self) -> list[Placed]:
        """Finalize: merge overlapping groupable members into composite regions."""
        return apply_merges(self.placed)


# --- Anthropic tool schema ---------------------------------------------------

PLACE_OBJECT_TOOL = {
    "name": "place_object",
    "description": (
        "Place one object into the room (or re-place an already-placed object to move it). "
        "Specify the footprint, height, an xy position mode, and a z anchor. "
        "Returns where it ended up, whether it had to be nudged to avoid a collision, or an "
        "error to react to. Re-call with the same object_id to reposition it."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "object_id": {"type": "string", "description": "stable id from the room (e.g. obj_03)"},
            "shape": {"type": "string", "enum": ["rect", "circle"]},
            "d": {"type": "integer", "description": "rect depth = extent along x (cm)"},
            "w": {"type": "integer", "description": "rect width = extent along y (cm)"},
            "r": {"type": "integer", "description": "circle radius (cm)"},
            "height": {"type": "integer", "description": "object height = extent along z (cm)"},
            "xy_mode": {
                "type": "string",
                "enum": ["grid", "against_wall", "beside", "centered_on"],
                "description": "grid: cell+offset; against_wall: flush to a wall at 'along'; "
                               "beside: next to 'target' on a 'side'; centered_on: centered over 'target'",
            },
            "cell": {"type": "array", "items": {"type": "integer"},
                     "description": "[ix, iy], each 0-3 (grid mode)"},
            "offset": {"type": "array", "items": {"type": "integer"},
                       "description": "[dx, dy] cm nudge (grid / centered_on)"},
            "wall": {"type": "string", "enum": list(WALLS), "description": "against_wall mode"},
            "along": {"type": "integer", "description": "position along the wall in cm (against_wall)"},
            "target": {"type": "string", "description": "object_id to position relative to (beside / centered_on)"},
            "side": {"type": "string", "enum": list(SIDES), "description": "which side of target (beside)"},
            "gap": {"type": "integer", "description": "cm gap from target (beside)"},
            "slide": {"type": "integer", "description": "cm slide along the free axis (beside)"},
            "z_anchor": {"type": "string", "enum": ["floor", "wall", "ceiling", "on"]},
            "mount_center": {"type": "integer", "description": "z center for z_anchor 'wall' (cm)"},
            "support": {"type": "string", "description": "object_id this rests on (z_anchor 'on')"},
            "role": {"type": "string", "enum": ["floorCovering"],
                     "description": "set for rugs/carpets: marks no-collide underlay"},
            "group_id": {"type": "string", "description": "groupable-set id; members may overlap and will merge"},
        },
        "required": ["object_id", "shape", "height", "xy_mode", "z_anchor"],
    },
}
