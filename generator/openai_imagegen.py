"""OpenAI image backend (gpt-image-1) for step 6.

Reads OPENAI_API_KEY from the environment (loaded from .env) - never hardcoded. Sends the
wireframe as a reference image plus a prompt that explains how to read it (see gpt_prompt), so
the model lays the room out from the wireframe instead of inventing positions. The official
`openai` SDK reads the key from the environment automatically.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from dotenv import load_dotenv

MODEL = "gpt-image-1"
DEFAULT_SIZE = "1536x1024"      # landscape, matching the wide-from-the-doorway view
DEFAULT_QUALITY = "high"        # "low" | "medium" | "high" | "auto"


def generate_image(wireframe_path: str | Path, prompt: str, out_path: str | Path, *,
                   size: str = DEFAULT_SIZE, quality: str = DEFAULT_QUALITY, client=None) -> Path:
    """Generate one room image from a wireframe + prompt via gpt-image-1; save it to out_path.

    The wireframe is passed as a reference image and `prompt` should be the full message from
    gpt_prompt.build_chatgpt_message (the wireframe-reading instructions + the room description).
    """
    import openai

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your-key-here":
        raise SystemExit("OPENAI_API_KEY is not set in .env")
    client = client or openai.OpenAI()
    with open(wireframe_path, "rb") as f:
        result = client.images.edit(model=MODEL, image=f, prompt=prompt,
                                    size=size, quality=quality)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(result.data[0].b64_json))
    return out
