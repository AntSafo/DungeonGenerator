"""Wrap a step-5 image prompt with instructions that teach ChatGPT how to read the wireframe.

The local SD pipeline fed the wireframe to ControlNet (pure line geometry) and was capped at
77 tokens. A chat model has no such cap and can be *told* what the wireframe means, so we
prepend a plain-language explanation of the layout guide before the room description.
"""

from __future__ import annotations

WIREFRAME_PREAMBLE = """\
Generate ONE finished, photorealistic, atmospheric image of a single dark-fantasy dungeon room, viewed from its doorway.

The attached picture is a WIREFRAME LAYOUT GUIDE produced by a 3D engine. It is NOT art to copy or stylize - it is a map of where things go:
- The outer lines are the room's walls, floor, and ceiling seen from the doorway (one-point perspective, looking straight in).
- Each smaller box marks the position, footprint, and rough size of one object in the room.
- The camera angle, proportions, and the relative position of every object in your image must match this guide.

Hard rules:
- Do NOT draw the wireframe lines, boxes, grid, or any 3D-render / CAD look in the final image. Render a believable, lived-in room in those positions instead.
- Cover the walls, floor, and ceiling with the materials described below, and place each described object where its box sits in the guide.
- One single image. No text, captions, labels, watermarks, or borders.

Render the room described here:

"""


def build_chatgpt_message(image_prompt: str) -> str:
    """Full message to paste/send: wireframe instructions + the room's image prompt."""
    return WIREFRAME_PREAMBLE + image_prompt.strip() + "\n"
