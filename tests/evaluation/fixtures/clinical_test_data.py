"""
tests/evaluation/fixtures/clinical_test_data.py
===============================================
Deterministic synthetic test fixtures for verifying KPI mathematical correctness,
aggregation logic, population denominators, and filter criteria without relying
on production database mutations.
"""

from typing import Dict, Any, List


# Synthetic Cohort: 4 Subjects in ADSL (2 Drug X, 2 Placebo)
SYNTHETIC_ADSL: List[Dict[str, Any]] = [
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-001",
        "ARM": "Drug X",
        "TRT01A": "Drug X",
        "SAFFL": "Y",
        "ITTFL": "Y",
        "EFFFL": "Y",
        "AGE": 45,
        "SEX": "M",
    },
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-002",
        "ARM": "Drug X",
        "TRT01A": "Drug X",
        "SAFFL": "Y",
        "ITTFL": "Y",
        "EFFFL": "Y",
        "AGE": 52,
        "SEX": "F",
    },
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-003",
        "ARM": "Placebo",
        "TRT01A": "Placebo",
        "SAFFL": "Y",
        "ITTFL": "Y",
        "EFFFL": "Y",
        "AGE": 61,
        "SEX": "M",
    },
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-004",
        "ARM": "Placebo",
        "TRT01A": "Placebo",
        "SAFFL": "Y",
        "ITTFL": "Y",
        "EFFFL": "Y",
        "AGE": 39,
        "SEX": "F",
    },
]

# Synthetic Adverse Events: Multiple events per subject, non-TEAE, and serious flags
SYNTHETIC_ADAE: List[Dict[str, Any]] = [
    # SUBJ-001 (Drug X): 2 treatment-emergent AEs (Nausea, Headache), Non-serious
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-001",
        "TRT01A": "Drug X",
        "AEDECOD": "Nausea",
        "TRTEMFL": "Y",
        "SAFFL": "Y",
        "AESER": "N",
        "AESEV": "MILD",
    },
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-001",
        "TRT01A": "Drug X",
        "AEDECOD": "Headache",
        "TRTEMFL": "Y",
        "SAFFL": "Y",
        "AESER": "N",
        "AESEV": "MODERATE",
    },
    # SUBJ-002 (Drug X): No adverse events recorded (0 rows)
    # SUBJ-003 (Placebo): 1 treatment-emergent Serious Adverse Event (Serious Infection)
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-003",
        "TRT01A": "Placebo",
        "AEDECOD": "Serious Infection",
        "TRTEMFL": "Y",
        "SAFFL": "Y",
        "AESER": "Y",
        "AESEV": "SEVERE",
    },
    # SUBJ-004 (Placebo): 1 pre-existing event (NOT treatment emergent: TRTEMFL = 'N')
    {
        "STUDYID": "TEST-001",
        "USUBJID": "SUBJ-004",
        "TRT01A": "Placebo",
        "AEDECOD": "Cough",
        "TRTEMFL": "N",
        "SAFFL": "Y",
        "AESER": "N",
        "AESEV": "MILD",
    },
]

# Synthetic Lab Analysis: Baseline and Visit 1 values
SYNTHETIC_ADLB: List[Dict[str, Any]] = [
    {"USUBJID": "SUBJ-001", "TRT01A": "Drug X", "PARAMCD": "ALT", "AVISIT": "Baseline", "BASE": 25.0, "AVAL": 25.0, "CHG": 0.0},
    {"USUBJID": "SUBJ-001", "TRT01A": "Drug X", "PARAMCD": "ALT", "AVISIT": "Week 4", "BASE": 25.0, "AVAL": 35.0, "CHG": 10.0},
    {"USUBJID": "SUBJ-002", "TRT01A": "Drug X", "PARAMCD": "ALT", "AVISIT": "Baseline", "BASE": 30.0, "AVAL": 30.0, "CHG": 0.0},
    {"USUBJID": "SUBJ-002", "TRT01A": "Drug X", "PARAMCD": "ALT", "AVISIT": "Week 4", "BASE": 30.0, "AVAL": 32.0, "CHG": 2.0},
    {"USUBJID": "SUBJ-003", "TRT01A": "Placebo", "PARAMCD": "ALT", "AVISIT": "Baseline", "BASE": 22.0, "AVAL": 22.0, "CHG": 0.0},
    {"USUBJID": "SUBJ-003", "TRT01A": "Placebo", "PARAMCD": "ALT", "AVISIT": "Week 4", "BASE": 22.0, "AVAL": 23.0, "CHG": 1.0},
    {"USUBJID": "SUBJ-004", "TRT01A": "Placebo", "PARAMCD": "ALT", "AVISIT": "Baseline", "BASE": 28.0, "AVAL": 28.0, "CHG": 0.0},
    {"USUBJID": "SUBJ-004", "TRT01A": "Placebo", "PARAMCD": "ALT", "AVISIT": "Week 4", "BASE": 28.0, "AVAL": 29.0, "CHG": 1.0},
]

# Synthetic Responder Analysis: ADRESP
SYNTHETIC_ADRESP: List[Dict[str, Any]] = [
    {"USUBJID": "SUBJ-001", "TRT01A": "Drug X", "PARAMCD": "BOR", "RESPFL": "Y", "EFFFL": "Y"},
    {"USUBJID": "SUBJ-002", "TRT01A": "Drug X", "PARAMCD": "BOR", "RESPFL": "N", "EFFFL": "Y"},
    {"USUBJID": "SUBJ-003", "TRT01A": "Placebo", "PARAMCD": "BOR", "RESPFL": "N", "EFFFL": "Y"},
    {"USUBJID": "SUBJ-004", "TRT01A": "Placebo", "PARAMCD": "BOR", "RESPFL": "N", "EFFFL": "Y"},
]

# Trusted Invariant Ground Truth Calculations
GROUND_TRUTH_KPIS: Dict[str, Any] = {
    "total_subjects": 4,
    "subjects_by_arm": {
        "Drug X": 2,
        "Placebo": 2,
    },
    "ae_incidence_rate": {
        # Numerator: Distinct subjects with >=1 TEAE (SUBJ-001 for Drug X, SUBJ-003 for Placebo)
        # Denominator: Total subjects in safety population per arm (2 each)
        "Drug X": {
            "numerator": 1,
            "denominator": 2,
            "percentage": 50.0,
        },
        "Placebo": {
            "numerator": 1,
            "denominator": 2,
            "percentage": 50.0,
        },
        "Overall": {
            "numerator": 2,
            "denominator": 4,
            "percentage": 50.0,
        },
    },
    "sae_incidence_rate": {
        # Only SUBJ-003 had SAE = 'Y'
        "Drug X": {
            "numerator": 0,
            "denominator": 2,
            "percentage": 0.0,
        },
        "Placebo": {
            "numerator": 1,
            "denominator": 2,
            "percentage": 50.0,
        },
        "Overall": {
            "numerator": 1,
            "denominator": 4,
            "percentage": 25.0,
        },
    },
    "alt_mean_change_week4": {
        # Drug X: (10.0 + 2.0) / 2 = 6.0
        # Placebo: (1.0 + 1.0) / 2 = 1.0
        "Drug X": 6.0,
        "Placebo": 1.0,
    },
    "responder_rate": {
        # Drug X: 1 of 2 = 50.0%
        # Placebo: 0 of 2 = 0.0%
        # Overall: 1 of 4 = 25.0%
        "Drug X": 50.0,
        "Placebo": 0.0,
        "Overall": 25.0,
    },
}
