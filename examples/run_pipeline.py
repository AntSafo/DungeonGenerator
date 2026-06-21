"""End-to-end dungeon pipeline: setting -> room -> layout -> image prompt -> image -> ASCII.

Steps 2/3/5 are driven by the code via generator.llm.call_llm (default backend: local
`claude -p`; set DUNGEON_LLM_BACKEND=api to use the Anthropic API key instead). For each
generated image it emits a 4-way ASCII comparison: {plain, contrast-boosted} x {inverted,
normal}.

Resolution is tunable:
  python examples/run_pipeline.py                 # defaults (640x480, 120-col ASCII)
  python examples/run_pipeline.py --res 1024x768 --cols 200
A too-large --res falls back to the next size that fits the GPU.
"""

import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))

import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageDraw

from generator.creative_agent import build_user_prompt as creative_user
from generator.dungeon_render import to_dungeon_ascii
from generator.ascii_art import render_ascii_to_image
from generator.imageprompt import build_user_prompt as imageprompt_user
from generator.layout_oneshot import apply_placements, build_room_prompt
from generator.layout_oneshot import build_system_prompt as layout_system
from generator.llm import call_llm, extract_json
from generator.local_imagegen import DEFAULT_SCALE, encode_prompt, generate, load_pipeline, to_control
from generator.presets import get_preset
from generator.prompts import load_prompt
from generator.render import save_depth, save_wireframe
from generator.schema import room_from_dict

OUT_ROOT = Path("savedOutputs/pipeline")
DEFAULT_RES = (640, 480)
DEFAULT_COLS = 120
SEED = 42
# Descending sizes to fall back to if a requested resolution runs out of VRAM.
FALLBACK_RES = [(1024, 768), (896, 672), (832, 624), (768, 576), (640, 480), (512, 384)]

SETTINGS = [
    {
        "location": ("the spire of a long-dead plague doctor, atop a collapsed alchemist's "
                     "laboratory gone to dust and mold"),
        "room_type": "alchemist's laboratory",
        "tone": "decayed, claustrophobic, quietly menacing",
        "required_items": ["a distillation apparatus of glassware", "a specimen shelf"],
    },
    {
        "location": "a galleon wrecked on the deep seabed, flooded and silt-choked",
        "room_type": "captain's cabin",
        "tone": "drowned and still, lit by drifting motes and deep-sea glow",
        "required_items": ["a captain's desk", "a sea chest"],
    },
]


def parse_res(text: str) -> tuple[int, int]:
    w, h = text.lower().split("x")
    return int(w), int(h)


def montage(tiles, cols, thumb=(540, 405)):
    pad, labelh = 4, 16
    cw, ch = thumb[0] + 2 * pad, thumb[1] + labelh + 2 * pad
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (25, 25, 25))
    draw = ImageDraw.Draw(sheet)
    for i, (label, img) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = c * cw + pad, r * ch + pad
        draw.text((x, y), label, fill=(235, 235, 235))
        sheet.paste(img.resize(thumb), (x, y + labelh))
    return sheet


def generate_at(pipe, wire_img, res, pos, neg):
    """Generate at `res`, falling back to smaller sizes on out-of-memory."""
    candidates = [res] + [r for r in FALLBACK_RES if r[0] < res[0]]
    for r in candidates:
        try:
            img = generate(pipe, to_control(wire_img, r), prompt_embeds=pos,
                           negative_prompt_embeds=neg, scale=DEFAULT_SCALE, seed=SEED)
            return img, r
        except torch.cuda.OutOfMemoryError:
            print(f"  OOM at {r[0]}x{r[1]}, falling back")
            torch.cuda.empty_cache()
    raise SystemExit("could not generate at any candidate resolution")


def run_one(spec, pipe, res, cols):
    step2_sys = load_prompt("step2_creative_system")
    step3_sys = layout_system()
    step5_sys = load_prompt("step5_imageprompt_system")

    room_obj = extract_json(call_llm(step2_sys, creative_user(
        spec["location"], spec.get("required_items"), spec.get("room_type"), spec.get("tone"))))
    room = room_from_dict(room_obj)
    out = OUT_ROOT / room.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "01_room.json").write_text(json.dumps(room_obj, indent=2), encoding="utf-8")
    print(f"[{room.run_id}] step2 ok ({room.size_preset}, {len(room.objects)} objects)")

    place_obj = extract_json(call_llm(step3_sys, build_room_prompt(room)))
    (out / "02_placements.json").write_text(json.dumps(place_obj, indent=2), encoding="utf-8")
    placed, feedbacks = apply_placements(get_preset(room.size_preset), place_obj)
    bounds = get_preset(room.size_preset).bounds
    wire = save_wireframe(placed, bounds, out / "03_wireframe.png")
    save_depth(placed, bounds, out / "03_depth.png")
    print(f"[{room.run_id}] step3 ok ({len(placed)} regions, "
          f"{len([f for f in feedbacks if f['status'] != 'placed'])} errors)")

    img_prompt = call_llm(step5_sys, imageprompt_user(room, placed))
    (out / "04_imageprompt.txt").write_text(img_prompt, encoding="utf-8")

    pos, neg = encode_prompt(pipe, img_prompt)
    img, used_res = generate_at(pipe, Image.open(wire), res, pos, neg)
    img.save(out / "05_image.png")
    print(f"[{room.run_id}] image generated at {used_res[0]}x{used_res[1]}")

    tiles = []
    for boost in (False, True):
        for invert in (True, False):
            text = to_dungeon_ascii(img, cols=cols, invert=invert, boost=boost)
            tag = f"{'boost' if boost else 'plain'}_{'inv' if invert else 'norm'}"
            (out / f"06_ascii_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            fg, bg = ((225, 225, 225), (12, 12, 12)) if invert else ((20, 20, 20), (245, 245, 245))
            tiles.append((tag, render_ascii_to_image(text, cell=(5, 10), fg=fg, bg=bg)))
    montage(tiles, cols=2).save(out / "06_ascii_compare.png")
    print(f"[{room.run_id}] done -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", type=parse_res, default=DEFAULT_RES, help="image resolution, e.g. 1024x768")
    ap.add_argument("--cols", type=int, default=DEFAULT_COLS, help="ASCII width in characters")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    pipe = load_pipeline("lineart")
    for spec in SETTINGS:
        try:
            run_one(spec, pipe, args.res, args.cols)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
