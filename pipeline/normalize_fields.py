"""
Step 2 of Part 1: normalize parsed model fields to AMS-compatible formats.

The model often returns *semantically* correct data in *syntactically* wrong
shapes (e.g. "Tex." instead of "TX", "$4.2M" instead of 4200000). This module
fixes format — not factual accuracy. Factual checks against the source email
live in source_validation.py (governability: we defend what we submit).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pipeline.schema import VALID_LINES_OF_BUSINESS, VALID_STATE_CODES

# Map common model spellings → AMS enum values.
_LINE_OF_BUSINESS_ALIASES: dict[str, str] = {
    "general liability": "general_liability",
    "general_liability": "general_liability",
    "gl": "general_liability",
    "commercial property": "commercial_property",
    "commercial_property": "commercial_property",
    "property": "commercial_property",
    "workers compensation": "workers_compensation",
    "workers comp": "workers_compensation",
    "workers_comp": "workers_compensation",
    "workers_compensation": "workers_compensation",
    "work comp": "workers_compensation",
    "commercial auto": "commercial_auto",
    "commercial_auto": "commercial_auto",
    "bop": "bop",
    "business owners policy": "bop",
    "business owners": "bop",
}

# Map informal state names/abbreviations → 2-letter USPS code.
_STATE_ALIASES: dict[str, str] = {
    "tex.": "TX",
    "texas": "TX",
    "tx": "TX",
    "calif.": "CA",
    "california": "CA",
    "ca": "CA",
    "oregon": "OR",
    "or": "OR",
    "alabama": "AL",
    "al": "AL",
}


def normalize_line_of_business(value: Any) -> str | None:
    """Convert free-text LOB labels to the AMS snake_case enum."""
    if value is None:
        return None
    key = str(value).strip().lower()
    normalized = _LINE_OF_BUSINESS_ALIASES.get(key)
    if normalized and normalized in VALID_LINES_OF_BUSINESS:
        return normalized
    # Already valid enum?
    if key in VALID_LINES_OF_BUSINESS:
        return key
    return None


def normalize_state(value: Any) -> str | None:
    """Convert state to 2-letter USPS code required by AMS."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    upper = raw.upper()
    if upper in VALID_STATE_CODES:
        return upper

    alias = _STATE_ALIASES.get(raw.lower())
    if alias:
        return alias

    return None


def normalize_zip(value: Any) -> str | None:
    """AMS requires exactly 5 digits (no ZIP+4)."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) >= 5:
        return digits[:5]
    return None


def normalize_effective_date(value: Any) -> str | None:
    """
    Convert assorted date strings to ISO YYYY-MM-DD.

    Handles formats seen in stub output: 07/01/2026, 2026-07-01, 8/15/26.
    Returns None if parsing fails — caller decides whether to block submission.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    # Already ISO-shaped?
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    formats = (
        "%m/%d/%Y",  # 07/01/2026
        "%m/%d/%y",  # 8/15/26
        "%Y-%m-%d",  # redundant but explicit
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_revenue(value: Any) -> int | None:
    """
    Convert revenue to integer USD, or None if unknown.

    README: "Use null if genuinely not stated — do not guess."
    This function only parses explicit values; it does not infer from context.
    """
    if value is None:
        return None

    # Already numeric from model JSON.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)

    raw = str(value).strip().lower()
    if not raw or raw in {"tbd", "unknown", "n/a", "na", "null", "none"}:
        return None

    # Strip currency symbols and commas: "$4,200,000" → 4200000
    cleaned = raw.replace(",", "").replace("$", "").strip()

    # Handle M/K suffixes common in insurance emails: "$4.2M", "950k"
    multiplier = 1
    if cleaned.endswith("m"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith("k"):
        multiplier = 1_000
        cleaned = cleaned[:-1]

    try:
        return int(float(cleaned) * multiplier)
    except ValueError:
        return None


def normalize_email(value: Any) -> str | None:
    """Basic email sanity check — AMS rejects malformed addresses."""
    if value is None:
        return None
    email = str(value).strip()
    # Same pattern the stub uses for validation.
    if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return email
    return None


def normalize_mailing_address(raw: Any) -> dict[str, str] | None:
    """
    Normalize nested address object from model output.

    Returns None if required sub-fields cannot be normalized — better to fail
    loudly than submit a partial address to a regulated AMS record.
    """
    if not isinstance(raw, dict):
        return None

    street = str(raw.get("street", "")).strip()
    city = str(raw.get("city", "")).strip()
    state = normalize_state(raw.get("state"))
    zip_code = normalize_zip(raw.get("zip"))

    if not street or not city or not state or not zip_code:
        return None

    return {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def normalize_dba(value: Any) -> str | None:
    """DBA is optional — AMS accepts string or null."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_insured_name(value: Any) -> str | None:
    """Legal entity name — required non-empty string."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_parsed_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Apply all field normalizers to a parsed model dict.

    Output is still a *draft* — source_validation.py may override values when
    the model contradicts the original email (governability layer).
    """
    return {
        "insuredName": normalize_insured_name(raw.get("insuredName")),
        "dba": normalize_dba(raw.get("dba")),
        "mailingAddress": normalize_mailing_address(raw.get("mailingAddress")),
        "lineOfBusiness": normalize_line_of_business(raw.get("lineOfBusiness")),
        "effectiveDate": normalize_effective_date(raw.get("effectiveDate")),
        "annualRevenue": normalize_revenue(raw.get("annualRevenue")),
        "contactEmail": normalize_email(raw.get("contactEmail")),
    }
