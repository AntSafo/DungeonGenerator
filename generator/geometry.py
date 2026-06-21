"""Geometry primitives for spatial layout (step 3).

All coordinates are integer centimeters in the room frame (origin back-left;
+x toward viewer / depth, +y right / width, +z up / height). A footprint lives in
the x-y (floor) plane; a region adds a vertical extent.

Overlap is **strict**: objects that merely touch at a boundary (a cup resting on a
table, two boxes flush against each other) do NOT count as overlapping. To stay exact
on integer cm, rect math is done in a 2x-scaled space so half-cm edges (odd sizes)
never introduce floats.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    """A closed integer interval [lo, hi] on one axis."""
    lo: int
    hi: int

    def __post_init__(self):
        if self.hi < self.lo:
            raise ValueError(f"Interval hi ({self.hi}) < lo ({self.lo})")

    def overlaps(self, other: "Interval") -> bool:
        """True iff the intervals share more than a single boundary point."""
        return self.lo < other.hi and other.lo < self.hi

    def contains(self, other: "Interval") -> bool:
        return self.lo <= other.lo and other.hi <= self.hi


@dataclass(frozen=True)
class RectFootprint:
    """Axis-aligned rectangle, given by its center and full extents."""
    cx: int  # center on x (depth)
    cy: int  # center on y (width)
    d: int   # full extent along x (depth)
    w: int   # full extent along y (width)

    def __post_init__(self):
        if self.d <= 0 or self.w <= 0:
            raise ValueError("RectFootprint extents must be positive")


@dataclass(frozen=True)
class CircleFootprint:
    """Circle, given by its center and radius."""
    cx: int
    cy: int
    r: int

    def __post_init__(self):
        if self.r <= 0:
            raise ValueError("CircleFootprint radius must be positive")


Footprint = RectFootprint | CircleFootprint


@dataclass(frozen=True)
class Region:
    """A footprint plus a vertical extent [z_bottom, z_top]."""
    footprint: Footprint
    z: Interval


@dataclass(frozen=True)
class RoomBounds:
    """Room interior extent: d along x (depth), w along y (width), h along z (height)."""
    d: int
    w: int
    h: int

    def __post_init__(self):
        if self.d <= 0 or self.w <= 0 or self.h <= 0:
            raise ValueError("RoomBounds dimensions must be positive")


# --- footprint overlap (strict) ---------------------------------------------

def _rect_rect(a: RectFootprint, b: RectFootprint) -> bool:
    # 2*|dcenter| < sum of full extents  <=>  edges strictly overlap.
    return (2 * abs(a.cx - b.cx) < a.d + b.d) and (2 * abs(a.cy - b.cy) < a.w + b.w)


def _circle_circle(a: CircleFootprint, b: CircleFootprint) -> bool:
    dx, dy = a.cx - b.cx, a.cy - b.cy
    rr = a.r + b.r
    return dx * dx + dy * dy < rr * rr


def _rect_circle(rect: RectFootprint, circ: CircleFootprint) -> bool:
    # Work in 2x integer space so odd rect extents stay exact.
    cx2, cy2 = 2 * circ.cx, 2 * circ.cy
    xlo, xhi = 2 * rect.cx - rect.d, 2 * rect.cx + rect.d
    ylo, yhi = 2 * rect.cy - rect.w, 2 * rect.cy + rect.w
    px = min(max(cx2, xlo), xhi)
    py = min(max(cy2, ylo), yhi)
    dx, dy = cx2 - px, cy2 - py  # = 2 * (distance from circle center to nearest edge)
    return dx * dx + dy * dy < (2 * circ.r) ** 2


def footprints_overlap(a: Footprint, b: Footprint) -> bool:
    if isinstance(a, RectFootprint) and isinstance(b, RectFootprint):
        return _rect_rect(a, b)
    if isinstance(a, CircleFootprint) and isinstance(b, CircleFootprint):
        return _circle_circle(a, b)
    if isinstance(a, RectFootprint) and isinstance(b, CircleFootprint):
        return _rect_circle(a, b)
    if isinstance(a, CircleFootprint) and isinstance(b, RectFootprint):
        return _rect_circle(b, a)
    raise TypeError(f"unsupported footprint types: {type(a).__name__}, {type(b).__name__}")


def regions_overlap(a: Region, b: Region) -> bool:
    """3D overlap: footprints overlap AND vertical extents overlap (both strict)."""
    return footprints_overlap(a.footprint, b.footprint) and a.z.overlaps(b.z)


# --- bounds checks (inclusive: flush against a wall is in-bounds) ------------

def footprint_within(fp: Footprint, bounds: RoomBounds) -> bool:
    if isinstance(fp, RectFootprint):
        return (2 * fp.cx - fp.d >= 0 and 2 * fp.cx + fp.d <= 2 * bounds.d
                and 2 * fp.cy - fp.w >= 0 and 2 * fp.cy + fp.w <= 2 * bounds.w)
    if isinstance(fp, CircleFootprint):
        return (fp.cx - fp.r >= 0 and fp.cx + fp.r <= bounds.d
                and fp.cy - fp.r >= 0 and fp.cy + fp.r <= bounds.w)
    raise TypeError(f"unsupported footprint type: {type(fp).__name__}")


def region_within_bounds(region: Region, bounds: RoomBounds) -> bool:
    return (footprint_within(region.footprint, bounds)
            and region.z.lo >= 0 and region.z.hi <= bounds.h)
