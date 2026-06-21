"""LLM call backend for steps 2/3/5.

Two backends, chosen by env var DUNGEON_LLM_BACKEND (default "claudecode"):
  - "claudecode": shell out to the local `claude -p` CLI (no API key needed).
  - "api": use the Anthropic SDK with ANTHROPIC_API_KEY from .env.
The code makes the call either way — callers just use `call_llm(system, user)`.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

API_MODEL = "claude-opus-4-8"
CC_MODEL = "opus"   # claude -p model alias


def call_llm(system_prompt: str, user_message: str, *, backend: str | None = None,
             model: str | None = None) -> str:
    load_dotenv()
    backend = (backend or os.getenv("DUNGEON_LLM_BACKEND", "claudecode")).lower()
    if backend == "api":
        return _call_api(system_prompt, user_message, model or API_MODEL)
    if backend == "claudecode":
        return _call_claude_code(system_prompt, user_message, model or CC_MODEL)
    raise ValueError(f"unknown DUNGEON_LLM_BACKEND {backend!r} (use 'claudecode' or 'api')")


def _call_api(system: str, user: str, model: str) -> str:
    import anthropic

    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") == "your-key-here":
        raise SystemExit("DUNGEON_LLM_BACKEND=api but ANTHROPIC_API_KEY is not set in .env")
    client = anthropic.Anthropic()
    resp = client.messages.create(model=model, max_tokens=16000, system=system,
                                  messages=[{"role": "user", "content": user}])
    return next(b.text for b in resp.content if b.type == "text").strip()


def _call_claude_code(system: str, user: str, model: str) -> str:
    tmp = Path(tempfile.gettempdir()) / f"dg_sys_{os.getpid()}.txt"
    tmp.write_text(system, encoding="utf-8")
    try:
        cmd = (f'claude -p --system-prompt-file "{tmp}" --exclude-dynamic-system-prompt-sections '
               f'--output-format text --model {model}')
        r = subprocess.run(cmd, input=user, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", shell=True)
        if r.returncode != 0:
            raise RuntimeError(f"claude -p failed ({r.returncode}): {(r.stderr or '')[-400:]}")
        return r.stdout.strip()
    finally:
        tmp.unlink(missing_ok=True)


def strip_fences(text: str) -> str:
    """Strip ```...``` fences if a model wrapped its output despite instructions."""
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 3:
            t = parts[1]
            if t.lstrip().lower().startswith("json"):
                t = t.lstrip()[4:]
    return t.strip()


def extract_json(text: str):
    """Parse the JSON object/array from a model reply, tolerating fences and a chatty
    preamble/trailer (e.g. "I'll design this now.\\n\\n{...}"). Returns the parsed object."""
    import json

    t = strip_fences(text)
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        raise ValueError(f"no JSON object found in model output: {t[:120]!r}")
    obj, _ = json.JSONDecoder().raw_decode(t[min(starts):])  # ignores any trailing text
    return obj
