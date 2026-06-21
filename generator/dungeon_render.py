"""Steps 7-8 — the final ASCII render of a room image (the last deterministic stage).

Greyscales the (fal-generated) room image and converts it to ASCII with the project's
locked output conventions:
  - the full character set and invert=True (light-on-dark terminal mapping),
  - perceptual L* luminance and automatic per-image tone-mapping (from ascii_art),
  - resolution chosen by a target COLUMN COUNT so the output fits a terminal,
  - equal-length lines, saved UTF-8 with a trailing newline.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance

from generator.ascii_art import image_to_ascii, render_ascii_to_image, save_ascii

DEFAULT_COLS = 120

# Fixed ASCII column widths, coarse -> fine. save_ascii_resolutions also appends the image's
# native width (1 px per character cell = maximum detail).
ASCII_RESOLUTIONS = (100, 200, 450, 800)


def boost_image(image: Image.Image, contrast: float = 1.7, sharpness: float = 2.0) -> Image.Image:
    """Post-production punch for painterly/low-contrast renders before ASCII-ifying."""
    img = ImageEnhance.Contrast(image.convert("RGB")).enhance(contrast)
    return ImageEnhance.Sharpness(img).enhance(sharpness)


def to_dungeon_ascii(image: Image.Image, cols: int = DEFAULT_COLS, invert: bool = True,
                     boost: bool = True) -> str:
    """Final ASCII for a room image at ~`cols` characters wide (the locked conventions).
    `invert` flips bright<->dense; `boost` applies a contrast+sharpen pass first."""
    if boost:
        image = boost_image(image)
    cell_w = max(1, round(image.width / cols))
    return image_to_ascii(image, cell_w=cell_w, invert=invert)


def save_dungeon_ascii(image: Image.Image, txt_path: str | Path, cols: int = DEFAULT_COLS,
                       preview_path: str | Path | None = None, invert: bool = True,
                       boost: bool = True) -> str:
    """Write the final 06_ascii.txt (and an optional light-on-dark preview PNG)."""
    text = to_dungeon_ascii(image, cols, invert=invert, boost=boost)
    save_ascii(text, txt_path)
    if preview_path is not None:
        Path(preview_path).parent.mkdir(parents=True, exist_ok=True)
        render_ascii_to_image(text, fg=(225, 225, 225), bg=(12, 12, 12)).save(preview_path)
    return text


def save_ascii_resolutions(image: Image.Image, out_dir: str | Path, stem: str,
                           resolutions=ASCII_RESOLUTIONS, invert: bool = True,
                           boost: bool = True, previews: bool = True,
                           native: bool = True) -> list[Path]:
    """Write one ASCII .txt per resolution (and a matching light-on-dark preview PNG).

    Each width is capped at the image width; with `native=True` the image's native width is
    also included (1 px per character cell = maximum detail). Files are named by resolution,
    `<stem>_ascii_<cols>c.txt` (e.g. `image_ascii_100c.txt`, `image_ascii_1448c.txt`), so a
    gallery can switch resolutions by filename. The preview cell shrinks for finer tiers.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    widths = {min(int(v), image.width) for v in resolutions}
    if native:
        widths.add(image.width)
    written = []
    for cols in sorted(widths):
        text = to_dungeon_ascii(image, cols=cols, invert=invert, boost=boost)
        base = f"{stem}_ascii_{cols}c"
        save_ascii(text, out / f"{base}.txt")
        written.append(out / f"{base}.txt")
        if previews:
            cw = max(2, min(7, round(1600 / cols)))  # smaller cells for finer ASCII
            render_ascii_to_image(text, cell=(cw, cw * 2), font_px=cw * 2,
                                  fg=(225, 225, 225), bg=(12, 12, 12)).save(out / f"{base}.png")
    return written
