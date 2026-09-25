"""
app/ingestion/privacy_detector.py
=================================
Sensitive and Direct-Identifier Detection

WHY THIS EXISTS:
    Clinical datasets often contain Protected Health Information (PHI) and
    Direct Identifiers (such as Social Security Numbers, Passport numbers,
    Driver's license IDs, and patient full names).

    Under regulations such as HIPAA Safe Harbor and GDPR:
      - Direct identifiers must NOT be exposed in plain text in analytical tables
      - Geolocation below state/3-digit ZIP must be protected
      - Dates and identifiers require controlled de-identification/masking

CRITICAL SAFETY PRINCIPLE:
    This module NEVER modifies or deletes columns from the source files.
    All source CSVs remain 100% read-only.
    This module only DETECTS and REPORTS sensitive columns so they can be
    properly protected during analytical MySQL schema design (Phase 4).
"""

import re
from typing import Optional, Dict
from app.schemas.validation import SensitiveColumnMetadata


# =============================================================================
# Sensitive Patterns Catalog
# =============================================================================

# Known direct-identifier column names mapped to classification and mitigation advice
SENSITIVE_COLUMN_RULES: Dict[str, Dict[str, str]] = {
    "SSN": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Social Security Number uniquely identifies an individual in the United States.",
        "recommendation": "Hash (SHA-256 with salt) or exclude completely from analytical tables.",
    },
    "DRIVERS": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Driver's license number is a government-issued unique identifier.",
        "recommendation": "Exclude from analytical tables or store only in encrypted key vault.",
    },
    "PASSPORT": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Passport number uniquely identifies an individual internationally.",
        "recommendation": "Exclude from analytical tables or store only in encrypted key vault.",
    },
    "FIRST": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Patient's first name is a direct personal identifier.",
        "recommendation": "De-identify using surrogate pseudonyms or mask in analytical reporting.",
    },
    "LAST": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Patient's surname is a direct personal identifier.",
        "recommendation": "De-identify using surrogate pseudonyms or mask in analytical reporting.",
    },
    "MAIDEN": {
        "category": "Direct Identifier / Demographic",
        "reason": "Mother's maiden name is sensitive personal history used in identity verification.",
        "recommendation": "Exclude or mask in analytical datasets.",
    },
    "ADDRESS": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Street address constitutes specific geographic identification smaller than a state.",
        "recommendation": "Aggregate to city/state level; do not load raw street addresses into queryable analytics.",
    },
    "ZIP": {
        "category": "Quasi-Identifier / Geolocation (HIPAA Safe Harbor)",
        "reason": "5-digit ZIP codes combined with demographic data can enable patient re-identification.",
        "recommendation": "Truncate to 3-digit prefix if population > 20,000, or aggregate to county level.",
    },
    "BIRTHPLACE": {
        "category": "Quasi-Identifier / Demographic",
        "reason": "Specific birthplace information can assist in re-identification of rare populations.",
        "recommendation": "Generalize to state/country or exclude if not clinically needed.",
    },
    "LAT": {
        "category": "Precise Geolocation (HIPAA Safe Harbor)",
        "reason": "Latitude coordinate pinpoints precise physical residence of the patient.",
        "recommendation": "Fuzz/jitter coordinates or drop precise coordinates in favor of county/state.",
    },
    "LON": {
        "category": "Precise Geolocation (HIPAA Safe Harbor)",
        "reason": "Longitude coordinate pinpoints precise physical residence of the patient.",
        "recommendation": "Fuzz/jitter coordinates or drop precise coordinates in favor of county/state.",
    },
    "PHONE": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Telephone numbers directly identify patient contact information.",
        "recommendation": "Exclude from analytical tables.",
    },
    "EMAIL": {
        "category": "Direct Identifier (HIPAA Safe Harbor)",
        "reason": "Electronic mail address directly identifies the individual.",
        "recommendation": "Exclude from analytical tables.",
    },
}


def detect_sensitive_column(column_name: str, sample_values: Optional[list] = None) -> Optional[SensitiveColumnMetadata]:
    """
    Evaluates whether a given column is a sensitive direct identifier or quasi-identifier.

    Checks:
      1. Exact match against known identifier rules (case-insensitive)
      2. Heuristic suffix/prefix matching (e.g. 'PATIENT_NAME', 'SSN_NUM')
      3. Value pattern matching (e.g. SSN regex XXX-XX-XXXX)

    Returns:
      SensitiveColumnMetadata if sensitive, else None.
    """
    col_upper = column_name.strip().upper()

    # 1. Exact match against catalog
    if col_upper in SENSITIVE_COLUMN_RULES:
        rule = SENSITIVE_COLUMN_RULES[col_upper]
        return SensitiveColumnMetadata(
            column=column_name,
            category=rule["category"],
            reason=rule["reason"],
            recommendation=rule["recommendation"],
        )

    # 2. Heuristic name checks
    if any(k in col_upper for k in ["_SSN", "SSN_", "SOCIAL_SECURITY"]):
        return SensitiveColumnMetadata(
            column=column_name,
            category="Direct Identifier (HIPAA Safe Harbor)",
            reason="Column name indicates Social Security Number.",
            recommendation="Exclude or mask prior to analytical loading.",
        )

    if any(k in col_upper for k in ["PASSPORT", "DRIVERS_LIC", "DL_NUMBER"]):
        return SensitiveColumnMetadata(
            column=column_name,
            category="Direct Identifier (HIPAA Safe Harbor)",
            reason="Column name indicates government-issued identification.",
            recommendation="Exclude or mask prior to analytical loading.",
        )

    # 3. Value-based inspection for SSN format (###-##-####)
    if sample_values:
        ssn_regex = re.compile(r"^\d{3}-\d{2}-\d{4}$")
        matches = [s for s in sample_values if isinstance(s, str) and ssn_regex.match(s.strip())]
        if matches and len(matches) >= len(sample_values) * 0.5:
            return SensitiveColumnMetadata(
                column=column_name,
                category="Direct Identifier (HIPAA Safe Harbor)",
                reason="Values match Social Security Number pattern (XXX-XX-XXXX).",
                recommendation="Mask or exclude from analytical tables.",
            )

    return None
