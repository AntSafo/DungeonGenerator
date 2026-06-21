"""Room-size presets and the placement grid (step 3).

See docs/room-presets-and-reference-sizes.md. Every preset dimension is divisible by
8 so that, with a 4x4 grid, each cell size is even and every cell center is an integer
cm. That invariant is asserted at import time.
"""

from __future__ import annotations

from dataclasses import dataclass

from generator.geometry import RoomBounds

GRID_CELLS = 4  # per axis (4x4)


@dataclass(frozen=True)
class Grid:
    """A uniform grid over the room floor. cell_d/cell_w are even (integer centers)."""
    cells: int
    cell_d: int  # cell extent along x (depth)
    cell_w: int  # cell extent along y (width)

    def cell_center(self, ix: int, iy: int) -> tuple[int, int]:
        if not (0 <= ix < self.cells and 0 <= iy < self.cells):
            raise IndexError(f"cell ({ix}, {iy}) out of range for {self.cells}x{self.cells} grid")
        cx = self.cell_d * ix + self.cell_d // 2
        cy = self.cell_w * iy + self.cell_w // 2
        return cx, cy


@dataclass(frozen=True)
class Preset:
    name: str
    bounds: RoomBounds
    grid: Grid


def _make(name: str, d: int, w: int, h: int) -> Preset:
    if d % (2 * GRID_CELLS) or w % (2 * GRID_CELLS):
        raise ValueError(f"{name}: depth/width must be divisible by {2 * GRID_CELLS} for integer cell centers")
    return Preset(name=name,
                  bounds=RoomBounds(d=d, w=w, h=h),
                  grid=Grid(cells=GRID_CELLS, cell_d=d // GRID_CELLS, cell_w=w // GRID_CELLS))


ROOM_PRESETS: dict[str, Preset] = {
    "small": _make("small", 400, 200, 240),
    "medium": _make("medium", 360, 360, 260),
    "large": _make("large", 528, 352, 290),
    "grand": _make("grand", 432, 648, 340),
}


def get_preset(name: str) -> Preset:
    try:
        return ROOM_PRESETS[name]
    except KeyError:
        raise KeyError(f"unknown room size preset '{name}'") from None
