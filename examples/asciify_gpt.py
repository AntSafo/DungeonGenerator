"""(Re)generate the 4-resolution ASCII for every ChatGPT-generated image already on disk.

Useful for ASCII-ifying images without regenerating them. Scans:
  - savedOutputs/cc-run/gpt_test.png          -> stem 'gpt_test'
  - savedOutputs/pipeline/<room>/05_gpt_image.png -> stem '05_gpt_image'

    python examples/asciify_gpt.py
"""

import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))

from pathlib import Path

from PIL import Image

from generator.dungeon_render import ASCII_RESOLUTIONS, save_ascii_resolutions


def targets():
    out = []
    test = Path("savedOutputs/cc-run/gpt_test.png")
    if test.exists():
        out.append((test, test.parent, "gpt_test"))
    root = Path("savedOutputs/pipeline")
    if root.exists():
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            img = d / "05_gpt_image.png"
            if img.exists():
                out.append((img, d, "05_gpt_image"))
    return out


def main():
    jobs = targets()
    if not jobs:
        print("No ChatGPT images found yet (run the test or gallery first).")
        return
    cols = ", ".join(f"{v}c" for v in ASCII_RESOLUTIONS) + ", native"
    print(f"{len(jobs)} image(s); resolutions: {cols}")
    for img, out_dir, stem in jobs:
        save_ascii_resolutions(Image.open(img), out_dir, stem)
        print(f"  {img}  ->  {stem}_ascii_*.txt (+ .png previews)")


if __name__ == "__main__":
    main()
