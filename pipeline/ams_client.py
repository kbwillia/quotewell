"""
Part 2: submit cleaned records to the unreliable AMS and confirm they landed.

Priorities under the 3-hour cap (per README):
  - Idempotency-Key on every POST (safe retries)
  - Retry 429 / 503 / timeouts / fake 200 responses
  - Never treat HTTP status alone as success — validate body, then GET confirm

Uses stdlib urllib only (no pip dependencies).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pipeline.extract_client import DEFAULT_BASE_URL

# Stub can hang ~30s before 503; read timeout must exceed that.
POST_TIMEOUT_SECONDS = 45.0
GET_TIMEOUT_SECONDS = 10.0
MAX_SUBMIT_ATTEMPTS = 10


class SubmitOutcome(str, Enum):
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class SubmitResult:
    """Auditable result for one AMS submission attempt chain."""

    outcome: SubmitOutcome
    record_id: str | None = None
    message: str = ""
    attempts: int = 0
    log: list[str] = field(default_factory=list)


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = GET_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, str], Any]:
    """
    Issue an HTTP request and parse JSON response body when possible.

    Returns (status_code, response_headers, parsed_body_or_raw_text).
    Raises on connection errors (caller retries).
    """
    data = None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        resp_headers = dict(response.headers)
        status = response.status

    try:
        parsed: Any = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = raw

    return status, resp_headers, parsed


def _is_accepted_create_response(body: Any) -> bool:
    """
    True only for a well-formed AMS success payload.

    README: a 200 does not necessarily mean what you think — truncated JSON
    and wrong shapes are simulated by the stub.
    """
    if not isinstance(body, dict):
        return False
    record_id = body.get("recordId")
    status = body.get("status")
    return (
        isinstance(record_id, str)
        and record_id.startswith("AMS-")
        and status == "accepted"
    )


def confirm_record_exists(record_id: str, base_url: str) -> bool:
    """GET /api/v1/records/:id — reliable confirmation endpoint."""
    url = f"{base_url.rstrip('/')}/api/v1/records/{record_id}"
    status, _, body = _http_json("GET", url, timeout=GET_TIMEOUT_SECONDS)
    return status == 200 and isinstance(body, dict) and body.get("recordId") == record_id


def submit_record(
    record: dict[str, Any],
    idempotency_key: str,
    base_url: str = DEFAULT_BASE_URL,
) -> SubmitResult:
    """
    POST record to AMS with retries until confirmed or attempts exhausted.

    idempotency_key must be stable per logical record (e.g. source filename).
    Same key on retry returns the original record instead of a duplicate.
    """
    url = f"{base_url.rstrip('/')}/api/v1/records"
    result = SubmitResult(outcome=SubmitOutcome.FAILED)

    for attempt in range(1, MAX_SUBMIT_ATTEMPTS + 1):
        result.attempts = attempt
        headers = {"Idempotency-Key": idempotency_key}

        try:
            status, resp_headers, body = _http_json(
                "POST",
                url,
                body=record,
                headers=headers,
                timeout=POST_TIMEOUT_SECONDS,
            )
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = dict(exc.headers)
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {}
        except (urllib.error.URLError, TimeoutError) as exc:
            result.log.append(f"attempt {attempt}: transport error ({exc}) — retrying")
            time.sleep(min(attempt, 3))
            continue

        # --- 429 rate limit: honor Retry-After ---------------------------
        if status == 429:
            retry_after = int(resp_headers.get("Retry-After", "1"))
            result.log.append(f"attempt {attempt}: 429 rate limited — sleep {retry_after}s")
            time.sleep(retry_after)
            continue

        # --- 422 validation: fix upstream, don't spin forever ------------
        if status == 422:
            details = body.get("details", body) if isinstance(body, dict) else body
            result.message = f"AMS validation failed: {details}"
            result.log.append(f"attempt {attempt}: 422 {result.message}")
            return result

        # --- 503 / 400: may have persisted anyway — retry with same key --
        if status in {503, 400}:
            msg = body.get("message", body) if isinstance(body, dict) else body
            result.log.append(f"attempt {attempt}: {status} ({msg}) — retrying")
            time.sleep(min(attempt, 3))
            continue

        # --- 201 or suspicious 200: validate body shape ------------------
        if status in {200, 201}:
            if _is_accepted_create_response(body):
                record_id = body["recordId"]
                if confirm_record_exists(record_id, base_url):
                    result.outcome = SubmitOutcome.CONFIRMED
                    result.record_id = record_id
                    result.message = "Record confirmed via GET"
                    result.log.append(f"attempt {attempt}: {status} accepted, GET verified {record_id}")
                    return result
                result.log.append(
                    f"attempt {attempt}: {status} looked accepted but GET failed — retrying"
                )
                continue

            result.log.append(
                f"attempt {attempt}: {status} with malformed body — retrying"
            )
            time.sleep(1)
            continue

        # --- Unexpected status -------------------------------------------
        result.log.append(f"attempt {attempt}: unexpected status {status} — retrying")
        time.sleep(1)

    result.message = (
        f"Gave up after {MAX_SUBMIT_ATTEMPTS} attempts. "
        f"Last log: {result.log[-1] if result.log else 'none'}"
    )
    return result
