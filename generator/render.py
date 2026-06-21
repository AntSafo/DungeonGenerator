"""Wireframe rendering of a placed layout (step 4).

A pinhole camera floats just in front of the front wall (max x), centered, at eye
height, looking toward the back wall (x=0). It projects the room box and each placed
region (box for rect footprints, cylinder for circle footprints) to a fixed-size image.
The PNG it saves is the shared base image the fal step (step 6) will condition on.

Coordinate frame: origin back-left floor corner, +x toward viewer (depth), +y right
(width), +z up (height); integer cm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from generator.engine import Placed
from generator.geometry import CircleFootprint, RectFootprint, Region, RoomBounds

# Camera / canvas constants (locked; see the step-4 discussion).
EYE_Z = 160         # 170 cm reference human - 10 for eye level
CAM_INSET = 10      # cm the camera floats in front of the wall it sits on (front, max x)
HFOV_DEG = 88       # horizontal field of view; wide enough to catch near-corner objects
CANVAS_W, CANVAS_H = 1024, 768   # canonical image size, shared by wireframe/depth/render
NEAR = 1.0          # near clip plane (cm in front of the camera)
CYL_SEGMENTS = 24
DEPTH_GAMMA = 0.5   # <1 lifts the far/dark end so objects separate from the black back wall

Point = tuple[float, float, float]


@dataclass(frozen=True)
class Camera:
    eye: Point
    focal: float
    cx: float
    cy: float
    width: int
    height: int
    near: float


def camera_for(bounds: RoomBounds) -> Camera:
    """Camera at (depth-inset, width/2, eye_z) looking down -x toward the x=0 wall."""
    eye = (bounds.d - CAM_INSET, bounds.w / 2, EYE_Z)
    focal = (CANVAS_W / 2) / math.tan(math.radians(HFOV_DEG) / 2)
    return Camera(eye, focal, CANVAS_W / 2, CANVAS_H / 2, CANVAS_W, CANVAS_H, NEAR)


def _depth(p: Point, cam: Camera) -> float:
    return cam.eye[0] - p[0]  # dot(P - eye, forward=(-1,0,0))


def project(p: Point, cam: Camera) -> tuple[float, float]:
    """Project a point assumed to be in front of the near plane to pixel coords."""
    dep = _depth(p, cam)
    hor = p[1] - cam.eye[1]   # dot with right = (0,1,0)
    ver = p[2] - cam.eye[2]   # dot with up = (0,0,1)
    px = cam.cx + cam.focal * hor / dep
    py = cam.cy - cam.focal * ver / dep   # invert: image rows increase downward
    return px, py


def clip_near(a: Point, b: Point, cam: Camera):
    """Clip a segment to the near plane. Returns (A, B) or None if fully behind."""
    da, db = _depth(a, cam), _depth(b, cam)
    if da >= cam.near and db >= cam.near:
        return a, b
    if da < cam.near and db < cam.near:
        return None
    t = (cam.near - da) / (db - da)
    inter = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
    return (inter, b) if da < cam.near else (a, inter)


def _segment(draw: ImageDraw.ImageDraw, a: Point, b: Point, cam: Camera, color, width: int):
    clipped = clip_near(a, b, cam)
    if clipped is None:
        return
    A, B = clipped
    draw.line([project(A, cam), project(B, cam)], fill=color, width=width)


def _box_edges(x0, x1, y0, y1, z0, z1):
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    return [(c[i], c[j]) for i, j in edges]


def _draw_region(draw, region: Region, cam: Camera, color, width: int):
    fp = region.footprint
    z0, z1 = region.z.lo, region.z.hi
    if isinstance(fp, RectFootprint):
        x0, x1 = fp.cx - fp.d / 2, fp.cx + fp.d / 2
        y0, y1 = fp.cy - fp.w / 2, fp.cy + fp.w / 2
        for a, b in _box_edges(x0, x1, y0, y1, z0, z1):
            _segment(draw, a, b, cam, color, width)
    elif isinstance(fp, CircleFootprint):
        n = CYL_SEGMENTS
        ring = [(fp.cx + fp.r * math.cos(2 * math.pi * k / n),
                 fp.cy + fp.r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        for k in range(n):
            ax, ay = ring[k]
            bx, by = ring[(k + 1) % n]
            _segment(draw, (ax, ay, z0), (bx, by, z0), cam, color, width)  # bottom
            _segment(draw, (ax, ay, z1), (bx, by, z1), cam, color, width)  # top
            _segment(draw, (ax, ay, z0), (ax, ay, z1), cam, color, width)  # vertical
    else:
        raise TypeError(type(fp).__name__)


def render_wireframe(placed: list[Placed], bounds: RoomBounds,
                     room_color=(170, 170, 170), object_color=(0, 0, 0),
                     background=(255, 255, 255)) -> Image.Image:
    """Render the room box (light) + every placed region (dark) to a fixed-size image."""
    cam = camera_for(bounds)
    img = Image.new("RGB", (cam.width, cam.height), background)
    draw = ImageDraw.Draw(img)
    for a, b in _box_edges(0, bounds.d, 0, bounds.w, 0, bounds.h):
        _segment(draw, a, b, cam, room_color, width=2)
    for p in placed:
        _draw_region(draw, p.region, cam, object_color, width=2)
    return img


def save_wireframe(placed: list[Placed], bounds: RoomBounds, path: str | Path) -> Path:
    """Render and save the wireframe PNG (the shared base image for the fal step)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    render_wireframe(placed, bounds).save(out)
    return out


# --- depth map ---------------------------------------------------------------
# Per-pixel ray cast (vectorized in numpy): for every pixel, find the nearest surface
# (room shell + object boxes/cylinders) and record its forward depth, then map to gray.

