"""
Glue layer: prepare record from email → AMS submit → final status per email.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pipeline.ams_client import SubmitOutcome, SubmitResult, submit_record
from pipeline.extract_client import DEFAULT_BASE_URL
from pipeline.prepare_record import PreparedRecordResult, RecordStatus, process_email_file


class PipelineStatus(str, Enum):
    CONFIRMED = "confirmed"  # in AMS, GET verified
    NEEDS_REVIEW = "needs_review"  # prepare step blocked (e.g. Tula)
    FAILED = "failed"  # was ready but AMS never confirmed


@dataclass
class PipelineResult:
    source_file: str
    status: PipelineStatus
    record_id: str | None = None
    prepared: PreparedRecordResult | None = None
    submit: SubmitResult | None = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_display_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "status": self.status.value,
            "record_id": self.record_id,
            "message": self.message,
            "warnings": self.warnings,
            "errors": self.errors,
            "submit_attempts": self.submit.attempts if self.submit else 0,
        }


def _idempotency_key(email_path: Path) -> str:
    # One stable key per inbox file — same key on every retry for that email
    return f"quotewell-{email_path.name}"


def run_email(email_path: Path, base_url: str = DEFAULT_BASE_URL) -> PipelineResult:
    # --- Prepare: extract, parse, normalize, validate ---
    prepared = process_email_file(email_path, base_url=base_url)

    result = PipelineResult(
        source_file=email_path.name,
        status=PipelineStatus.FAILED,  # default; updated below
        prepared=prepared,
        warnings=list(prepared.warnings),
        errors=list(prepared.errors),
    )

    # Blocking errors → don't submit, report needs_review
    if prepared.status != RecordStatus.READY or not prepared.final_record:
        result.status = PipelineStatus.NEEDS_REVIEW
        result.message = "; ".join(prepared.errors) or "Record not ready for submission"
        return result

    # --- Submit: POST /records with retries + GET confirm ---
    submit = submit_record(
        prepared.final_record,
        idempotency_key=_idempotency_key(email_path),
        base_url=base_url,
    )
    result.submit = submit

    if submit.outcome == SubmitOutcome.CONFIRMED:
        result.status = PipelineStatus.CONFIRMED
        result.record_id = submit.record_id
        result.message = submit.message
    else:
        result.status = PipelineStatus.FAILED
        result.message = submit.message
        result.errors.append(submit.message)

    return result


def run_inbox(inbox_dir: Path, base_url: str = DEFAULT_BASE_URL) -> list[PipelineResult]:
    paths = sorted(inbox_dir.glob("*.txt"))
    return [run_email(path, base_url=base_url) for path in paths]
