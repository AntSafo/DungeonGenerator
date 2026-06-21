"""Tests for the LLM output parsing helpers (no API/CLI calls)."""

import pytest

from generator.llm import extract_json, strip_fences


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_tolerates_preamble_and_trailer():
    # The real failure: claude -p prepended a chatty sentence before the JSON.
    text = 'I\'ll design this throne room now.\n\n{"runId": "x", "n": 2}\n\nDone!'
    assert extract_json(text) == {"runId": "x", "n": 2}


def test_extract_json_handles_fences():
    assert extract_json("```json\n{\"a\": [1, 2]}\n```") == {"a": [1, 2]}


def test_extract_json_array():
    assert extract_json("here:\n[1, 2, 3]") == [1, 2, 3]


def test_extract_json_raises_without_json():
    with pytest.raises(ValueError):
        extract_json("no json here at all")


def test_strip_fences_unwraps_json_block():
    assert strip_fences("```json\n{\"x\": 1}\n```") == '{"x": 1}'
