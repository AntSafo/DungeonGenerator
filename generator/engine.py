"""Deterministic placement engine (step 3, phase 4).

Takes per-object placement specs (the data the layout LLM will eventually produce),
walks them in order, builds each Region (footprint + anchor-derived z-extent),
resolves unintended collisions by nudging, and merges overlapping groupable members
into one bounding-box region. No LLM here.

See docs/step3-spatial-layout-design.md.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from generator.geometry import (
    CircleFootprint,
    Footprint,
    Interval,
    RectFootprint,
    Region,
    RoomBounds,
    region_within_bounds,
    regions_overlap,
)
from generator.placement import (
    z_extent_ceiling,
    z_extent_floor,
    z_extent_on,
    z_extent_wall,
)


@dataclass(frozen=True)
class PlacementSpec:
    """One object's placement instruction. The footprint is pre-centered (cx, cy set);
    the z-extent is derived here from the anchor."""
    object_id: str
    footprint: Footprint
    height: int
    z_anchor: str  # "floor" | "wall" | "ceiling" | "on"
    mount_center: Optional[int] = None  # required for "wall"
    support_id: Optional[str] = None    # required for "on"
    no_collide: bool = False            # True for floor coverings
    group_id: Optional[str] = None      # groupable-set membership


@dataclass
class Placed:
    object_id: str
    region: Region
    no_collide: bool = False
    group_id: Optional[str] = None
    member_ids: list[str] = field(default_factory=list)  # >1 for a merged composite


# --- region construction -----------------------------------------------------

def build_region(spec: PlacementSpec, placed_by_id: dict[str, Placed], bounds: RoomBounds) -> Region:
    if spec.z_anchor == "floor":
        z = z_extent_floor(spec.height)
    elif spec.z_anchor == "wall":
        if spec.mount_center is None:
            raise ValueError(f"{spec.object_id}: wall anchor needs mount_center")
        z = z_extent_wall(spec.mount_center, spec.height)
    elif spec.z_anchor == "ceiling":
        z = z_extent_ceiling(bounds.h, spec.height)
    elif spec.z_anchor == "on":
        if spec.support_id is None or spec.support_id not in placed_by_id:
            raise ValueError(f"{spec.object_id}: 'on' anchor needs an already-placed support")
        z = z_extent_on(placed_by_id[spec.support_id].region.z.hi, spec.height)
    else:
        raise ValueError(f"{spec.object_id}: unknown z_anchor '{spec.z_anchor}'")
    return Region(spec.footprint, z)


# --- collision resolution ----------------------------------------------------

def _translate(fp: Footprint, dx: int, dy: int) -> Footprint:
    if isinstance(fp, RectFootprint):
        return RectFootprint(fp.cx + dx, fp.cy + dy, fp.d, fp.w)
    if isinstance(fp, CircleFootprint):
        return CircleFootprint(fp.cx + dx, fp.cy + dy, fp.r)
    raise TypeError(type(fp).__name__)


def _collides(region: Region, others: list[Placed], group_id: Optional[str]) -> bool:
    for o in others:
        if o.no_collide:               # coverings never block
            continue
        if group_id is not None and o.group_id == group_id:  # same group may overlap (it merges)
            continue
        if regions_overlap(region, o.region):
            return True
    return False


def _ring(radius: int) -> list[tuple[int, int]]:
    pts = [(dx, dy)
           for dx in range(-radius, radius + 1)
           for dy in range(-radius, radius + 1)
           if max(abs(dx), abs(dy)) == radius]
    pts.sort(key=lambda p: (abs(p[0]) + abs(p[1]), p))  # nearest first, deterministic
    return pts


def resolve_collision(region: Region, others: list[Placed], bounds: RoomBounds,
                      no_collide: bool, group_id: Optional[str],
                      max_radius: Optional[int] = None) -> Optional[Region]:
    """Return a non-colliding, in-bounds region by nudging xy (z unchanged), or None if
    no spot is found within max_radius."""
    if no_collide:
        return region
    if region_within_bounds(region, bounds) and not _collides(region, others, group_id):
        return region
    R = max_radius if max_radius is not None else max(bounds.d, bounds.w)
    for radius in range(1, R + 1):
        for dx, dy in _ring(radius):
            cand = Region(_translate(region.footprint, dx, dy), region.z)
            if region_within_bounds(cand, bounds) and not _collides(cand, others, group_id):
                return cand
    return None


# --- merge -------------------------------------------------------------------

def _edges(fp: Footprint) -> tuple[float, float, float, float]:
    """(x_lo, x_hi, y_lo, y_hi) of a footprint."""
    if isinstance(fp, RectFootprint):
        return (fp.cx - fp.d / 2, fp.cx + fp.d / 2, fp.cy - fp.w / 2, fp.cy + fp.w / 2)
    if isinstance(fp, CircleFootprint):
        return (fp.cx - fp.r, fp.cx + fp.r, fp.cy - fp.r, fp.cy + fp.r)
    raise TypeError(type(fp).__name__)


def merge_regions(regions: list[Region]) -> Region:
    """Axis-aligned bounding box enclosing all footprints; z spans min..max.
    The box is integer-centered with integer extents (expanded outward as needed)."""
    if not regions:
        raise ValueError("merge_regions needs at least one region")
    xs_lo, xs_hi, ys_lo, ys_hi = zip(*(_edges(r.footprint) for r in regions))
    minx, maxx = math.floor(min(xs_lo)), math.ceil(max(xs_hi))
    miny, maxy = math.floor(min(ys_lo)), math.ceil(max(ys_hi))
    if (minx + maxx) % 2:  # keep center integer
        maxx += 1
    if (miny + maxy) % 2:
        maxy += 1
    fp = RectFootprint(cx=(minx + maxx) // 2, cy=(miny + maxy) // 2, d=maxx - minx, w=maxy - miny)
    z = Interval(min(r.z.lo for r in regions), max(r.z.hi for r in regions))
    return Region(fp, z)


def _components(members: list[Placed]) -> list[list[Placed]]:
    """Connected components of group members by region overlap."""
    n = len(members)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if regions_overlap(members[i].region, members[j].region):
                parent[find(i)] = find(j)
    comps: dict[int, list[Placed]] = defaultdict(list)
    for i, m in enumerate(members):
        comps[find(i)].append(m)
    return list(comps.values())


def apply_merges(placed: list[Placed]) -> list[Placed]:
    """Replace each set of overlapping groupable members with one composite region.
    Non-overlapping group members and ungrouped objects are left as-is."""
    groups: dict[str, list[Placed]] = defaultdict(list)
    out: list[Placed] = []
    for p in placed:
        if p.group_id:
            groups[p.group_id].append(p)
        else:
            out.append(p)
    for gid, members in groups.items():
        for comp in _components(members):
            if len(comp) == 1:
                out.append(comp[0])
            else:
                out.append(Placed(
                    object_id=gid,
                    region=merge_regions([m.region for m in comp]),
                    group_id=gid,
                    member_ids=[m.object_id for m in comp],
                ))
    return out


# --- orchestration -----------------------------------------------------------

def place_all(specs: list[PlacementSpec], bounds: RoomBounds) -> list[Placed]:
    """Place specs in the given order, resolving collisions, then merge groups.
    Returns the placed regions. Raises if an object cannot be placed."""
    placed: list[Placed] = []
    by_id: dict[str, Placed] = {}
    for spec in specs:
        region = build_region(spec, by_id, bounds)
        resolved = resolve_collision(region, placed, bounds, spec.no_collide, spec.group_id)
        if resolved is None:
            raise ValueError(f"could not place {spec.object_id} without collision")
        p = Placed(spec.object_id, resolved, spec.no_collide, spec.group_id)
        placed.append(p)
        by_id[spec.object_id] = p
    return apply_merges(placed)
