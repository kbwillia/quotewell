"""
Prepare AMS record from email: extract → parse → normalize → validate.

Output is either READY (submit to AMS) or NEEDS_REVIEW (blocking errors).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pipeline.extract_client import call_extract_service
from pipeline.normalize_fields import normalize_parsed_record
from pipeline.parse_model_output import parse_model_output
from pipeline.source_validation import apply_source_validation, validate_record_completeness


class RecordStatus(str, Enum):
    READY = "ready"  # safe to submit to AMS
    NEEDS_REVIEW = "needs_review"  # blocking errors — do not submit


@dataclass
class PreparedRecordResult:
    """Holds every stage's output for one email (auditable trail)."""

    source_file: str
    model_name: str | None = None
    raw_model_output: str = ""  # exact string from /extract "output" field
    parsed_raw: dict[str, Any] | None = None  # after parse_model_output
    normalized_draft: dict[str, Any] | None = None  # after normalize_fields
    final_record: dict[str, Any] | None = None  # after source_validation
    status: RecordStatus = RecordStatus.NEEDS_REVIEW
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_display_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "status": self.status.value,
            "model": self.model_name,
            "warnings": self.warnings,
            "errors": self.errors,
            "final_record": self.final_record,
        }


def process_email_file(
    email_path: Path,
    base_url: str = "http://localhost:8472",
) -> PreparedRecordResult:
    result = PreparedRecordResult(source_file=email_path.name)

    # Read the broker email from disk
    source_email = email_path.read_text(encoding="utf-8")

    # --- Step 1: POST /extract (assignment requires this path) ---
    try:
        extract_response = call_extract_service(source_email, base_url=base_url)
    except (ConnectionError, ValueError) as exc:
        result.errors.append(str(exc))
        return result

    result.model_name = extract_response.get("model")
    result.raw_model_output = extract_response["output"]

    # --- Step 2: parse messy string → dict ---
    try:
        parsed = parse_model_output(result.raw_model_output)
    except ValueError as exc:
        result.errors.append(f"Parse failed: {exc}")
        return result

    result.parsed_raw = parsed

    # --- Step 3: fix formats (state, dates, LOB, money) ---
    normalized = normalize_parsed_record(parsed)
    result.normalized_draft = normalized

    # --- Step 4: broker email overrides model mistakes ---
    validated, warnings, source_errors = apply_source_validation(source_email, normalized)
    result.warnings.extend(warnings)
    result.errors.extend(source_errors)

    # --- Step 5: ensure all required AMS fields present ---
    completeness_errors = validate_record_completeness(validated)
    result.errors.extend(completeness_errors)

    result.final_record = validated

    # No errors at all → ready for AMS submit
    if not result.errors:
        result.status = RecordStatus.READY

    return result


def process_inbox(
    inbox_dir: Path,
    base_url: str = "http://localhost:8472",
) -> list[PreparedRecordResult]:
    paths = sorted(inbox_dir.glob("*.txt"))
    return [process_email_file(path, base_url=base_url) for path in paths]
