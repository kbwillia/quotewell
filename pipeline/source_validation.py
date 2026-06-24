"""
Step 3 of Part 1: cross-check normalized model output against the source email.

This is the governability layer QuoteWell cares about (see audience.md):
  - Who is the AI acting for? → the broker's email, not the model.
  - What happens when the model is wrong? → override, warn, or block submission.

We do NOT blindly trust /extract output. Real retail submissions (company.md)
include mid-thread corrections, TBD fields, and explicit mailing-address rules.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Source-email pattern detectors
# ---------------------------------------------------------------------------


def _revenue_marked_unknown_in_source(email_text: str) -> bool:
    """
    Detect when the broker explicitly says revenue is unknown / TBD.

    email_2.txt: "revenue is TBD — don't hold the submission for it"
    The stub model still returns annualRevenue: 850000 — that is a hallucination
    we must reject (README: do not guess).
    """
    lowered = email_text.lower()
    patterns = (
        r"revenue\s+is\s+tbd",
        r"revenue\s+tbd",
        r"financials?\s+(?:is|are)\s+tbd",
        r"revenue\s+(?:is\s+)?unknown",
        r"don't hold the submission for it",  # paired with TBD in sample email
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _effective_date_not_confirmed_in_source(email_text: str) -> bool:
    """
    Detect when effective date is explicitly not finalized.

    email_4.txt: owner "hasn't locked it in yet" — stub model still returns
    effectiveDate: 2026-07-01. Submitting that would be indefensible.
    """
    lowered = email_text.lower()
    patterns = (
        r"hasn't locked it in",
        r"has not locked it in",
        r"hasn't confirmed",
        r"once the owner confirms",
        r"deciding between a couple of options",
        r"get you the requested effective date once",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _extract_po_box_mailing_address(email_text: str) -> dict[str, str] | None:
    """
    Pull PO Box mailing address when the email insists mail goes to a PO Box.

    email_3.txt: facility at 880 Frontage Rd but "mailing addres is the po box"
    Stub model returns the facility street — wrong for AMS mailingAddress field.
    """
    # Match: PO Box 1142, Bend, OR 97709 (flexible spacing/casing)
    match = re.search(
        r"po\s*\.?\s*box\s+(\d+)\s*,\s*([^,]+)\s*,\s*([A-Za-z]{2})\s+(\d{5})",
        email_text,
        re.IGNORECASE,
    )
    if not match:
        return None

    box_number, city, state, zip_code = match.groups()
    return {
        "street": f"PO Box {box_number}",
        "city": city.strip(),
        "state": state.upper(),
        "zip": zip_code,
    }


def _po_box_required_for_mailing(email_text: str) -> bool:
    """
    True when broker text says mailing must be the PO Box, not the facility.

    We require PO Box AND an explicit facility-vs-mail contrast (email_3 pattern).
    Note: we cannot use the substring "mailing addres" alone — it falsely matches
    the normal phrase "mailing address" in other emails (e.g. email_1).
    """
    lowered = email_text.lower()
    has_po_box = "po box" in lowered or "p.o. box" in lowered
    facility_contrast = (
        "facility" in lowered
        or "mail goes" in lowered
        or "mailing addres is the po box" in lowered  # typo from sample email_3
        or "mailing address is the po box" in lowered
    )
    return has_po_box and facility_contrast


def _latest_revenue_from_source(email_text: str) -> int | None:
    """
    For threaded emails with corrections, prefer the latest stated revenue.

    email_1.txt: correction says $4.2M overrides earlier $3.8M in the thread.
    The stub model already returns $4.2M — this is a safety net if it didn't.
    """
    lowered = email_text.lower()

    # Look for explicit correction phrasing near a dollar amount.
    correction = re.search(
        r"(?:annual revenue is|revenue is)\s+\$?\s*([\d,.]+)\s*([mk])?",
        lowered,
    )
    if correction:
        return _parse_money_fragment(correction.group(1), correction.group(2))

    return None


def _parse_money_fragment(number_part: str, suffix: str | None) -> int | None:
    """Helper: turn '4.2' + 'm' into 4200000."""
    try:
        value = float(number_part.replace(",", ""))
    except ValueError:
        return None
    if suffix == "m":
        value *= 1_000_000
    elif suffix == "k":
        value *= 1_000
    return int(value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_source_validation(
    source_email: str,
    draft: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """
    Adjust a normalized draft using evidence from the original email.

    Returns:
      - updated draft (may mutate field values)
      - warnings: non-blocking issues a broker should see (Human+ / red zone)
      - errors: blocking issues — record must NOT be submitted as-is

    Philosophy (audience.md): get to the red zone with defensible data; flag
    ambiguity rather than silently shipping model hallucinations.
    """
    warnings: list[str] = []
    errors: list[str] = []
    updated = dict(draft)

    # --- Revenue: unknown in source → force null ---------------------------
    if _revenue_marked_unknown_in_source(source_email):
        if updated.get("annualRevenue") is not None:
            warnings.append(
                "Source email says revenue is TBD; cleared model-provided "
                f"annualRevenue ({updated.get('annualRevenue')}) — will not guess."
            )
        updated["annualRevenue"] = None

    # --- Revenue: threaded correction (Blue Oak) ---------------------------
    elif (corrected := _latest_revenue_from_source(source_email)) is not None:
        if updated.get("annualRevenue") != corrected:
            warnings.append(
                f"Applied latest revenue from source email thread: ${corrected:,}."
            )
        updated["annualRevenue"] = corrected

    # --- Mailing address: PO Box override (Sundance) -----------------------
    if _po_box_required_for_mailing(source_email):
        po_box = _extract_po_box_mailing_address(source_email)
        if po_box:
            model_street = (updated.get("mailingAddress") or {}).get("street", "")
            if model_street and "po box" not in model_street.lower():
                warnings.append(
                    "Source email requires PO Box for mailing; replaced model "
                    f"facility address ({model_street!r}) with {po_box['street']!r}."
                )
            updated["mailingAddress"] = po_box
        else:
            errors.append(
                "Source email requires PO Box mailing address but we could not "
                "parse it — needs human review."
            )

    # --- Effective date: not confirmed → block -----------------------------
    if _effective_date_not_confirmed_in_source(source_email):
        if updated.get("effectiveDate"):
            warnings.append(
                "Source email says effective date is not confirmed; cleared "
                f"model-provided effectiveDate ({updated.get('effectiveDate')!r})."
            )
        updated["effectiveDate"] = None
        errors.append(
            "Effective date not stated in source email — cannot submit a complete "
            "AMS record yet. File can be started; human must add date before bind."
        )

    return updated, warnings, errors


def validate_record_completeness(record: dict[str, Any]) -> list[str]:
    """
    Final schema check: every AMS-required field present and non-empty.

    annualRevenue may legitimately be null (Pelican Point). effectiveDate may
    NOT be null for submission — that's why Tula fails here.
    """
    from pipeline.schema import REQUIRED_ADDRESS_FIELDS, REQUIRED_RECORD_FIELDS

    errors: list[str] = []

    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            errors.append(f"Missing field: {field}")
            continue

        value = record[field]

        # annualRevenue and dba are allowed to be None.
        if field in {"annualRevenue", "dba"}:
            continue

        if value is None or value == "":
            errors.append(f"Required field empty: {field}")

    address = record.get("mailingAddress")
    if not isinstance(address, dict):
        errors.append("mailingAddress must be an object")
    else:
        for sub in REQUIRED_ADDRESS_FIELDS:
            if not address.get(sub):
                errors.append(f"mailingAddress.{sub} is required")

    return errors
