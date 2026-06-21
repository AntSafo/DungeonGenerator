"""Step 2 - Creative pass prompts.

Given a location, optionally the kind of room and a tonal note, and optionally a few items
the room must contain, Claude invents one original room and emits a full room.json (the schema
in docs/room-schema.md) so the output validates with generator.schema and feeds step 3
directly. The creative pass fills in everything else and adds objects beyond the required ones
so the room feels complete. `run_creative` makes the live call (not tested); the prompt
builders are unit-tested and used to produce text for manual runs.
"""

from __future__ import annotations

import json

from dotenv import load_dotenv

from generator.prompts import load_prompt

MODEL = "claude-opus-4-8"


def build_system_prompt() -> str:
    return load_prompt("step2_creative_system")


def build_user_prompt(location: str, required_items: list[str] | None = None,
                      room_type: str | None = None, tone: str | None = None) -> str:
    """Inputs for the creative pass.

    - location: where the room is (e.g. "a vast medieval castle"). Required.
    - required_items: things the room MUST contain (a starting point, not the full list).
    - room_type: what the room is (e.g. "throne room"); invented if omitted.
    - tone: a brief tonal/mood note; chosen to fit if omitted.
    """
    payload: dict = {"location": location}
    if room_type:
        payload["roomType"] = room_type
    if tone:
        payload["tone"] = tone
    if required_items:
        payload["requiredItems"] = list(required_items)
    return ('Design one room for this input. Copy these inputs verbatim into the output\'s '
            '"input" field, then produce the full room JSON. Include EVERY requiredItem as an '
            "object, and add more objects so the room feels complete (see the system prompt's "
            "FULLNESS rule).\n\n" + json.dumps(payload, indent=2))


def run_creative(location: str, required_items: list[str] | None = None,
                 room_type: str | None = None, tone: str | None = None, client=None):
    """Live creative pass -> validated Room. Not exercised by tests (spends tokens)."""
    import anthropic

    from generator.schema import room_from_dict

    load_dotenv()
    client = client or anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=build_system_prompt(),
        messages=[{"role": "user",
                   "content": build_user_prompt(location, required_items, room_type, tone)}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return room_from_dict(json.loads(text))
