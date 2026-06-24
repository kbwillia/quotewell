"""
Step 1 of Part 1: pull structured data out of raw model *text*.

The /extract endpoint returns prose, markdown fences, or bare JSON — not a
guaranteed schema. QuoteWell's real Alby/Terminal pipeline has the same problem:
the model's job is to get you close; your code must parse defensively.

See company.md: "LLM output is raw — may be wrapped in prose/markdown..."
"""

from __future__ import annotations

import json
import re
from typing import Any


def parse_model_output(raw_text: str) -> dict[str, Any]:
    """
    Turn the `output` field from POST /extract into a Python dict.

    Strategy (in order — first success wins):
      1. Parse the entire string as JSON (works for email_2, _3, _4 stub output).
      2. Extract a ```json ... ``` fenced block (works for email_1 stub output).
      3. Find the first balanced `{ ... }` object in the text (last-resort fallback).

    Raises ValueError if no JSON object can be recovered — that is a hard failure
    we would route to human review in production (Joey's "red zone" — don't guess).
    """
    text = raw_text.strip()
    if not text:
        raise ValueError("Model output was empty")

    # --- Attempt 1: whole string is JSON ---------------------------------
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass  # Expected for markdown-wrapped responses; try next strategy.

    # --- Attempt 2: markdown code fence ----------------------------------
    # Pattern matches ```json ... ``` or generic ``` ... ``` blocks.
    fence_pattern = re.compile(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    fence_match = fence_pattern.search(text)
    if fence_match:
        return _loads_object(fence_match.group(1), context="markdown code fence")

    # --- Attempt 3: first balanced JSON object in free text --------------
    start = text.find("{")
    if start != -1:
        candidate = _extract_balanced_object(text, start)
        if candidate:
            return _loads_object(candidate, context="inline JSON object")

    raise ValueError(
        "Could not find a JSON object in model output. "
        "Would flag for human review rather than invent fields."
    )


def _loads_object(json_str: str, context: str) -> dict[str, Any]:
    """Parse JSON and enforce that the top-level value is an object (dict)."""
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {context}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object in {context}, got {type(parsed).__name__}")

    return parsed


def _extract_balanced_object(text: str, start: int) -> str | None:
    """
    Walk characters from `start` (at '{') and return the substring through the
    matching '}'. Handles nested braces so we don't truncate nested objects.
    """
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None  # Unbalanced — malformed model output.
