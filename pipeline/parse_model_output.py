"""
Step 2 after /extract: turn messy model TEXT into a Python dict.
"""

import json
import re
from typing import Any


def parse_model_output(raw_text: str) -> dict[str, Any]:
    """
    The model returns a string, not guaranteed JSON.
    Try multiple strategies until we get a dict.
    """
    text = raw_text.strip()
    if not text:
        raise ValueError("Model output was empty")

    # --- Strategy 1: entire string is JSON (emails 2, 3, 4) ---
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass  # not bare JSON — try markdown fence next

    # --- Strategy 2: JSON inside ```json ... ``` (email 1) ---
    fence_pattern = re.compile(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    fence_match = fence_pattern.search(text)
    if fence_match:
        # group(1) is the JSON object inside the code fence
        return _loads_object(fence_match.group(1), context="markdown code fence")

    # --- Strategy 3: find first { ... } with matching braces ---
    start = text.find("{")
    if start != -1:
        candidate = _extract_balanced_object(text, start)
        if candidate:
            return _loads_object(candidate, context="inline JSON object")

    # Can't recover structure — fail loudly, don't invent fields
    raise ValueError(
        "Could not find a JSON object in model output. "
        "Would flag for human review rather than invent fields."
    )


def _loads_object(json_str: str, context: str) -> dict[str, Any]:
    """Parse a JSON string and require top-level object (dict)."""
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {context}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object in {context}, got {type(parsed).__name__}")

    return parsed


def _extract_balanced_object(text: str, start: int) -> str | None:
    """
    Walk from opening '{' until matching '}'.
    Tracks string literals so braces inside "..." don't confuse us.
    """
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            # Inside "quoted string" — ignore { and } for depth counting
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
                # Found the closing brace for the object that started at `start`
                return text[start : index + 1]

    return None  # unclosed braces — malformed output
