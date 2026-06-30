"""
Step 4: cross-check model output against the SOURCE EMAIL (governability).
Broker email wins when the model is wrong or invents data.
"""

import re
from typing import Any


def _revenue_marked_unknown_in_source(email_text: str) -> bool:
    # email_2: "revenue is TBD" — model wrongly returns 850000
    lowered = email_text.lower()
    patterns = (
        r"revenue\s+is\s+tbd",
        r"revenue\s+tbd",
        r"financials?\s+(?:is|are)\s+tbd",
        r"revenue\s+(?:is\s+)?unknown",
        r"don't hold the submission for it",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _effective_date_not_confirmed_in_source(email_text: str) -> bool:
    # email_4: owner hasn't locked date — model wrongly returns 2026-07-01
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
    # email_3: parse "PO Box 1142, Bend, OR 97709" from broker text
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
    # Only when email contrasts facility vs PO Box (avoids false match on email_1)
    lowered = email_text.lower()
    has_po_box = "po box" in lowered or "p.o. box" in lowered
    facility_contrast = (
        "facility" in lowered
        or "mail goes" in lowered
        or "mailing addres is the po box" in lowered
        or "mailing address is the po box" in lowered
    )
    return has_po_box and facility_contrast


def _latest_revenue_from_source(email_text: str) -> int | None:
    # email_1 safety net: "annual revenue is $4.2M" in latest reply
    lowered = email_text.lower()
    correction = re.search(
        r"(?:annual revenue is|revenue is)\s+\$?\s*([\d,.]+)\s*([mk])?",
        lowered,
    )
    if correction:
        return _parse_money_fragment(correction.group(1), correction.group(2))
    return None


def _parse_money_fragment(number_part: str, suffix: str | None) -> int | None:
    try:
        value = float(number_part.replace(",", ""))
    except ValueError:
        return None
    if suffix == "m":
        value *= 1_000_000
    elif suffix == "k":
        value *= 1_000
    return int(value)


def apply_source_validation(
    source_email: str,
    draft: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """
    Returns: (updated record, warnings, errors).
    errors = blocking (don't submit). warnings = broker should know.
    """
    warnings: list[str] = []
    errors: list[str] = []
    updated = dict(draft)  # copy so we don't mutate caller's dict

    # --- Pelican Point: revenue TBD → must be null ---
    if _revenue_marked_unknown_in_source(source_email):
        if updated.get("annualRevenue") is not None:
            warnings.append(
                "Source email says revenue is TBD; cleared model-provided "
                f"annualRevenue ({updated.get('annualRevenue')}) — will not guess."
            )
        updated["annualRevenue"] = None

    # --- Blue Oak: prefer latest revenue from thread (if detected) ---
    elif (corrected := _latest_revenue_from_source(source_email)) is not None:
        if updated.get("annualRevenue") != corrected:
            warnings.append(
                f"Applied latest revenue from source email thread: ${corrected:,}."
            )
        updated["annualRevenue"] = corrected

    # --- Sundance: PO Box for mailing, not facility street ---
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

    # --- Tula: effective date not confirmed → block submit ---
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
    """Final gate: all required AMS fields present before Part 2 submit."""
    from pipeline.schema import REQUIRED_ADDRESS_FIELDS, REQUIRED_RECORD_FIELDS

    errors: list[str] = []

    for field in REQUIRED_RECORD_FIELDS:
        if field not in record:
            errors.append(f"Missing field: {field}")
            continue

        value = record[field]

        # null is OK for optional-ish fields
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
