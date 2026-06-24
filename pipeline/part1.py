"""
Part 1 orchestration: email file → extract → parse → normalize → source-validate.

This module ties together the full "messy text cleanup" pipeline. Part 2
(AMS submission with retries) will consume Part1Result.ready_record when
status is READY.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pipeline.extract_client import call_extract_service
from pipeline.normalize_fields import normalize_parsed_record
from pipeline.parse_model_output import parse_model_output
from pipeline.source_validation import apply_source_validation, validate_record_completeness


class RecordStatus(str, Enum):
    """Whether the cleaned record is safe to hand to Part 2 (AMS submit)."""

    READY = "ready"  # All required fields present; defensible against source email.
    NEEDS_REVIEW = "needs_review"  # Parsed but blocking errors — do not submit silently.


@dataclass
class Part1Result:
    """Everything Part 1 produces for one inbox email — auditable end-to-end."""

    source_file: str
    model_name: str | None = None
    raw_model_output: str = ""
    parsed_raw: dict[str, Any] | None = None
    normalized_draft: dict[str, Any] | None = None
    final_record: dict[str, Any] | None = None
    status: RecordStatus = RecordStatus.NEEDS_REVIEW
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_display_dict(self) -> dict[str, Any]:
        """JSON-serializable summary for CLI output / debugging."""
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
) -> Part1Result:
    """
    Run the full Part 1 pipeline for one file in inbox/.

    Flow mirrors QuoteWell's Terminal triage (company.md):
      unstructured email → extraction → structured record → validation
    """
    result = Part1Result(source_file=email_path.name)
    source_email = email_path.read_text(encoding="utf-8")

    # --- Call /extract (required — no hand transcription) ------------------
    try:
        extract_response = call_extract_service(source_email, base_url=base_url)
    except (ConnectionError, ValueError) as exc:
        result.errors.append(str(exc))
        return result

    result.model_name = extract_response.get("model")
    result.raw_model_output = extract_response["output"]

    # --- Parse raw model text → dict ---------------------------------------
    try:
        parsed = parse_model_output(result.raw_model_output)
    except ValueError as exc:
        result.errors.append(f"Parse failed: {exc}")
        return result

    result.parsed_raw = parsed

    # --- Normalize field formats (syntax, not truth) -----------------------
    normalized = normalize_parsed_record(parsed)
    result.normalized_draft = normalized

    # --- Source validation (truth / governability) -------------------------
    validated, warnings, source_errors = apply_source_validation(source_email, normalized)
    result.warnings.extend(warnings)
    result.errors.extend(source_errors)

    # --- Schema completeness check -----------------------------------------
    completeness_errors = validate_record_completeness(validated)
    result.errors.extend(completeness_errors)

    result.final_record = validated

    if not result.errors:
        result.status = RecordStatus.READY

    return result


def process_inbox(
    inbox_dir: Path,
    base_url: str = "http://localhost:8472",
) -> list[Part1Result]:
    """Process every .txt file in inbox/ in sorted order."""
    paths = sorted(inbox_dir.glob("*.txt"))
    return [process_email_file(path, base_url=base_url) for path in paths]
