"""Load prompt text from docs/prompts/ so prompts live in editable files, not code.

A prompt file may contain {{SENTINEL}} placeholders filled via keyword args to
`load_prompt`. Any leftover {{...}} after substitution is an error (a missing fill).
Single braces (e.g. JSON examples) are left untouched.
"""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "prompts"


def load_prompt(name: str, **subs: str) -> str:
    text = (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    for key, value in subs.items():
        text = text.replace("{{" + key + "}}", value)
    if "{{" in text:
        snippet = text[text.index("{{"): text.index("{{") + 40]
        raise ValueError(f"unfilled placeholder in prompt '{name}': {snippet!r}")
    return text.rstrip("\n")
