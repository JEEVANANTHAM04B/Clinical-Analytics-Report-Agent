"""
app/clinical/kpi_definitions.py
===============================
Standard Clinical KPI definitions, calculations, numerator/denominator formulas,
and deterministic SQL templates for CDISC clinical trial analysis.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class KPIDefinition:
    """Specification of a clinical key performance indicator (KPI)."""
    kpi_id: str
    name: str
    category: str  # "Enrollment", "Demographics", "Safety", "Laboratory", "Vital Signs", "Efficacy", "Disposition"
    description: str
    primary_dataset: str
    required_datasets: List[str]
    required_columns: List[str]
    dimensions: List[str]
    numerator: Optional[str] = None
    denominator: Optional[str] = None
    formula: str = ""
    calculation_type: str = "count"  # "count", "average", "percentage", "rate", "distribution"
    sql_template: str = ""
    supported_filters: List[str] = field(default_factory=list)


# =============================================================================
# CLINICAL TRIAL KPI REGISTRY
# =============================================================================

KPIS: Dict[str, KPIDefinition] = {
    # ── 1. Total Subjects ────────────────────────────────────────────────────
    "TOTAL_SUBJECTS": KPIDefinition(
        kpi_id="TOTAL_SUBJECTS",
        name="Total Enrolled Subjects",
        category="Enrollment",
        description="Total distinct enrolled subjects participating in the study.",
        primary_dataset="dm",
        required_datasets=["dm"],
        required_columns=["dm.USUBJID"],
        dimensions=[],
        numerator="COUNT(DISTINCT dm.USUBJID)",
        denominator=None,
        formula="COUNT(DISTINCT dm.USUBJID)",
        calculation_type="count",
        sql_template="SELECT COUNT(DISTINCT USUBJID) AS total_subjects FROM dm;",
        supported_filters=["ARM", "ARMCD", "SITEID", "SEX"],
    ),

    # ── 2. Enrollment by Site ────────────────────────────────────────────────
    "ENROLLMENT_BY_SITE": KPIDefinition(
        kpi_id="ENROLLMENT_BY_SITE",
        name="Enrollment by Clinical Site",
        category="Enrollment",
        description="Number of subjects recruited at each investigator site.",
        primary_dataset="dm",
        required_datasets=["sites", "dm"],
        required_columns=["sites.SITEID", "sites.SITE_NAME", "dm.USUBJID"],
        dimensions=["SITEID", "SITE_NAME"],
        numerator="COUNT(DISTINCT dm.USUBJID)",
        denominator=None,
        formula="COUNT(DISTINCT dm.USUBJID) GROUP BY sites.SITEID",
        calculation_type="distribution",
        sql_template="""
            SELECT sites.SITEID, sites.SITE_NAME, sites.CITY, COUNT(DISTINCT dm.USUBJID) AS enrolled_subjects
            FROM sites
            JOIN dm ON sites.SITEID = dm.SITEID
            GROUP BY sites.SITEID, sites.SITE_NAME, sites.CITY
            ORDER BY enrolled_subjects DESC;
        """,
        supported_filters=["COUNTRY", "CITY"],
    ),

    # ── 2b. Participating Clinical Sites Count ───────────────────────────────
    "CLINICAL_SITES_COUNT": KPIDefinition(
        kpi_id="CLINICAL_SITES_COUNT",
        name="Participating Clinical Sites",
        category="Enrollment",
        description="Total distinct clinical trial sites participating in the study.",
        primary_dataset="sites",
        required_datasets=["sites"],
        required_columns=["sites.SITEID"],
        dimensions=[],
        numerator="COUNT(DISTINCT sites.SITEID)",
        denominator=None,
        formula="COUNT(DISTINCT sites.SITEID)",
        calculation_type="count",
        sql_template="SELECT COUNT(DISTINCT SITEID) AS site_count FROM sites;",
        supported_filters=["COUNTRY", "CITY"],
    ),

    # ── 2c. Safety Population ────────────────────────────────────────────────
    "SAFETY_POPULATION": KPIDefinition(
        kpi_id="SAFETY_POPULATION",
        name="Safety Population Count",
        category="Demographics",
        description="Number of subjects meeting safety population criteria (SAFFL = 'Y').",
        primary_dataset="adsl",
        required_datasets=["adsl"],
        required_columns=["adsl.USUBJID", "adsl.SAFFL"],
        dimensions=["SAFFL"],
        numerator="COUNT(DISTINCT adsl.USUBJID)",
        denominator=None,
        formula="COUNT(DISTINCT adsl.USUBJID) WHERE adsl.SAFFL = 'Y'",
        calculation_type="count",
        sql_template="SELECT COUNT(DISTINCT USUBJID) AS safety_population_count FROM adsl WHERE SAFFL = 'Y';",
        supported_filters=["TRT01A", "SEX"],
    ),

    # ── 3. Subjects by Treatment Arm ─────────────────────────────────────────
    "SUBJECTS_BY_TREATMENT_ARM": KPIDefinition(
        kpi_id="SUBJECTS_BY_TREATMENT_ARM",
        name="Subjects by Treatment Arm",
        category="Demographics",
        description="Subject distribution across randomized treatment arms.",
        primary_dataset="adsl",
        required_datasets=["adsl"],
        required_columns=["adsl.USUBJID", "adsl.TRT01A"],
        dimensions=["TRT01A"],
        numerator="COUNT(DISTINCT adsl.USUBJID)",
        denominator=None,
        formula="COUNT(DISTINCT adsl.USUBJID) GROUP BY adsl.TRT01A",
        calculation_type="distribution",
        sql_template="""
            SELECT TRT01A, COUNT(DISTINCT USUBJID) AS subject_count
            FROM adsl
            GROUP BY TRT01A
            ORDER BY subject_count DESC;
        """,
        supported_filters=["SAFFL", "ITTFL", "SEX"],
    ),

    # ── 4. Average Age ───────────────────────────────────────────────────────
    "AVERAGE_AGE": KPIDefinition(
        kpi_id="AVERAGE_AGE",
        name="Average Subject Age",
        category="Demographics",
        description="Mean and range of subject age across trial cohorts.",
        primary_dataset="dm",
        required_datasets=["dm"],
        required_columns=["dm.AGE"],
        dimensions=[],
        numerator="SUM(dm.AGE)",
        denominator="COUNT(dm.AGE)",
        formula="AVG(dm.AGE)",
        calculation_type="average",
        sql_template="""
            SELECT ROUND(AVG(AGE), 2) AS mean_age, MIN(AGE) AS min_age, MAX(AGE) AS max_age
            FROM dm;
        """,
        supported_filters=["ARM", "SEX", "SITEID"],
    ),

    # ── 5. Sex Distribution ──────────────────────────────────────────────────
    "SEX_DISTRIBUTION": KPIDefinition(
        kpi_id="SEX_DISTRIBUTION",
        name="Sex Distribution",
        category="Demographics",
        description="Distribution and proportion of enrolled subjects by biological sex.",
        primary_dataset="dm",
        required_datasets=["dm"],
        required_columns=["dm.USUBJID", "dm.SEX"],
        dimensions=["SEX"],
        numerator="COUNT(DISTINCT dm.USUBJID)",
        denominator="Total Subjects",
        formula="COUNT(DISTINCT dm.USUBJID) GROUP BY dm.SEX",
        calculation_type="distribution",
        sql_template="""
            SELECT SEX, COUNT(DISTINCT USUBJID) AS subject_count,
                   ROUND(COUNT(DISTINCT USUBJID) * 100.0 / (SELECT COUNT(DISTINCT USUBJID) FROM dm), 2) AS percentage
            FROM dm
            GROUP BY SEX;
        """,
        supported_filters=["ARM", "SITEID"],
    ),

    # ── 6. Adverse Event Count ───────────────────────────────────────────────
    "ADVERSE_EVENT_COUNT": KPIDefinition(
        kpi_id="ADVERSE_EVENT_COUNT",
        name="Total Adverse Events",
        category="Safety",
        description="Total cumulative count of reported adverse event incidents.",
        primary_dataset="ae",
        required_datasets=["ae"],
        required_columns=["ae.USUBJID", "ae.AESEQ"],
        dimensions=[],
        numerator="COUNT(*)",
        denominator=None,
        formula="COUNT(*)",
        calculation_type="count",
        sql_template="SELECT COUNT(*) AS total_adverse_events FROM ae;",
        supported_filters=["AESEV", "AESER", "AEREL", "AEDECOD"],
    ),

    # ── 7. Serious Adverse Event Count ───────────────────────────────────────
    "SERIOUS_AE_COUNT": KPIDefinition(
        kpi_id="SERIOUS_AE_COUNT",
        name="Serious Adverse Event Count",
        category="Safety",
        description="Total number of Serious Adverse Events (SAEs, AESER = 'Y').",
        primary_dataset="ae",
        required_datasets=["ae"],
        required_columns=["ae.USUBJID", "ae.AESER"],
        dimensions=[],
        numerator="COUNT(*) WHERE AESER = 'Y'",
        denominator=None,
        formula="COUNT(*) WHERE ae.AESER = 'Y'",
        calculation_type="count",
        sql_template="SELECT COUNT(*) AS serious_adverse_events FROM ae WHERE AESER = 'Y';",
        supported_filters=["AESEV", "AEDECOD", "AEBODSYS"],
    ),

    # ── 8. Adverse Event Rate ────────────────────────────────────────────────
    "ADVERSE_EVENT_RATE": KPIDefinition(
        kpi_id="ADVERSE_EVENT_RATE",
        name="Overall Adverse Event Rate",
        category="Safety",
        description="Percentage of safety population experiencing at least one adverse event.",
        primary_dataset="adae",
        required_datasets=["adsl", "adae"],
        required_columns=["adsl.USUBJID", "adae.USUBJID"],
        dimensions=[],
        numerator="COUNT(DISTINCT adae.USUBJID)",
        denominator="COUNT(DISTINCT adsl.USUBJID)",
        formula="(COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID)) * 100",
        calculation_type="rate",
        sql_template="""
            SELECT ROUND(COUNT(DISTINCT adae.USUBJID) * 100.0 / COUNT(DISTINCT adsl.USUBJID), 2) AS overall_ae_rate_pct
            FROM adsl
            LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID;
        """,
        supported_filters=["TRT01A", "AESER"],
    ),

    # ── 9. AE Rate by Treatment Arm ──────────────────────────────────────────
    "AE_RATE_BY_TREATMENT": KPIDefinition(
        kpi_id="AE_RATE_BY_TREATMENT",
        name="Adverse Event Rate by Treatment Arm",
        category="Safety",
        description="Incidence rate of adverse events compared across treatment arms.",
        primary_dataset="adae",
        required_datasets=["adsl", "adae"],
        required_columns=["adsl.USUBJID", "adsl.TRT01A", "adae.USUBJID"],
        dimensions=["TRT01A"],
        numerator="COUNT(DISTINCT adae.USUBJID) in treatment arm",
        denominator="COUNT(DISTINCT adsl.USUBJID) in treatment arm",
        formula="(COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID)) * 100",
        calculation_type="rate",
        sql_template="""
            SELECT adsl.TRT01A,
                   COUNT(DISTINCT adsl.USUBJID) AS total_subjects,
                   COUNT(DISTINCT adae.USUBJID) AS ae_subjects,
                   ROUND(COUNT(DISTINCT adae.USUBJID) * 100.0 / COUNT(DISTINCT adsl.USUBJID), 2) AS ae_rate_pct
            FROM adsl
            LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID
            GROUP BY adsl.TRT01A
            ORDER BY ae_rate_pct DESC;
        """,
        supported_filters=["AESEV", "AESER"],
    ),

    # ── 10. AE Severity Distribution ────────────────────────────────────────
    "AE_SEVERITY_DISTRIBUTION": KPIDefinition(
        kpi_id="AE_SEVERITY_DISTRIBUTION",
        name="Adverse Event Severity Distribution",
        category="Safety",
        description="Breakdown of adverse events by severity grade (MILD, MODERATE, SEVERE).",
        primary_dataset="adae",
        required_datasets=["adae"],
        required_columns=["adae.USUBJID", "adae.AESEV"],
        dimensions=["AESEV"],
        numerator="COUNT(*)",
        denominator="Total AEs",
        formula="COUNT(*) GROUP BY adae.AESEV",
        calculation_type="distribution",
        sql_template="""
            SELECT AESEV AS severity, COUNT(*) AS event_count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM adae), 2) AS percentage
            FROM adae
            GROUP BY AESEV
            ORDER BY event_count DESC;
        """,
        supported_filters=["TRT01A", "AESER"],
    ),

    # ── 11. Laboratory Value ─────────────────────────────────────────────────
    "LAB_VALUE": KPIDefinition(
        kpi_id="LAB_VALUE",
        name="Laboratory Analysis Value",
        category="Laboratory",
        description="Statistical summary of laboratory biomarker measurements.",
        primary_dataset="adlb",
        required_datasets=["adlb"],
        required_columns=["adlb.PARAMCD", "adlb.PARAM", "adlb.AVAL", "adlb.AVISIT"],
        dimensions=["PARAMCD", "AVISIT"],
        numerator="AVG(adlb.AVAL)",
        denominator=None,
        formula="AVG(adlb.AVAL) GROUP BY adlb.PARAMCD, adlb.AVISIT",
        calculation_type="average",
        sql_template="""
            SELECT PARAMCD, PARAM, AVISIT,
                   ROUND(AVG(AVAL), 2) AS mean_aval,
                   ROUND(MIN(AVAL), 2) AS min_aval,
                   ROUND(MAX(AVAL), 2) AS max_aval,
                   COUNT(DISTINCT USUBJID) AS subject_count
            FROM adlb
            GROUP BY PARAMCD, PARAM, AVISIT
            ORDER BY PARAMCD, AVISIT;
        """,
        supported_filters=["TRT01A", "PARAMCD"],
    ),

    # ── 12. Laboratory Change from Baseline ──────────────────────────────────
    "LAB_CHANGE_FROM_BASELINE": KPIDefinition(
        kpi_id="LAB_CHANGE_FROM_BASELINE",
        name="Laboratory Change from Baseline",
        category="Laboratory",
        description="Mean absolute and percentage change from baseline in lab parameters.",
        primary_dataset="adlb",
        required_datasets=["adlb"],
        required_columns=["adlb.PARAMCD", "adlb.TRT01A", "adlb.AVISIT", "adlb.CHG", "adlb.PCHG"],
        dimensions=["PARAMCD", "TRT01A", "AVISIT"],
        numerator="AVG(adlb.CHG)",
        denominator=None,
        formula="AVG(adlb.CHG), AVG(adlb.PCHG)",
        calculation_type="average",
        sql_template="""
            SELECT PARAMCD, TRT01A, AVISIT,
                   ROUND(AVG(BASE), 2) AS mean_baseline,
                   ROUND(AVG(AVAL), 2) AS mean_visit_value,
                   ROUND(AVG(CHG), 2) AS mean_change,
                   ROUND(AVG(PCHG), 2) AS mean_pct_change
            FROM adlb
            WHERE AVISIT = 'WEEK 8'
            GROUP BY PARAMCD, TRT01A, AVISIT
            ORDER BY PARAMCD, TRT01A;
        """,
        supported_filters=["PARAMCD", "AVISIT"],
    ),

    # ── 13. Vital Sign Value ─────────────────────────────────────────────────
    "VITAL_SIGN_VALUE": KPIDefinition(
        kpi_id="VITAL_SIGN_VALUE",
        name="Vital Sign Measurement Summary",
        category="Vital Signs",
        description="Statistical summary of vital sign readings (Systolic BP, etc.).",
        primary_dataset="advs",
        required_datasets=["advs"],
        required_columns=["advs.PARAMCD", "advs.PARAM", "advs.AVAL", "advs.AVISIT"],
        dimensions=["PARAMCD", "AVISIT"],
        numerator="AVG(advs.AVAL)",
        denominator=None,
        formula="AVG(advs.AVAL) GROUP BY advs.PARAMCD, advs.AVISIT",
        calculation_type="average",
        sql_template="""
            SELECT PARAMCD, PARAM, AVISIT,
                   ROUND(AVG(AVAL), 2) AS mean_val,
                   ROUND(MIN(AVAL), 2) AS min_val,
                   ROUND(MAX(AVAL), 2) AS max_val
            FROM advs
            GROUP BY PARAMCD, PARAM, AVISIT;
        """,
        supported_filters=["TRT01A", "PARAMCD"],
    ),

    # ── 14. Vital Sign Change from Baseline ──────────────────────────────────
    "VITAL_SIGN_CHANGE_FROM_BASELINE": KPIDefinition(
        kpi_id="VITAL_SIGN_CHANGE_FROM_BASELINE",
        name="Vital Sign Change from Baseline",
        category="Vital Signs",
        description="Mean reduction/change in vital signs from baseline to post-baseline visits.",
        primary_dataset="advs",
        required_datasets=["advs"],
        required_columns=["advs.PARAMCD", "advs.TRT01A", "advs.AVISIT", "advs.CHG", "advs.PCHG"],
        dimensions=["PARAMCD", "TRT01A", "AVISIT"],
        numerator="AVG(advs.CHG)",
        denominator=None,
        formula="AVG(advs.CHG), AVG(advs.PCHG)",
        calculation_type="average",
        sql_template="""
            SELECT PARAMCD, TRT01A, AVISIT,
                   ROUND(AVG(BASE), 2) AS mean_baseline,
                   ROUND(AVG(AVAL), 2) AS mean_visit_val,
                   ROUND(AVG(CHG), 2) AS mean_change,
                   ROUND(AVG(PCHG), 2) AS mean_pct_change
            FROM advs
            WHERE AVISIT = 'WEEK 8'
            GROUP BY PARAMCD, TRT01A, AVISIT
            ORDER BY PARAMCD, TRT01A;
        """,
        supported_filters=["PARAMCD", "AVISIT"],
    ),

    # ── 15. Efficacy Response Count ──────────────────────────────────────────
    "EFFICACY_RESPONSE_COUNT": KPIDefinition(
        kpi_id="EFFICACY_RESPONSE_COUNT",
        name="Efficacy Responder Count",
        category="Efficacy",
        description="Total distinct subjects achieving clinical responder status (RESPFL = 'Y').",
        primary_dataset="adresp",
        required_datasets=["adresp"],
        required_columns=["adresp.USUBJID", "adresp.RESPFL", "adresp.AVISIT"],
        dimensions=["AVISIT"],
        numerator="COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END)",
        denominator=None,
        formula="COUNT(DISTINCT USUBJID) WHERE RESPFL = 'Y'",
        calculation_type="count",
        sql_template="""
            SELECT AVISIT, COUNT(DISTINCT USUBJID) AS responder_count
            FROM adresp
            WHERE RESPFL = 'Y'
            GROUP BY AVISIT;
        """,
        supported_filters=["TRT01A", "PARAMCD"],
    ),

    # ── 16. Efficacy Response Rate ───────────────────────────────────────────
    "EFFICACY_RESPONSE_RATE": KPIDefinition(
        kpi_id="EFFICACY_RESPONSE_RATE",
        name="Efficacy Response Rate by Treatment",
        category="Efficacy",
        description="Proportion of subjects in each treatment arm achieving clinical response.",
        primary_dataset="adresp",
        required_datasets=["adresp"],
        required_columns=["adresp.USUBJID", "adresp.TRT01A", "adresp.AVISIT", "adresp.RESPFL"],
        dimensions=["TRT01A", "AVISIT"],
        numerator="COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END)",
        denominator="COUNT(DISTINCT USUBJID)",
        formula="(responders / evaluable_subjects) * 100",
        calculation_type="rate",
        sql_template="""
            SELECT TRT01A, AVISIT,
                   COUNT(DISTINCT USUBJID) AS evaluable_subjects,
                   COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) AS responders,
                   ROUND(COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) * 100.0 / COUNT(DISTINCT USUBJID), 2) AS response_rate_pct
            FROM adresp
            WHERE AVISIT = 'WEEK 8'
            GROUP BY TRT01A, AVISIT
            ORDER BY response_rate_pct DESC;
        """,
        supported_filters=["AVISIT", "PARAMCD"],
    ),

    # ── 17. Subject Disposition ──────────────────────────────────────────────
    "SUBJECT_DISPOSITION": KPIDefinition(
        kpi_id="SUBJECT_DISPOSITION",
        name="Subject Trial Disposition / Completion",
        category="Disposition",
        description="Subject trial milestones, treatment completion, and end of study tracking.",
        primary_dataset="adsl",
        required_datasets=["adsl"],
        required_columns=["adsl.USUBJID", "adsl.TRT01A", "adsl.TRTSDT", "adsl.TRTEDT", "adsl.EOSDT"],
        dimensions=["TRT01A"],
        numerator="COUNT(DISTINCT adsl.USUBJID)",
        denominator=None,
        formula="COUNT(DISTINCT adsl.USUBJID) WHERE adsl.EOSDT IS NOT NULL",
        calculation_type="count",
        sql_template="""
            SELECT TRT01A,
                   COUNT(DISTINCT USUBJID) AS randomized_subjects,
                   COUNT(DISTINCT CASE WHEN TRTSDT IS NOT NULL THEN USUBJID END) AS treated_subjects,
                   COUNT(DISTINCT CASE WHEN EOSDT IS NOT NULL THEN USUBJID END) AS completed_study_subjects
            FROM adsl
            GROUP BY TRT01A;
        """,
        supported_filters=["TRT01A", "SITEID"],
    ),
}


def get_kpi(kpi_id: str) -> Optional[KPIDefinition]:
    """Retrieves a KPI definition by its identifier."""
    return KPIS.get(kpi_id.upper())


def list_kpis_by_category(category: Optional[str] = None) -> List[KPIDefinition]:
    """Returns all KPIs, optionally filtered by category."""
    if not category:
        return list(KPIS.values())
    return [k for k in KPIS.values() if k.category.lower() == category.lower()]