def _ray_dirs(cam: Camera):
    xs = np.arange(cam.width) + 0.5
    ys = np.arange(cam.height) + 0.5
    sx = xs - cam.cx
    sy = cam.cy - ys
    SX, SY = np.meshgrid(sx, sy)          # (H, W)
    dirx = np.full(SX.shape, -cam.focal)
    return dirx, SX, SY                    # ray direction = (-focal, sx, sy)


def _plane_t(eye, d, axis, value, other_bounds):
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (value - eye[axis]) / d[axis]
    valid = t > 1e-6
    for ax, (lo, hi) in other_bounds.items():
        coord = eye[ax] + t * d[ax]
        valid &= (coord >= lo) & (coord <= hi)
    return np.where(valid, t, np.inf)


def _aabb_t(eye, d, box):
    lo = (box[0], box[2], box[4])
    hi = (box[1], box[3], box[5])
    tmin = np.full(d[0].shape, -np.inf)
    tmax = np.full(d[0].shape, np.inf)
    for ax in range(3):
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (lo[ax] - eye[ax]) / d[ax]
            t2 = (hi[ax] - eye[ax]) / d[ax]
        tmin = np.maximum(tmin, np.minimum(t1, t2))
        tmax = np.minimum(tmax, np.maximum(t1, t2))
    hit = (tmax >= tmin) & (tmax > 1e-6)
    entry = np.where(tmin > 1e-6, tmin, tmax)   # use exit t if the camera is inside
    return np.where(hit, entry, np.inf)


def _cyl_t(eye, d, cx, cy, r, z0, z1):
    dx, dy, dz = d
    ox, oy = eye[0] - cx, eye[1] - cy
    a = dx * dx + dy * dy
    b = 2 * (ox * dx + oy * dy)
    c = ox * ox + oy * oy - r * r
    disc = b * b - 4 * a * c
    ok = disc >= 0
    sq = np.sqrt(np.where(ok, disc, 0.0))
    ts = np.full(dx.shape, np.inf)
    with np.errstate(divide="ignore", invalid="ignore"):
        for t in ((-b - sq) / (2 * a), (-b + sq) / (2 * a)):   # curved side
            pz = eye[2] + t * dz
            m = ok & (t > 1e-6) & (pz >= z0) & (pz <= z1)
            ts = np.where(m & (t < ts), t, ts)
        for zc in (z0, z1):                                    # flat end caps
            tc = (zc - eye[2]) / dz
            px, py = eye[0] + tc * dx, eye[1] + tc * dy
            m = (tc > 1e-6) & ((px - cx) ** 2 + (py - cy) ** 2 <= r * r)
            ts = np.where(m & (tc < ts), tc, ts)
    return ts


def depth_buffer(placed: list[Placed], bounds: RoomBounds, cam: Camera):
    """Per-pixel forward depth (cm) of the nearest surface; +inf where nothing is hit."""
    d = _ray_dirs(cam)
    eye = cam.eye
    t = np.full(d[0].shape, np.inf)
    t = np.minimum(t, _plane_t(eye, d, 0, 0.0, {1: (0, bounds.w), 2: (0, bounds.h)}))             # back wall
    t = np.minimum(t, _plane_t(eye, d, 1, 0.0, {0: (0, bounds.d), 2: (0, bounds.h)}))             # left wall
    t = np.minimum(t, _plane_t(eye, d, 1, float(bounds.w), {0: (0, bounds.d), 2: (0, bounds.h)}))  # right wall
    t = np.minimum(t, _plane_t(eye, d, 2, 0.0, {0: (0, bounds.d), 1: (0, bounds.w)}))             # floor
    t = np.minimum(t, _plane_t(eye, d, 2, float(bounds.h), {0: (0, bounds.d), 1: (0, bounds.w)}))  # ceiling
    for p in placed:
        fp = p.region.footprint
        z0, z1 = p.region.z.lo, p.region.z.hi
        if isinstance(fp, RectFootprint):
            t = np.minimum(t, _aabb_t(eye, d, (fp.cx - fp.d / 2, fp.cx + fp.d / 2,
                                               fp.cy - fp.w / 2, fp.cy + fp.w / 2, z0, z1)))
        elif isinstance(fp, CircleFootprint):
            t = np.minimum(t, _cyl_t(eye, d, fp.cx, fp.cy, fp.r, z0, z1))
        else:
            raise TypeError(type(fp).__name__)
    return t * cam.focal   # forward depth = t * focal (since |dir.x| = focal)


def render_depth(placed: list[Placed], bounds: RoomBounds, near_white: bool = True,
                 gamma: float = DEPTH_GAMMA) -> Image.Image:
    """Grayscale depth map (3-channel) for control conditioning.

    The back wall is the farthest surface, so it normalizes to pure black; near_white
    makes closer surfaces brighter. A gamma < 1 lifts the far/dark midtones so objects
    sitting just in front of the back wall stay clearly distinguishable from it.
    """
    cam = camera_for(bounds)
    dep = depth_buffer(placed, bounds, cam)
    finite = np.isfinite(dep)
    lo, hi = dep[finite].min(), dep[finite].max()   # hi = back-wall depth -> pure black
    norm = np.clip((dep - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    shade = (1.0 - norm) if near_white else norm
    shade = np.power(shade, gamma)
    gray = (shade * 255).astype(np.uint8)
    gray[~finite] = 0
    return Image.fromarray(gray, mode="L").convert("RGB")


def save_depth(placed: list[Placed], bounds: RoomBounds, path: str | Path,
               near_white: bool = True, gamma: float = DEPTH_GAMMA) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    render_depth(placed, bounds, near_white, gamma).save(out)
    return out
