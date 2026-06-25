"""
Part 2: submit to flaky AMS with retries, idempotency key, and GET confirmation.
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

# Stub hangs ~30s before 503 — timeout must be longer than that
POST_TIMEOUT_SECONDS = 45.0
GET_TIMEOUT_SECONDS = 10.0
MAX_SUBMIT_ATTEMPTS = 10  # cap retries under 3-hour scope


class SubmitOutcome(str, Enum):
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class SubmitResult:
    outcome: SubmitOutcome
    record_id: str | None = None
    message: str = ""
    attempts: int = 0
    log: list[str] = field(default_factory=list)  # what happened each attempt


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = GET_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, str], Any]:
    """Low-level HTTP helper — returns (status_code, headers, body)."""
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
        parsed = raw  # stub sometimes returns broken JSON on purpose

    return status, resp_headers, parsed


def _is_accepted_create_response(body: Any) -> bool:
    """
    Don't trust HTTP 200 alone — body must look like real AMS success.
    Stub returns fake 200s with truncated or wrong JSON.
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
    """
    GET /records/:id — reliable endpoint.
    Proves the record actually landed, not just that POST returned 201.
    """
    url = f"{base_url.rstrip('/')}/api/v1/records/{record_id}"
    status, _, body = _http_json("GET", url, timeout=GET_TIMEOUT_SECONDS)
    return status == 200 and isinstance(body, dict) and body.get("recordId") == record_id


def submit_record(
    record: dict[str, Any],
    idempotency_key: str,
    base_url: str = DEFAULT_BASE_URL,
) -> SubmitResult:
    """
    Retry loop until confirmed or max attempts.
    Same idempotency_key every retry → stub won't create duplicates.
    """
    url = f"{base_url.rstrip('/')}/api/v1/records"
    result = SubmitResult(outcome=SubmitOutcome.FAILED)

    for attempt in range(1, MAX_SUBMIT_ATTEMPTS + 1):
        result.attempts = attempt

        # Same key on every attempt for this email — critical for safe retries
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
            # 429, 422, 503 come back as HTTPError — still have status code
            status = exc.code
            resp_headers = dict(exc.headers)
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {}
        except (urllib.error.URLError, TimeoutError) as exc:
            # Network/timeout — record may or may not have saved; retry with same key
            result.log.append(f"attempt {attempt}: transport error ({exc}) — retrying")
            time.sleep(min(attempt, 3))
            continue

        # --- 429: rate limited — wait exactly as long as stub says ---
        if status == 429:
            retry_after = int(resp_headers.get("Retry-After", "1"))
            result.log.append(f"attempt {attempt}: 429 rate limited — sleep {retry_after}s")
            time.sleep(retry_after)
            continue

        # --- 422: record failed AMS validation — fix prepare step, don't retry forever ---
        if status == 422:
            details = body.get("details", body) if isinstance(body, dict) else body
            result.message = f"AMS validation failed: {details}"
            result.log.append(f"attempt {attempt}: 422 {result.message}")
            return result

        # --- 503/400: stub may have saved record anyway — retry with same key ---
        if status in {503, 400}:
            msg = body.get("message", body) if isinstance(body, dict) else body
            result.log.append(f"attempt {attempt}: {status} ({msg}) — retrying")
            time.sleep(min(attempt, 3))
            continue

        # --- 200 or 201: might be real success OR fake malformed success ---
        if status in {200, 201}:
            if _is_accepted_create_response(body):
                record_id = body["recordId"]
                if confirm_record_exists(record_id, base_url):
                    result.outcome = SubmitOutcome.CONFIRMED
                    result.record_id = record_id
                    result.message = "Record confirmed via GET"
                    result.log.append(
                        f"attempt {attempt}: {status} accepted, GET verified {record_id}"
                    )
                    return result
                # POST looked OK but GET couldn't find it — try again
                result.log.append(
                    f"attempt {attempt}: {status} looked accepted but GET failed — retrying"
                )
                continue

            # 200 with wrong/truncated JSON — stub tests this case
            result.log.append(
                f"attempt {attempt}: {status} with malformed body — retrying"
            )
            time.sleep(1)
            continue

        # Anything else unexpected
        result.log.append(f"attempt {attempt}: unexpected status {status} — retrying")
        time.sleep(1)

    result.message = (
        f"Gave up after {MAX_SUBMIT_ATTEMPTS} attempts. "
        f"Last log: {result.log[-1] if result.log else 'none'}"
    )
    return result
