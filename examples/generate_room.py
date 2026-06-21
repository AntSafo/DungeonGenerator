"""End-to-end from the NEW creative input -> room -> wireframe -> image -> ASCII.

You describe the room at a high level and the creative pass invents the rest (always adding
objects beyond the ones you require). Steps 2/3/5 run via `claude -p`; the image is generated
with the OpenAI Images API (gpt-image-1), which reads OPENAI_API_KEY from .env.

    python examples/generate_room.py --location "a vast medieval castle" ^
        --room-type "throne room" --tone "grand but decaying" ^
        --items "a treasure chest, a throne"

Only --location is required. Use --no-image to stop after the wireframe + prompt. Output lands
in savedOutputs/pipeline/<run>/.
"""

import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent))

import argparse
import json
from pathlib import Path

from PIL import Image

from generator.creative_agent import build_user_prompt as creative_user
from generator.dungeon_render import save_ascii_resolutions
from generator.gpt_prompt import build_chatgpt_message
from generator.imageprompt import build_user_prompt as imageprompt_user
from generator.layout_oneshot import apply_placements, build_room_prompt
from generator.layout_oneshot import build_system_prompt as layout_system
from generator.llm import call_llm, extract_json
from generator.openai_imagegen import generate_image
from generator.presets import get_preset
from generator.prompts import load_prompt
from generator.render import save_depth, save_wireframe
from generator.schema import room_from_dict

OUT_ROOT = Path("savedOutputs/pipeline")


def parse_items(text: str | None) -> list[str]:
    if not text:
        return []
    return [s.strip() for s in text.split(",") if s.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--location", required=True, help="where the room is, e.g. 'a vast medieval castle'")
    ap.add_argument("--items", help="comma-separated items the room MUST contain")
    ap.add_argument("--room-type", help="what the room is, e.g. 'throne room' (optional)")
    ap.add_argument("--tone", help="brief tonal/mood note (optional)")
    ap.add_argument("--no-image", action="store_true", help="stop after wireframe + prompt")
    args = ap.parse_args()

    # Step 2 - creative pass (new input model).
    room_obj = extract_json(call_llm(
        load_prompt("step2_creative_system"),
        creative_user(args.location, parse_items(args.items), args.room_type, args.tone)))
    room = room_from_dict(room_obj)
    out = OUT_ROOT / room.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "01_room.json").write_text(json.dumps(room_obj, indent=2), encoding="utf-8")
    print(f"[{room.run_id}] step2 ok ({room.size_preset}, {len(room.objects)} objects)")

    # Step 3 - layout -> wireframe + depth.
    place_obj = extract_json(call_llm(layout_system(), build_room_prompt(room)))
    (out / "02_placements.json").write_text(json.dumps(place_obj, indent=2), encoding="utf-8")
    placed, feedbacks = apply_placements(get_preset(room.size_preset), place_obj)
    bounds = get_preset(room.size_preset).bounds
    wire = save_wireframe(placed, bounds, out / "03_wireframe.png")
    save_depth(placed, bounds, out / "03_depth.png")
    errs = len([f for f in feedbacks if f["status"] != "placed"])
    print(f"[{room.run_id}] step3 ok ({len(placed)} regions, {errs} errors)")

    # Step 5 - image prompt (+ wireframe-reading preamble for the image model).
    img_prompt = call_llm(load_prompt("step5_imageprompt_system"), imageprompt_user(room, placed))
    (out / "04_imageprompt.txt").write_text(img_prompt, encoding="utf-8")

    if args.no_image:
        print(f"[{room.run_id}] prepared (no image) -> {out}")
        return

    # Step 6 - generate the image with gpt-image-1 (+ save the exact input used).
    msg = build_chatgpt_message(img_prompt)
    (out / "05_gpt_input.txt").write_text(f"# wireframe: {wire.resolve()}\n\n{msg}", encoding="utf-8")
    generate_image(wire, msg, out / "05_gpt_image.png")
    print(f"[{room.run_id}] image generated")

    # Steps 7/8 - ASCII at all resolutions.
    save_ascii_resolutions(Image.open(out / "05_gpt_image.png"), out, "05_gpt_image")
    print(f"[{room.run_id}] done -> {out}  (image, input, ASCII)")


if __name__ == "__main__":
    main()
