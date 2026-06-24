"""
End-to-end pipeline: Part 1 (extract/normalize) + Part 2 (AMS submit/confirm).

One function per email; one list for the full inbox run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pipeline.ams_client import SubmitOutcome, SubmitResult, submit_record
from pipeline.extract_client import DEFAULT_BASE_URL
from pipeline.part1 import Part1Result, RecordStatus, process_email_file


class PipelineStatus(str, Enum):
    CONFIRMED = "confirmed"  # In AMS, verified by GET
    NEEDS_REVIEW = "needs_review"  # Part 1 blocked submission (e.g. missing date)
    FAILED = "failed"  # Was ready but AMS submit could not confirm


@dataclass
class PipelineResult:
    source_file: str
    status: PipelineStatus
    record_id: str | None = None
    part1: Part1Result | None = None
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
    """
    Stable key per inbox file — survives retries without duplicate AMS rows.

    Using the filename (not record content) keeps the key stable even if we
    tweak normalization between attempts during development.
    """
    return f"quotewell-{email_path.name}"


def run_email(email_path: Path, base_url: str = DEFAULT_BASE_URL) -> PipelineResult:
    """Full pipeline for one email file."""
    part1 = process_email_file(email_path, base_url=base_url)

    result = PipelineResult(
        source_file=email_path.name,
        status=PipelineStatus.FAILED,
        part1=part1,
        warnings=list(part1.warnings),
        errors=list(part1.errors),
    )

    # Part 1 blocked — report clearly, do not submit (governability).
    if part1.status != RecordStatus.READY or not part1.final_record:
        result.status = PipelineStatus.NEEDS_REVIEW
        result.message = "; ".join(part1.errors) or "Record not ready for submission"
        return result

    # Part 2: submit + confirm
    submit = submit_record(
        part1.final_record,
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
