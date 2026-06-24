"""
AMS record schema constants.

These mirror the fields documented in README.md for POST /api/v1/records.
We keep them in one place so normalization and validation stay aligned with
what the stub AMS actually accepts (see stub validation rules).
"""

# Lines of business the AMS accepts — exact snake_case strings only.
VALID_LINES_OF_BUSINESS = frozenset(
    {
        "general_liability",
        "commercial_property",
        "workers_compensation",
        "commercial_auto",
        "bop",
    }
)

# All US states + DC — AMS rejects anything else (e.g. "Tex.").
VALID_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI "
    "WY DC".split()
)

# Required top-level keys for a submittable AMS record.
REQUIRED_RECORD_FIELDS = (
    "insuredName",
    "dba",
    "mailingAddress",
    "lineOfBusiness",
    "effectiveDate",
    "annualRevenue",
    "contactEmail",
)

# Required keys inside mailingAddress.
REQUIRED_ADDRESS_FIELDS = ("street", "city", "state", "zip")
