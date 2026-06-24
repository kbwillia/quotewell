"""
HTTP client for the local stub's extraction service.

Part 1 must call POST /api/v1/extract — README forbids hand-transcribing emails.
We use stdlib urllib so there are zero pip dependencies for the take-home.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8472"


def call_extract_service(
    email_text: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """
    POST raw email text to /api/v1/extract and return the full JSON response.

    The extraction service is reliable (unlike the AMS) — we expect HTTP 200
    with {"model": "...", "output": "<raw model text>"}.
    """
    url = f"{base_url.rstrip('/')}/api/v1/extract"
    body = json.dumps({"email": email_text}).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Could not reach extraction service at {url}. "
            "Is the stub running? (node stub/server.js)"
        ) from exc

    if "output" not in payload:
        raise ValueError(f"Unexpected extract response (missing 'output'): {payload}")

    return payload
