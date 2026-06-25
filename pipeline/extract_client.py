"""
Calls POST /api/v1/extract — required first step (no hand-transcribing emails).
"""

from __future__ import annotations # this: lets us use type hints in python 3.7+

import json
import urllib.error
import urllib.request
from typing import Any

# Where the stub listens when you run: node stub/server.js
DEFAULT_BASE_URL = "http://localhost:8472"


def call_extract_service(
    email_text: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """
    Send raw email text to the fake LLM endpoint.
    Returns {"model": "qw-extract-1", "output": "<messy string>"}.
    """
    url = f"{base_url.rstrip('/')}/api/v1/extract"

    # Body must match README: {"email": "<raw email text>"}
    body = json.dumps({"email": email_text}).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            # Parse the HTTP response body as JSON
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        # Stub not running or wrong port
        raise ConnectionError(
            f"Could not reach extraction service at {url}. "
            "Is the stub running? (node stub/server.js)"
        ) from exc

    # We need the "output" key — that's the messy model text to parse next
    if "output" not in payload:
        raise ValueError(f"Unexpected extract response (missing 'output'): {payload}")

    return payload
