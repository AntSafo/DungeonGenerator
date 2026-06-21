"""Generate a whole SET of varied rooms into one organized folder tree.

Layout (everything for a room - image + every ASCII resolution - lives in its own folder):

    savedOutputs/sets/<set-name>/
        01_castle-throne-room/
            room.json  placements.json  wireframe.png  depth.png  imageprompt.txt
            image.png  image_input.txt
            image_ascii_100c.txt/.png  image_ascii_200c.txt/.png  ...  image_ascii_<native>c.*
        02_dwarven-forge/
            ...

Steps 2/3/5 run via `claude -p`; images are generated with the OpenAI Images API (gpt-image-1,
reads OPENAI_API_KEY from .env). Fully resumable and step-by-step: anything already on disk is
skipped, so you can stop/restart freely.

    python examples/generate_set.py              # generate the whole set
    python examples/generate_set.py --no-image   # just rooms+wireframes+prompts (no image API)
    python examples/generate_set.py --limit 2    # only the first couple
    python examples/generate_set.py --set my-set # name the set folder
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

SETS_ROOT = Path("savedOutputs/sets")

# A spread of locations, room types, tones, and required items. `slug` names the run folder
# (stable, so re-runs resume the same folder). Edit / extend freely.
SPECS = [
    {"slug": "castle-throne-room",
     "location": "a vast, half-ruined medieval castle high in the mountains",
     "room_type": "throne room", "tone": "grand but decaying, cold and long-abandoned",
     "items": ["a treasure chest", "a throne"]},
    {"slug": "dwarven-forge",
     "location": "the deep tunnels of an abandoned dwarven hold",
     "room_type": "forge", "tone": "soot-black, embers still glowing in the dark",
     "items": ["a great anvil", "an ore cart"]},
    {"slug": "wizard-library",
     "location": "the upper floor of a crooked, leaning wizard's tower",
     "room_type": "library study", "tone": "dusty, arcane, moonlit through tall windows",
     "items": ["a spellbook lectern", "a celestial globe"]},
    {"slug": "drowned-crypt",
     "location": "a flooded crypt beneath a sunken cathedral",
     "room_type": "burial vault", "tone": "still black water, cold and sacred",
     "items": ["a stone sarcophagus", "a heap of bones"]},
    {"slug": "pirate-cabin",
     "location": "a galleon run aground on a fog-bound reef",
     "room_type": "captain's cabin", "tone": "salt-rotted, lantern-lit, gently swaying",
     "items": ["a sea chest", "a navigation table"]},
    {"slug": "goblin-kitchen",
     "location": "the filthy warren of a goblin tribe",
     "room_type": "kitchen", "tone": "greasy, cluttered, firelit and foul",
     "items": ["a bubbling cauldron", "a butcher's block"]},
    {"slug": "frozen-shrine",
     "location": "a glacier cave high in a dead god's mountains",
     "room_type": "shrine", "tone": "blue ice, frozen silence, a faint inner glow",
     "items": ["an ice altar", "frozen offerings"]},
    {"slug": "overgrown-temple",
     "location": "a jungle temple swallowed by roots and vines",
     "room_type": "ruined sanctuary", "tone": "humid, green-lit, slowly collapsing",
     "items": ["a vine-choked idol", "a cracked stone altar"]},
]


def _gen_room(run_dir: Path, spec: dict):
    """Step 2 -> a valid room.json. Regenerates once if a stale/invalid file is present."""
    room_json = run_dir / "room.json"
    for _ in range(2):
        if not room_json.exists():
            obj = extract_json(call_llm(load_prompt("step2_creative_system"),
                                        creative_user(spec["location"], spec.get("items"),
                                                      spec.get("room_type"), spec.get("tone"))))
            room_json.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        try:
            return room_from_dict(json.loads(room_json.read_text(encoding="utf-8")))
        except Exception:
            room_json.unlink(missing_ok=True)  # bad file -> regenerate
    raise RuntimeError("could not produce a valid room.json after 2 attempts")


def _gen_wireframe(run_dir: Path, room):
    """Step 3 -> placements + wireframe/depth. Retries once on a bad layout reply."""
    wire = run_dir / "wireframe.png"
    pf = run_dir / "placements.json"
    if wire.exists():
        placed, _ = apply_placements(get_preset(room.size_preset),
                                     json.loads(pf.read_text(encoding="utf-8")))
        return wire, placed
    last = None
    for _ in range(2):
        try:
            obj = extract_json(call_llm(layout_system(), build_room_prompt(room)))
            pf.write_text(json.dumps(obj, indent=2), encoding="utf-8")
            placed, _ = apply_placements(get_preset(room.size_preset), obj)
            bounds = get_preset(room.size_preset).bounds
            save_wireframe(placed, bounds, wire)
            save_depth(placed, bounds, run_dir / "depth.png")
            return wire, placed
        except Exception as e:  # noqa: BLE001
            last, _ = e, pf.unlink(missing_ok=True)
    raise RuntimeError(f"could not produce a valid layout after 2 attempts ({last})")


def prep_room(spec: dict, run_dir: Path):
    """Steps 2/3/5 + wireframe (no image API). Resumable + self-healing per step."""
    run_dir.mkdir(parents=True, exist_ok=True)
    room = _gen_room(run_dir, spec)
    wire, placed = _gen_wireframe(run_dir, room)
    prompt_file = run_dir / "imageprompt.txt"
    if not prompt_file.exists():
        prompt_file.write_text(call_llm(load_prompt("step5_imageprompt_system"),
                                        imageprompt_user(room, placed)), encoding="utf-8")
    return room, wire, prompt_file


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="set-01", help="name of the set folder")
    ap.add_argument("--limit", type=int, default=None, help="only the first N specs")
    ap.add_argument("--no-image", action="store_true", help="prep only (rooms+wireframes), no image API")
    args = ap.parse_args()

    specs = SPECS[: args.limit] if args.limit else SPECS
    base = SETS_ROOT / args.set
    print(f"Set '{args.set}': {len(specs)} room(s) -> {base}")

    # Phase 1: prep every room (claude -p + wireframe). Per-room isolated.
    runs = []
    for i, spec in enumerate(specs, 1):
        run_dir = base / f"{i:02d}_{spec['slug']}"
        try:
            room, wire, prompt_file = prep_room(spec, run_dir)
            runs.append((spec, run_dir, room, wire, prompt_file))
            print(f"  [{i:02d}] {spec['slug']}: prepped ({room.size_preset}, {len(room.objects)} objects)")
        except Exception as e:  # noqa: BLE001 - keep the batch going
            print(f"  [{i:02d}] {spec['slug']}: PREP FAILED ({type(e).__name__}: {e})")

    if args.no_image:
        print("\nPrep done (no images). Re-run without --no-image to render + ASCII.")
        return

    # Phase 2: generate images via gpt-image-1 for any room missing one (per-room isolated).
    for spec, run_dir, room, wire, prompt_file in runs:
        out = run_dir / "image.png"
        if out.exists():
            continue
        try:
            msg = build_chatgpt_message(prompt_file.read_text(encoding="utf-8"))
            (run_dir / "image_input.txt").write_text(
                f"# wireframe: {wire.resolve()}\n\n{msg}", encoding="utf-8")
            generate_image(wire, msg, out)
            print(f"  [{run_dir.name}] image ok")
        except Exception as e:  # noqa: BLE001 - keep the batch going
            print(f"  [{run_dir.name}] IMAGE FAILED ({type(e).__name__}: {e})")

    # Phase 3: ASCII (all resolutions) for any room with an image but no ASCII yet.
    for spec, run_dir, room, wire, prompt_file in runs:
        out = run_dir / "image.png"
        if out.exists() and not (run_dir / "image_ascii_100c.txt").exists():
            save_ascii_resolutions(Image.open(out), run_dir, "image")
    print(f"\nDone -> {base}")


if __name__ == "__main__":
    main()
