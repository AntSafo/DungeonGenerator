"""Tests for the wireframe camera/projection math."""

import numpy as np

from generator.engine import Placed
from generator.geometry import Interval, RectFootprint, Region, RoomBounds
from generator.render import (
    CANVAS_H,
    CANVAS_W,
    EYE_Z,
    camera_for,
    clip_near,
    depth_buffer,
    project,
    render_depth,
    render_wireframe,
)

BOUNDS = RoomBounds(d=400, w=200, h=240)
CAM = camera_for(BOUNDS)


def test_camera_position():
    assert CAM.eye == (390, 100, EYE_Z)  # depth-10, width/2, eye height


def test_far_wall_center_projects_to_image_center():
    px, py = project((0, 100, EYE_Z), CAM)  # straight ahead on the back wall, at eye height
    assert abs(px - CANVAS_W / 2) < 1e-6
    assert abs(py - CANVAS_H / 2) < 1e-6


def test_right_of_center_projects_right():
    px, _ = project((0, 150, EYE_Z), CAM)  # +y is screen-right when facing -x
    assert px > CANVAS_W / 2


def test_floor_projects_below_ceiling_above():
    _, py_floor = project((0, 100, 0), CAM)
    _, py_ceiling = project((0, 100, 240), CAM)
    assert py_floor > CANVAS_H / 2   # floor is lower on screen
    assert py_ceiling < CANVAS_H / 2  # ceiling is higher


def test_nearer_object_appears_larger():
    # Same physical half-width, two depths: the closer one spans more pixels.
    near = project((300, 150, EYE_Z), CAM)[0] - project((300, 100, EYE_Z), CAM)[0]
    far = project((50, 150, EYE_Z), CAM)[0] - project((50, 100, EYE_Z), CAM)[0]
    assert near > far


def test_clip_near_drops_fully_behind():
    # Both points are behind the camera (x > eye.x = 390).
    assert clip_near((395, 100, 160), (400, 100, 160), CAM) is None


def test_clip_near_trims_straddling_segment():
    a, b = clip_near((395, 100, 160), (0, 100, 160), CAM)  # a is behind, b in front
    assert abs((CAM.eye[0] - a[0]) - CAM.near) < 1e-6  # trimmed endpoint sits on near plane
    assert b == (0, 100, 160)


def test_render_produces_fixed_size_image():
    placed = [Placed("a", Region(RectFootprint(100, 100, 80, 80), Interval(0, 60)))]
    img = render_wireframe(placed, BOUNDS)
    assert img.size == (CANVAS_W, CANVAS_H)
    assert img.mode == "RGB"


# --- depth map --------------------------------------------------------------

def test_depth_room_shell_is_fully_covered():
    dep = depth_buffer([], BOUNDS, CAM)
    assert np.isfinite(dep).all()  # every ray hits an interior surface


def test_object_is_nearer_than_back_wall():
    empty = depth_buffer([], BOUNDS, CAM)
    box = Placed("b", Region(RectFootprint(200, 100, 80, 80), Interval(0, 200)))
    with_obj = depth_buffer([box], BOUNDS, CAM)
    r, c = int(CAM.cy), int(CAM.cx)  # center pixel looks straight at the box, then the back wall
    assert with_obj[r, c] < empty[r, c]


def test_depth_near_is_brighter_than_far():
    img = render_depth([], BOUNDS)
    arr = np.asarray(img.convert("L"))
    assert img.size == (CANVAS_W, CANVAS_H) and img.mode == "RGB"
    center_far = arr[CANVAS_H // 2, CANVAS_W // 2]   # back wall, farthest
    near_ceiling = arr[10, CANVAS_W // 2]            # ceiling just above the camera, near
    assert near_ceiling > center_far


def test_object_against_back_wall_separates_from_it():
    # A thin tall box flush against the back wall (x in [0,14]) must read clearly
    # lighter than the bare wall beside it, despite being only ~14 cm in front.
    box = Placed("b", Region(RectFootprint(7, 100, 14, 60), Interval(0, 200)))
    arr = np.asarray(render_depth([box], BOUNDS).convert("L"))
    r = CANVAS_H // 2
    box_px = int(arr[r, CANVAS_W // 2])         # center ray -> the box
    wall_px = int(arr[r, CANVAS_W // 2 + 60])   # offset ray -> bare back wall
    assert box_px - wall_px > 20
