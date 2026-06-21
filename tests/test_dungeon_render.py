"""Tests for the final ASCII render stage (steps 7-8)."""

import numpy as np
from PIL import Image

from generator.ascii_art import coverage_of
from generator.dungeon_render import save_dungeon_ascii, to_dungeon_ascii


def _gradient(w=240, h=120):
    ramp = np.tile(np.linspace(0, 255, w), (h, 1)).astype(np.uint8)
    return Image.fromarray(np.stack([ramp] * 3, axis=-1))


def test_hits_target_columns_with_equal_lines():
    text = to_dungeon_ascii(_gradient(240, 120), cols=60)
    lines = text.splitlines()
    assert len(lines[0]) == 60
    assert len({len(line) for line in lines}) == 1   # every line equal width


def test_invert_maps_bright_to_dense():
    # Left dark -> right bright; with invert, the bright (right) end is the densest glyph.
    line = to_dungeon_ascii(_gradient(240, 120), cols=60).splitlines()[0]
    assert coverage_of(line[-1]) > coverage_of(line[0])


def test_save_writes_utf8_with_trailing_newline(tmp_path):
    out = tmp_path / "06_ascii.txt"
    save_dungeon_ascii(_gradient(), out, cols=50)
    content = out.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert len(content.splitlines()) > 0
