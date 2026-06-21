"""Tests for the ASCII converter and the luminance handling."""

import numpy as np
from PIL import Image

from generator.ascii_art import (
    DEFAULT_CHARSET,
    coverage_of,
    image_to_ascii,
    lightness_perceptual,
    luminance_linear,
    render_ascii_to_image,
)


def _solid(rgb, size=(64, 64)):
    return Image.new("RGB", size, rgb)


# --- luminance --------------------------------------------------------------

def test_luminance_endpoints():
    white = np.full((1, 1, 3), 255, np.uint8)
    black = np.zeros((1, 1, 3), np.uint8)
    assert luminance_linear(white)[0, 0] > 0.999
    assert luminance_linear(black)[0, 0] < 1e-6
    assert lightness_perceptual(white)[0, 0] > 0.999


def test_perceptual_lifts_midtones_above_physical():
    mid = np.full((1, 1, 3), 128, np.uint8)
    y = luminance_linear(mid)[0, 0]            # ~0.216 (too dark)
    lstar = lightness_perceptual(mid)[0, 0]    # ~0.53 (matches perception)
    assert lstar > y + 0.2


def test_green_is_brighter_than_blue():
    # Rec.709 weighting: pure green reads much brighter than pure blue.
    g = luminance_linear(np.array([[[0, 255, 0]]], np.uint8))[0, 0]
    b = luminance_linear(np.array([[[0, 0, 255]]], np.uint8))[0, 0]
    assert g > b


# --- coverage ramp ----------------------------------------------------------

def test_space_is_lightest_and_dense_glyphs_are_heaviest():
    assert coverage_of(" ") < 0.01
    assert coverage_of("@") > coverage_of(".")
    assert coverage_of("#") > coverage_of(":")


# --- conversion -------------------------------------------------------------

def test_solid_images_map_to_expected_extremes():
    white = image_to_ascii(_solid((255, 255, 255)), cell_w=8)
    black = image_to_ascii(_solid((0, 0, 0)), cell_w=8)
    assert set(white.replace("\n", "")) == {" "}        # light -> blank
    assert coverage_of(black.strip()[0]) > 0.8           # dark -> dense glyph


def test_resolution_knob_changes_grid_size():
    img = _solid((128, 128, 128), size=(128, 128))
    fine = image_to_ascii(img, cell_w=4)
    coarse = image_to_ascii(img, cell_w=16)
    assert len(fine.splitlines()[0]) > len(coarse.splitlines()[0])


def test_cells_are_taller_than_wide():
    # 100x100 image, cell_w=10, char_aspect 0.5 -> cell_h=20 -> 10 cols, 5 rows.
    out = image_to_ascii(Image.new("RGB", (100, 100), (90, 90, 90)), cell_w=10)
    lines = out.splitlines()
    assert len(lines[0]) == 10 and len(lines) == 5


def test_horizontal_gradient_is_monotonic_in_coverage():
    # Left dark -> right light; left chars should be denser than right.
    ramp = np.tile(np.linspace(0, 255, 256, dtype=np.uint8), (32, 1))
    img = Image.fromarray(np.stack([ramp] * 3, axis=-1))
    line = image_to_ascii(img, cell_w=8).splitlines()[0]
    assert coverage_of(line[0]) > coverage_of(line[-1])


def test_invert_flips_mapping():
    dark = _solid((30, 30, 30))
    normal = image_to_ascii(dark, cell_w=8)             # dark -> dense
    inverted = image_to_ascii(dark, cell_w=8, invert=True)  # dark -> blank
    assert coverage_of(normal.strip()[0]) > coverage_of(inverted.strip()[0] if inverted.strip() else " ")


def _coverage_span(text: str) -> float:
    chars = {ch for ch in text if ch != "\n"}
    covs = [coverage_of(c) for c in chars]
    return max(covs) - min(covs)


def test_auto_levels_expands_low_contrast_image():
    # A gradient compressed into a narrow brightness band (sRGB 110-150).
    ramp = np.tile(np.linspace(110, 150, 256), (40, 1)).astype(np.uint8)
    img = Image.fromarray(np.stack([ramp] * 3, axis=-1))
    flat = image_to_ascii(img, cell_w=8, auto_levels=False, contrast=0.0)
    auto = image_to_ascii(img, cell_w=8)  # defaults: auto_levels on
    assert _coverage_span(auto) > _coverage_span(flat) + 0.2


def test_render_ascii_to_image_size():
    text = "abc\nde f"   # widest line is 4 chars
    img = render_ascii_to_image(text, cell=(7, 14))
    assert img.size == (4 * 7, 2 * 14)
