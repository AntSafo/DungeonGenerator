"""Image -> ASCII conversion (steps 7-8).

Two ideas:
  1. Character ink coverage is measured by rendering each glyph in a fixed cell and
     counting filled pixels, then normalizing. A block's target darkness picks the
     nearest-coverage character.
  2. Perceived lightness != physical luminance. We linearize sRGB to relative
     luminance Y, then convert to CIE L* (~Y^(1/3)) so equal steps in the character
     ramp correspond to equal steps in *perceived* lightness. `perceptual=False` maps
     raw linear luminance instead (the physically-faithful-but-too-dark "before").

Character cells are ~2x taller than wide (terminal glyphs), so each sampled block is
sampled taller than wide (char_aspect) to keep the output proportional.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Dark -> light ramp (ordering is re-measured per font below); includes space.
DEFAULT_CHARSET = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
CHAR_ASPECT = 0.5   # character width / height
_RAMP_FONT_PX = 24


# --- luminance ---------------------------------------------------------------

def _linearize(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance_linear(rgb: np.ndarray) -> np.ndarray:
    """Relative (physical) luminance Y in [0,1] from an HxWx3 uint8 sRGB array."""
    a = rgb.astype(np.float64) / 255.0
    lin = _linearize(a)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def lightness_perceptual(rgb: np.ndarray) -> np.ndarray:
    """Perceptual lightness L*/100 in [0,1] (CIE Lab) from an HxWx3 uint8 sRGB array."""
    y = luminance_linear(rgb)
    lstar = np.where(y <= 0.008856, y * 903.3, 116.0 * np.cbrt(y) - 16.0)
    return np.clip(lstar / 100.0, 0.0, 1.0)


# --- character coverage ramp -------------------------------------------------

@lru_cache(maxsize=4)
def _mono_font(size: int):
    """A monospace font, so the coverage ramp and the preview PNG match how the .txt
    actually displays in a monospace viewer. Falls back to PIL's default if none found."""
    for name in ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
                 "DejaVuSansMono.ttf", "consola.ttf", "cour.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


@lru_cache(maxsize=8)
def _ramp(charset: str, font_px: int):
    """Return (coverages, chars) sorted ascending by normalized ink coverage."""
    font = _mono_font(font_px)
    try:
        cw = max(1, round(font.getlength("M")))   # monospace advance width
    except Exception:
        cw = font_px
    ch = max(1, round(cw / CHAR_ASPECT))
    covs = []
    for ch_ in charset:
        cell = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(cell).text((0, 0), ch_, fill=255, font=font)
        covs.append(float(np.asarray(cell).mean()) / 255.0)
    covs = np.array(covs)
    covs = (covs - covs.min()) / (covs.max() - covs.min() + 1e-9)
    order = np.argsort(covs, kind="stable")
    return covs[order], [charset[i] for i in order]


def coverage_of(char: str, charset: str = DEFAULT_CHARSET) -> float:
    covs, chars = _ramp(charset, _RAMP_FONT_PX)
    return float(covs[chars.index(char)])


def _lut(charset: str, invert: bool):
    """256-entry char lookup table indexed by target darkness*255."""
    covs, chars = _ramp(charset, _RAMP_FONT_PX)
    levels = np.linspace(0.0, 1.0, 256)
    idx = np.abs(covs[None, :] - levels[:, None]).argmin(axis=1)
    return np.array([chars[i] for i in idx], dtype="<U1")


# --- conversion --------------------------------------------------------------

def _scurve(x: np.ndarray, amount: float) -> np.ndarray:
    """S-curve contrast around mid-gray; amount in [0,1] (0 = none). Ends stay at 0/1."""
    if amount <= 0:
        return x
    k = amount * 8.0
    s = 1.0 / (1.0 + np.exp(-k * (x - 0.5)))
    s0 = 1.0 / (1.0 + np.exp(k * 0.5))
    s1 = 1.0 / (1.0 + np.exp(-k * 0.5))
    return (s - s0) / (s1 - s0)


def _tone_map(blocks: np.ndarray, auto_levels: bool, levels_clip: float, contrast: float) -> np.ndarray:
    """Auto-stretch the block range to [0,1] (robust percentiles) and boost contrast.

    This makes the character set span the image's full brightness range and helps features
    stand out — important for coarse output, where block averaging compresses the range.
    """
    if auto_levels:
        lo, hi = np.percentile(blocks, [levels_clip * 100, 100 - levels_clip * 100])
        if hi - lo > 1e-6:
            blocks = np.clip((blocks - lo) / (hi - lo), 0.0, 1.0)
    return _scurve(blocks, contrast)


def image_to_ascii(img: Image.Image, cell_w: int = 6, char_aspect: float = CHAR_ASPECT,
                   perceptual: bool = True, invert: bool = False, charset: str = DEFAULT_CHARSET,
                   auto_levels: bool = True, levels_clip: float = 0.02, contrast: float = 0.25) -> str:
    """Convert an image to ASCII. `cell_w` = source pixels per character (the resolution
    knob: larger -> coarser). `invert=False` maps darker image -> denser glyph (ink on a
    light background); `invert=True` maps brighter -> denser (for light-on-dark terminals).

    `auto_levels` stretches the per-image block range to [0,1] (clipping `levels_clip` at
    each end) so the extreme glyphs are reached; `contrast` (0-1) applies an S-curve. Both
    auto-tune to the input.
    """
    rgb = np.asarray(img.convert("RGB"))
    light = lightness_perceptual(rgb) if perceptual else luminance_linear(rgb)
    cell_h = max(1, round(cell_w / char_aspect))
    h, w = light.shape
    rows, cols = h // cell_h, w // cell_w
    if rows == 0 or cols == 0:
        raise ValueError("image too small for this cell size")
    light = light[: rows * cell_h, : cols * cell_w]
    blocks = light.reshape(rows, cell_h, cols, cell_w).mean(axis=(1, 3))
    blocks = _tone_map(blocks, auto_levels, levels_clip, contrast)
    target = blocks if invert else 1.0 - blocks
    idx = np.clip((target * 255).round().astype(int), 0, 255)
    grid = _lut(charset, invert)[idx]
    return "\n".join("".join(row) for row in grid)


def save_ascii(text: str, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8", newline="\n")
    return out


def render_ascii_to_image(text: str, cell=(7, 14), fg=(20, 20, 20),
                          bg=(255, 255, 255), font_px: int = 12) -> Image.Image:
    """Draw ASCII text on a fixed monospace grid so it can be viewed as an image."""
    lines = text.split("\n")
    rows = len(lines)
    cols = max((len(line) for line in lines), default=0)
    cw, ch = cell
    img = Image.new("RGB", (max(1, cols * cw), max(1, rows * ch)), bg)
    draw = ImageDraw.Draw(img)
    font = _mono_font(font_px)
    for r, line in enumerate(lines):
        for c, glyph in enumerate(line):
            if glyph != " ":
                draw.text((c * cw, r * ch), glyph, fill=fg, font=font)
    return img
