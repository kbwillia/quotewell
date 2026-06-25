"""
Step 3: fix FORMAT so AMS accepts fields — does NOT judge factual truth yet.
Truth checks happen in source_validation.py using the original email.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pipeline.schema import VALID_LINES_OF_BUSINESS, VALID_STATE_CODES

# Model says "general liability" → AMS wants "general_liability"
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

# Model says "Tex." / "California" → AMS wants 2-letter USPS code (all states + DC)
_STATE_ALIASES: dict[str, str] = {
    # Alabama
    "alabama": "AL",
    "ala.": "AL",
    "ala": "AL",
    "al": "AL",
    # Alaska
    "alaska": "AK",
    "ak": "AK",
    # Arizona
    "arizona": "AZ",
    "ariz.": "AZ",
    "ariz": "AZ",
    "az": "AZ",
    # Arkansas
    "arkansas": "AR",
    "ark.": "AR",
    "ark": "AR",
    "ar": "AR",
    # California
    "california": "CA",
    "calif.": "CA",
    "calif": "CA",
    "cal.": "CA",
    "cal": "CA",
    "ca": "CA",
    # Colorado
    "colorado": "CO",
    "colo.": "CO",
    "colo": "CO",
    "co": "CO",
    # Connecticut
    "connecticut": "CT",
    "conn.": "CT",
    "conn": "CT",
    "ct": "CT",
    # Delaware
    "delaware": "DE",
    "del.": "DE",
    "del": "DE",
    "de": "DE",
    # District of Columbia
    "district of columbia": "DC",
    "washington dc": "DC",
    "washington d.c.": "DC",
    "d.c.": "DC",
    "dc": "DC",
    # Florida
    "florida": "FL",
    "fla.": "FL",
    "fla": "FL",
    "fl": "FL",
    # Georgia
    "georgia": "GA",
    "ga.": "GA",
    "ga": "GA",
    # Hawaii
    "hawaii": "HI",
    "hi": "HI",
    # Idaho
    "idaho": "ID",
    "id": "ID",
    # Illinois
    "illinois": "IL",
    "ill.": "IL",
    "ill": "IL",
    "il": "IL",
    # Indiana
    "indiana": "IN",
    "ind.": "IN",
    "ind": "IN",
    "in": "IN",
    # Iowa
    "iowa": "IA",
    "ia": "IA",
    # Kansas
    "kansas": "KS",
    "kans.": "KS",
    "kans": "KS",
    "ks": "KS",
    # Kentucky
    "kentucky": "KY",
    "ky.": "KY",
    "ky": "KY",
    # Louisiana
    "louisiana": "LA",
    "la.": "LA",
    "la": "LA",
    # Maine
    "maine": "ME",
    "me": "ME",
    # Maryland
    "maryland": "MD",
    "md.": "MD",
    "md": "MD",
    # Massachusetts
    "massachusetts": "MA",
    "mass.": "MA",
    "mass": "MA",
    "ma": "MA",
    # Michigan
    "michigan": "MI",
    "mich.": "MI",
    "mich": "MI",
    "mi": "MI",
    # Minnesota
    "minnesota": "MN",
    "minn.": "MN",
    "minn": "MN",
    "mn": "MN",
    # Mississippi
    "mississippi": "MS",
    "miss.": "MS",
    "miss": "MS",
    "ms": "MS",
    # Missouri
    "missouri": "MO",
    "mo.": "MO",
    "mo": "MO",
    # Montana
    "montana": "MT",
    "mont.": "MT",
    "mont": "MT",
    "mt": "MT",
    # Nebraska
    "nebraska": "NE",
    "nebr.": "NE",
    "nebr": "NE",
    "neb.": "NE",
    "neb": "NE",
    "ne": "NE",
    # Nevada
    "nevada": "NV",
    "nev.": "NV",
    "nev": "NV",
    "nv": "NV",
    # New Hampshire
    "new hampshire": "NH",
    "n.h.": "NH",
    "nh": "NH",
    # New Jersey
    "new jersey": "NJ",
    "n.j.": "NJ",
    "nj": "NJ",
    # New Mexico
    "new mexico": "NM",
    "n.m.": "NM",
    "nm": "NM",
    # New York
    "new york": "NY",
    "n.y.": "NY",
    "ny": "NY",
    # North Carolina
    "north carolina": "NC",
    "n.c.": "NC",
    "nc": "NC",
    # North Dakota
    "north dakota": "ND",
    "n.d.": "ND",
    "nd": "ND",
    # Ohio
    "ohio": "OH",
    "oh": "OH",
    # Oklahoma
    "oklahoma": "OK",
    "okla.": "OK",
    "okla": "OK",
    "ok": "OK",
    # Oregon
    "oregon": "OR",
    "ore.": "OR",
    "ore": "OR",
    "or": "OR",
    # Pennsylvania
    "pennsylvania": "PA",
    "penn.": "PA",
    "penn": "PA",
    "pa.": "PA",
    "pa": "PA",
    # Rhode Island
    "rhode island": "RI",
    "r.i.": "RI",
    "ri": "RI",
    # South Carolina
    "south carolina": "SC",
    "s.c.": "SC",
    "sc": "SC",
    # South Dakota
    "south dakota": "SD",
    "s.d.": "SD",
    "sd": "SD",
    # Tennessee
    "tennessee": "TN",
    "tenn.": "TN",
    "tenn": "TN",
    "tn": "TN",
    # Texas
    "texas": "TX",
    "tex.": "TX",
    "tex": "TX",
    "tx": "TX",
    # Utah
    "utah": "UT",
    "ut": "UT",
    # Vermont
    "vermont": "VT",
    "vt.": "VT",
    "vt": "VT",
    # Virginia
    "virginia": "VA",
    "va.": "VA",
    "va": "VA",
    # Washington
    "washington": "WA",
    "wash.": "WA",
    "wash": "WA",
    "wa": "WA",
    # West Virginia
    "west virginia": "WV",
    "w.va.": "WV",
    "w. va.": "WV",
    "wv": "WV",
    # Wisconsin
    "wisconsin": "WI",
    "wis.": "WI",
    "wis": "WI",
    "wisc.": "WI",
    "wisc": "WI",
    "wi": "WI",
    # Wyoming
    "wyoming": "WY",
    "wyo.": "WY",
    "wyo": "WY",
    "wy": "WY",
}


def normalize_line_of_business(value: Any) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    normalized = _LINE_OF_BUSINESS_ALIASES.get(key)
    if normalized and normalized in VALID_LINES_OF_BUSINESS:
        return normalized
    # Already a valid enum string?
    if key in VALID_LINES_OF_BUSINESS:
        return key
    return None  # unknown LOB — will fail completeness check


def normalize_state(value: Any) -> str | None:
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
    # Strip non-digits, take first 5 (AMS rejects ZIP+4)
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) >= 5:
        return digits[:5]
    return None


def normalize_effective_date(value: Any) -> str | None:
    # AMS requires YYYY-MM-DD
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw  # already ISO

    formats = (
        "%m/%d/%Y",  # 07/01/2026
        "%m/%d/%y",  # 8/15/26
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_revenue(value: Any) -> int | None:
    # README: use null if unknown — this only parses explicit values
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)  # e.g. 850000 from model JSON

    raw = str(value).strip().lower()
    if not raw or raw in {"tbd", "unknown", "n/a", "na", "null", "none"}:
        return None

    cleaned = raw.replace(",", "").replace("$", "").strip()

    # "$4.2M" → 4200000, "950k" → 950000
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
    if value is None:
        return None
    email = str(value).strip()
    if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return email
    return None


def normalize_mailing_address(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None

    street = str(raw.get("street", "")).strip()
    city = str(raw.get("city", "")).strip()
    state = normalize_state(raw.get("state"))
    zip_code = normalize_zip(raw.get("zip"))

    # All four required — partial address is worse than failing
    if not street or not city or not state or not zip_code:
        return None

    return {
        "street": street,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def normalize_dba(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_insured_name(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_parsed_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Run every field through its normalizer.
    Output is a draft — source_validation may still override values.
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
