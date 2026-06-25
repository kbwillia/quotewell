"""
AMS record schema constants — mirrors README field rules.
"""

# AMS only accepts these exact line-of-business strings (snake_case)
VALID_LINES_OF_BUSINESS = frozenset(
    {
        "general_liability",
        "commercial_property",
        "workers_compensation",
        "commercial_auto",
        "bop",
    }
)

# AMS rejects informal state text like "Tex." — must be 2-letter USPS code
VALID_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI "
    "WY DC".split()
)

# Every key the AMS record object must have before we try to submit
REQUIRED_RECORD_FIELDS = (
    "insuredName",
    "dba",  # can be null
    "mailingAddress",
    "lineOfBusiness",
    "effectiveDate",
    "annualRevenue",  # can be null if unknown
    "contactEmail",
)

# Nested address object must include all four sub-fields
REQUIRED_ADDRESS_FIELDS = ("street", "city", "state", "zip")
