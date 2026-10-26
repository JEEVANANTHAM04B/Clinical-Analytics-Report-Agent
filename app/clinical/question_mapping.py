"""
app/clinical/question_mapping.py
================================
Maps natural language clinical questions to required clinical datasets,
columns, relational joins, and statistical calculations without relying on LLMs.
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.clinical.kpi_definitions import KPIS, KPIDefinition
from app.clinical.dataset_metadata import DATASETS
from app.clinical.relationship_map import find_direct_relationship, are_tables_connected


@dataclass
class ClinicalQuestionPlan:
    """Structured execution plan for answering a clinical question."""
    question: str
    is_supported: bool
    question_type: str  # "enrollment", "demographics", "safety", "laboratory", "vital_signs", "efficacy", "disposition", "unknown"
    matched_kpi_id: Optional[str]
    metric: str
    primary_dataset: str
    datasets: List[str]
    dimensions: List[str]
    required_columns: List[str]
    calculation: str
    requires_join: bool
    join_tables: List[str]
    filter_conditions: List[str]
    suggested_sql: Optional[str]
    confidence: float
    explanation: str


# =============================================================================
# DETERMINISTIC CLINICAL QUESTION PATTERN MATCHER
# =============================================================================

def build_clinical_question_plan(question: str) -> ClinicalQuestionPlan:
    """
    Parses a user clinical question and deterministically resolves:
      1. Clinical domain / question type
      2. Matched KPI definition
      3. Required datasets and columns
      4. Join paths
      5. Precise statistical calculation
      6. Suggested SQL execution template

    Fails safely if question is unknown or asks for unsupported variables.
    """
    if not question or not question.strip():
        return ClinicalQuestionPlan(
            question="",
            is_supported=False,
            question_type="unknown",
            matched_kpi_id=None,
            metric="none",
            primary_dataset="",
            datasets=[],
            dimensions=[],
            required_columns=[],
            calculation="",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=None,
            confidence=0.0,
            explanation="Empty question provided."
        )

    q = question.strip().lower()

    # ── 1. AE Rate by Treatment Arm & TEAEs ──────────────────────────────────
    is_teae = (
        "treatment-emergent" in q
        or "treatment emergent" in q
        or "teae" in q
        or "teaes" in q
    )
    if is_teae or (
        ("treatment arm" in q or "treatment group" in q or "treatment groups" in q or "by arm" in q or "by treatment" in q or "arm" in q)
        and ("adverse event" in q or "ae" in q or "toxic" in q or "safety" in q)
        and ("rate" in q or "highest" in q or "incidence" in q or "percent" in q or "proportion" in q or "more" in q or "compare" in q or "comparison" in q)
    ):
        kpi = KPIS["AE_RATE_BY_TREATMENT"]
        if is_teae:
            sql_ae = (
                "SELECT adsl.TRT01A,\n"
                "       COUNT(DISTINCT adsl.USUBJID) AS total_subjects,\n"
                "       COUNT(DISTINCT adae.USUBJID) AS ae_subjects,\n"
                "       ROUND(COUNT(DISTINCT adae.USUBJID) * 100.0 / COUNT(DISTINCT adsl.USUBJID), 2) AS ae_rate_pct\n"
                "FROM adsl\n"
                "LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID AND adae.TRTEMFL = 'Y'\n"
                "GROUP BY adsl.TRT01A\n"
                "ORDER BY ae_rate_pct DESC;"
            )
            req_cols = ["adsl.USUBJID", "adsl.TRT01A", "adae.USUBJID", "adae.TRTEMFL"]
            filters = ["adae.TRTEMFL = 'Y'"]
            expl = "Matches treatment-emergent AE incidence (TRTEMFL = 'Y') by treatment arm joining ADSL and ADAE."
        else:
            sql_ae = kpi.sql_template.strip()
            req_cols = ["adsl.USUBJID", "adsl.TRT01A", "adae.USUBJID"]
            filters = []
            expl = "Matches safety incidence by treatment arm. Requires ADSL as denominator and ADAE as numerator joined on USUBJID."
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="safety",
            matched_kpi_id="AE_RATE_BY_TREATMENT",
            metric="adverse_event_rate_by_treatment",
            primary_dataset="adae",
            datasets=["adsl", "adae"],
            dimensions=["TRT01A"],
            required_columns=req_cols,
            calculation="COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID) * 100",
            requires_join=True,
            join_tables=["adsl", "adae"],
            filter_conditions=filters,
            suggested_sql=sql_ae,
            confidence=0.98,
            explanation=expl
        )

    # ── 2. Serious Adverse Events ────────────────────────────────────────────
    if (
        ("serious" in q or "sae" in q or "saes" in q)
        and ("adverse" in q or "event" in q or "safety" in q or "count" in q or "how many" in q)
    ):
        kpi = KPIS["SERIOUS_AE_COUNT"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="safety",
            matched_kpi_id="SERIOUS_AE_COUNT",
            metric="serious_adverse_event_count",
            primary_dataset="ae",
            datasets=["ae"],
            dimensions=[],
            required_columns=["ae.USUBJID", "ae.AESER"],
            calculation="COUNT(*) WHERE ae.AESER = 'Y'",
            requires_join=False,
            join_tables=[],
            filter_conditions=["ae.AESER = 'Y'"],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches serious adverse events query. Queries AE filtering for AESER = 'Y'."
        )

    # ── 3. Adverse Event Severity Distribution ──────────────────────────────
    if (
        ("severity" in q or "grade" in q or "mild" in q or "severe" in q)
        and ("adverse" in q or "ae" in q or "event" in q)
    ):
        has_treatment_stratification = bool(
            re.search(
                r'\b(treatment[\s_-]*arms?|treatment[\s_-]*groups?|arms?|cohorts?|trt01a)\b',
                q,
            )
        )
        if has_treatment_stratification:
            return ClinicalQuestionPlan(
                question=question,
                is_supported=True,
                question_type="safety",
                matched_kpi_id="AE_SEVERITY_DISTRIBUTION",
                metric="adverse_event_severity_distribution",
                primary_dataset="adae",
                datasets=["adsl", "adae"],
                dimensions=["TRT01A", "AESEV"],
                required_columns=["adsl.USUBJID", "adsl.TRT01A", "adae.USUBJID", "adae.AESEV"],
                calculation="COUNT(*) GROUP BY adsl.TRT01A, adae.AESEV",
                requires_join=True,
                join_tables=["adsl", "adae"],
                filter_conditions=[],
                suggested_sql="""SELECT adsl.TRT01A AS treatment_arm, adae.AESEV AS severity, COUNT(*) AS event_count
FROM adsl
JOIN adae ON adsl.USUBJID = adae.USUBJID
GROUP BY adsl.TRT01A, adae.AESEV
ORDER BY adsl.TRT01A, event_count DESC;""".strip(),
                confidence=0.95,
                explanation="Matches AE severity breakdown across treatment arms. Joins ADSL and ADAE grouping by TRT01A and AESEV."
            )

        kpi = KPIS["AE_SEVERITY_DISTRIBUTION"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="safety",
            matched_kpi_id="AE_SEVERITY_DISTRIBUTION",
            metric="adverse_event_severity_distribution",
            primary_dataset="adae",
            datasets=["adae"],
            dimensions=["AESEV"],
            required_columns=["adae.USUBJID", "adae.AESEV"],
            calculation="COUNT(*) GROUP BY adae.AESEV",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches AE severity breakdown. Aggregates ADAE grouping by AESEV."
        )

    # ── 4. Overall Adverse Event Count / Rate ────────────────────────────────
    if ("adverse event" in q or "adverse events" in q or "ae count" in q) and ("rate" in q or "percentage" in q):
        kpi = KPIS["ADVERSE_EVENT_RATE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="safety",
            matched_kpi_id="ADVERSE_EVENT_RATE",
            metric="adverse_event_rate",
            primary_dataset="adae",
            datasets=["adsl", "adae"],
            dimensions=[],
            required_columns=["adsl.USUBJID", "adae.USUBJID"],
            calculation="COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID) * 100",
            requires_join=True,
            join_tables=["adsl", "adae"],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.92,
            explanation="Matches general adverse event rate. Calculates percentage of safety population with an AE."
        )

    # ── Top / Frequently Reported Adverse Events ────────────────────────────
    if (
        ("most frequent" in q or "frequently reported" in q or "top" in q or "common" in q)
        and ("adverse event" in q or "ae" in q or "adverse events" in q)
    ):
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="safety",
            matched_kpi_id="TOP_ADVERSE_EVENTS",
            metric="top_adverse_events",
            primary_dataset="adae",
            datasets=["adae"],
            dimensions=["AEDECOD"],
            required_columns=["adae.USUBJID", "adae.AEDECOD"],
            calculation="COUNT(DISTINCT adae.USUBJID) GROUP BY adae.AEDECOD ORDER BY COUNT(DISTINCT adae.USUBJID) DESC LIMIT 5",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql="SELECT adae.AEDECOD AS adverse_event, COUNT(DISTINCT adae.USUBJID) AS subject_count FROM adae GROUP BY adae.AEDECOD ORDER BY subject_count DESC LIMIT 5;",
            confidence=0.95,
            explanation="Matches top frequently reported adverse events. Aggregates ADAE grouping by AEDECOD in descending order with LIMIT 5."
        )

    if "adverse event" in q or "how many ae" in q or "total ae" in q or "adverse events occurred" in q:
        kpi = KPIS["ADVERSE_EVENT_COUNT"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="safety",
            matched_kpi_id="ADVERSE_EVENT_COUNT",
            metric="adverse_event_count",
            primary_dataset="ae",
            datasets=["ae"],
            dimensions=[],
            required_columns=["ae.USUBJID", "ae.AESEQ"],
            calculation="COUNT(*)",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches total adverse event count. Aggregates all incident records in AE."
        )

    # ── 5. Laboratory Change from Baseline ───────────────────────────────────
    if (
        ("lab" in q or "laboratory" in q or "hgb" in q or "hemoglobin" in q or "alt" in q or "ast" in q)
        and ("change" in q or "baseline" in q or "week 8" in q or "week 4" in q or "difference" in q or "reduction" in q or "compare" in q or "larger" in q)
    ):
        kpi = KPIS["LAB_CHANGE_FROM_BASELINE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="laboratory",
            matched_kpi_id="LAB_CHANGE_FROM_BASELINE",
            metric="lab_change_from_baseline",
            primary_dataset="adlb",
            datasets=["adlb"],
            dimensions=["PARAMCD", "TRT01A", "AVISIT"],
            required_columns=["adlb.PARAMCD", "adlb.TRT01A", "adlb.AVISIT", "adlb.CHG", "adlb.PCHG"],
            calculation="AVG(adlb.CHG), AVG(adlb.PCHG) WHERE AVISIT = 'WEEK 8'",
            requires_join=False,
            join_tables=[],
            filter_conditions=["adlb.AVISIT = 'WEEK 8'"],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.96,
            explanation="Matches laboratory change from baseline analysis in ADLB for Week 8."
        )

    if "lab" in q or "laboratory" in q or "hemoglobin" in q or "hgb" in q:
        kpi = KPIS["LAB_VALUE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="laboratory",
            matched_kpi_id="LAB_VALUE",
            metric="laboratory_value_summary",
            primary_dataset="adlb",
            datasets=["adlb"],
            dimensions=["PARAMCD", "AVISIT"],
            required_columns=["adlb.PARAMCD", "adlb.PARAM", "adlb.AVAL", "adlb.AVISIT"],
            calculation="AVG(adlb.AVAL), MIN(adlb.AVAL), MAX(adlb.AVAL)",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.92,
            explanation="Matches laboratory measurement summary in ADLB."
        )

    # ── 6. Vital Signs Change from Baseline ──────────────────────────────────
    if (
        ("vital" in q or "vitals" in q or "blood pressure" in q or "sysbp" in q or "bp" in q)
        and ("change" in q or "baseline" in q or "week 8" in q or "reduction" in q or "compare" in q or "happened" in q or "during" in q)
    ):
        kpi = KPIS["VITAL_SIGN_CHANGE_FROM_BASELINE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="vital_signs",
            matched_kpi_id="VITAL_SIGN_CHANGE_FROM_BASELINE",
            metric="vital_sign_change_from_baseline",
            primary_dataset="advs",
            datasets=["advs"],
            dimensions=["PARAMCD", "TRT01A", "AVISIT"],
            required_columns=["advs.PARAMCD", "advs.TRT01A", "advs.AVISIT", "advs.CHG", "advs.PCHG"],
            calculation="AVG(advs.CHG), AVG(advs.PCHG) WHERE AVISIT = 'WEEK 8'",
            requires_join=False,
            join_tables=[],
            filter_conditions=["advs.AVISIT = 'WEEK 8'"],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.96,
            explanation="Matches vital sign change from baseline in ADVS."
        )

    if "vital" in q or "vitals" in q or "blood pressure" in q or "sysbp" in q:
        kpi = KPIS["VITAL_SIGN_VALUE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="vital_signs",
            matched_kpi_id="VITAL_SIGN_VALUE",
            metric="vital_sign_summary",
            primary_dataset="advs",
            datasets=["advs"],
            dimensions=["PARAMCD", "AVISIT"],
            required_columns=["advs.PARAMCD", "advs.PARAM", "advs.AVAL", "advs.AVISIT"],
            calculation="AVG(advs.AVAL)",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.90,
            explanation="Matches vital sign measurement summary in ADVS."
        )

    # ── 7. Efficacy Response Rate ────────────────────────────────────────────
    if (
        ("response" in q or "responder" in q or "efficacy" in q)
        and ("rate" in q or "percent" in q or "proportion" in q or "highest" in q)
    ):
        kpi = KPIS["EFFICACY_RESPONSE_RATE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="efficacy",
            matched_kpi_id="EFFICACY_RESPONSE_RATE",
            metric="efficacy_response_rate",
            primary_dataset="adresp",
            datasets=["adresp"],
            dimensions=["TRT01A", "AVISIT"],
            required_columns=["adresp.USUBJID", "adresp.TRT01A", "adresp.AVISIT", "adresp.RESPFL"],
            calculation="COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) / COUNT(DISTINCT USUBJID) * 100",
            requires_join=False,
            join_tables=[],
            filter_conditions=["adresp.AVISIT = 'WEEK 8'"],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.96,
            explanation="Matches efficacy response rate query. Evaluates responder flag RESPFL in ADRESP by treatment arm."
        )

    if "response" in q or "responder" in q or "responders" in q or "responded" in q or "effective" in q:
        kpi = KPIS["EFFICACY_RESPONSE_COUNT"]
        by_arm = ("treatment" in q or "arm" in q or "drug" in q or "placebo" in q)
        if by_arm:
            dims = ["TRT01A", "AVISIT"]
            sql_resp = "SELECT TRT01A, AVISIT, COUNT(DISTINCT USUBJID) AS responder_count FROM adresp WHERE RESPFL = 'Y' GROUP BY TRT01A, AVISIT;"
            calc = "COUNT(DISTINCT USUBJID) WHERE adresp.RESPFL = 'Y' GROUP BY TRT01A, AVISIT"
            req_cols = ["adresp.USUBJID", "adresp.RESPFL", "adresp.TRT01A", "adresp.AVISIT"]
            expl = "Matches efficacy responder count by treatment arm in ADRESP."
        else:
            dims = ["AVISIT"]
            sql_resp = kpi.sql_template.strip()
            calc = "COUNT(DISTINCT USUBJID) WHERE adresp.RESPFL = 'Y'"
            req_cols = ["adresp.USUBJID", "adresp.RESPFL", "adresp.AVISIT"]
            expl = "Matches efficacy responder count in ADRESP."
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="efficacy",
            matched_kpi_id="EFFICACY_RESPONSE_COUNT",
            metric="efficacy_response_count",
            primary_dataset="adresp",
            datasets=["adresp"],
            dimensions=dims,
            required_columns=req_cols,
            calculation=calc,
            requires_join=False,
            join_tables=[],
            filter_conditions=["adresp.RESPFL = 'Y'"],
            suggested_sql=sql_resp,
            confidence=0.95,
            explanation=expl
        )

    # ── 8. Enrollment by Site ────────────────────────────────────────────────
    if ("site" in q or "sites" in q or "center" in q or "investigator" in q) and ("enroll" in q or "highest" in q or "count" in q or "recruit" in q):
        kpi = KPIS["ENROLLMENT_BY_SITE"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="enrollment",
            matched_kpi_id="ENROLLMENT_BY_SITE",
            metric="enrollment_by_site",
            primary_dataset="dm",
            datasets=["sites", "dm"],
            dimensions=["SITEID", "SITE_NAME"],
            required_columns=["sites.SITEID", "sites.SITE_NAME", "dm.USUBJID"],
            calculation="COUNT(DISTINCT dm.USUBJID) GROUP BY sites.SITEID",
            requires_join=True,
            join_tables=["sites", "dm"],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches site enrollment query. Joins SITES and DM on SITEID to count enrolled subjects per center."
        )

    # ── 9. Average Age ───────────────────────────────────────────────────────
    if ((re.search(r"\bage\b", q) or re.search(r"\bages\b", q))
            and "distribution" in q
            and ("mean" in q or "average" in q)
            and ("treatment" in q or "arm" in q or "cohort" in q)):
        sql_age = """SELECT adsl.TRT01A AS treatment_arm,
    COUNT(DISTINCT adsl.USUBJID) AS subjects_with_age,
    ROUND(AVG(adsl.AGE), 2) AS mean_age,
    COUNT(DISTINCT CASE WHEN adsl.AGE < 40 THEN adsl.USUBJID END) AS age_under_40,
    COUNT(DISTINCT CASE WHEN adsl.AGE BETWEEN 40 AND 59 THEN adsl.USUBJID END) AS age_40_to_59,
    COUNT(DISTINCT CASE WHEN adsl.AGE >= 60 THEN adsl.USUBJID END) AS age_60_plus
FROM adsl
WHERE adsl.AGE IS NOT NULL AND adsl.TRT01A IS NOT NULL
GROUP BY adsl.TRT01A;"""
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="demographics",
            matched_kpi_id="AVERAGE_AGE",
            metric="age_distribution_and_mean",
            primary_dataset="adsl",
            datasets=["adsl"],
            dimensions=["TRT01A"],
            required_columns=["adsl.USUBJID", "adsl.TRT01A", "adsl.AGE"],
            calculation=("ROUND(AVG(adsl.AGE), 2) for mean age; "
                         "COUNT(DISTINCT adsl.USUBJID) for subjects with recorded age; "
                         "COUNT(DISTINCT CASE WHEN adsl.AGE < 40 THEN adsl.USUBJID END), "
                         "COUNT(DISTINCT CASE WHEN adsl.AGE BETWEEN 40 AND 59 THEN adsl.USUBJID END), "
                         "COUNT(DISTINCT CASE WHEN adsl.AGE >= 60 THEN adsl.USUBJID END) "
                         "for age bands under 40, 40-59, and 60 or older"),
            requires_join=False,
            join_tables=[],
            filter_conditions=["adsl.AGE IS NOT NULL", "adsl.TRT01A IS NOT NULL"],
            suggested_sql=sql_age,
            confidence=0.97,
            explanation=("Summarizes recorded age in ADSL by actual treatment arm. "
                         "The age bands are proposed for review; no median or unrequested statistic is added."),
        )
    if (re.search(r"\bage\b", q) or re.search(r"\bages\b", q) or "old" in q) and ("average" in q or "mean" in q or "old" in q or "distribution" in q or "profile" in q or "summary" in q or "compare" in q or "minimum" in q or "maximum" in q or "min" in q or "max" in q):
        kpi = KPIS["AVERAGE_AGE"]
        by_arm = ("treatment" in q or "arm" in q or "cohort" in q or "placebo" in q or "drug" in q)
        if "minimum" in q or "maximum" in q or "min" in q or "max" in q:
            sql_age = "SELECT MIN(AGE) AS min_age, MAX(AGE) AS max_age FROM dm;"
            dims = []
            req_cols = ["dm.AGE"]
            calc = "MIN(dm.AGE), MAX(dm.AGE)"
            expl = "Matches demographic age min and max bounds in DM."
        elif by_arm:
            sql_age = "SELECT ARM, ROUND(AVG(AGE), 2) AS mean_age, MIN(AGE) AS min_age, MAX(AGE) AS max_age FROM dm GROUP BY ARM;"
            dims = ["ARM"]
            req_cols = ["dm.ARM", "dm.AGE"]
            calc = "AVG(dm.AGE) GROUP BY dm.ARM"
            expl = "Matches demographic age distribution by treatment arm in DM."
        else:
            sql_age = kpi.sql_template.strip()
            dims = []
            req_cols = ["dm.AGE"]
            calc = "AVG(dm.AGE)"
            expl = "Matches demographic age question. Computes mean of AGE from DM."
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="demographics",
            matched_kpi_id="AVERAGE_AGE",
            metric="average_age",
            primary_dataset="dm",
            datasets=["dm"],
            dimensions=dims,
            required_columns=req_cols,
            calculation=calc,
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=sql_age,
            confidence=0.97,
            explanation=expl
        )

    # ── 10. Sex Distribution ─────────────────────────────────────────────────
    if "sex" in q or "gender" in q or "male" in q or "female" in q:
        kpi = KPIS["SEX_DISTRIBUTION"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="demographics",
            matched_kpi_id="SEX_DISTRIBUTION",
            metric="sex_distribution",
            primary_dataset="dm",
            datasets=["dm"],
            dimensions=["SEX"],
            required_columns=["dm.USUBJID", "dm.SEX"],
            calculation="COUNT(DISTINCT dm.USUBJID) GROUP BY dm.SEX",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches demographic sex distribution in DM."
        )

    # ── 11. Subjects by Treatment Arm ────────────────────────────────────────
    has_treatment_signal = (
        "treatment arm" in q or "treatment-arm" in q or "treatment group" in q or "treatment groups" in q
        or "treatment allocation" in q or "by treatment" in q or "each treatment" in q
        or "treatment" in q or "treatments" in q or "arm" in q or "cohort" in q
        or "versus" in q or "vs" in q
        or ("drug" in q and "placebo" in q)
        or ("compare" in q and ("placebo" in q or "drug" in q or "treatment" in q or "arm" in q))
        or "compared with placebo" in q
    )
    has_subject_count_signal = (
        "how many" in q or "subject" in q or "participant" in q or "patient" in q
        or "distribution" in q or "breakdown" in q or "allocation" in q or "population" in q
        or "compare" in q or "count" in q or "versus" in q or "vs" in q or "received" in q
    )
    if not is_teae and has_treatment_signal and has_subject_count_signal:
        kpi = KPIS["SUBJECTS_BY_TREATMENT_ARM"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="demographics",
            matched_kpi_id="SUBJECTS_BY_TREATMENT_ARM",
            metric="subjects_by_treatment_arm",
            primary_dataset="adsl",
            datasets=["adsl"],
            dimensions=["TRT01A"],
            required_columns=["adsl.USUBJID", "adsl.TRT01A"],
            calculation="COUNT(DISTINCT adsl.USUBJID) GROUP BY adsl.TRT01A",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches subject treatment arm breakdown in ADSL."
        )

    # ── 12. Subject Disposition / Completion ─────────────────────────────────
    is_discontinuation = any(
        w in q for w in [
            "discontinue", "discontinued", "discontinuations",
            "dropout", "drop out", "dropped out", "lost",
            "did not complete", "not complete", "failed to complete"
        ]
    )
    is_completion = any(
        w in q for w in [
            "completed", "complete the study", "completers",
            "completed the study", "completion", "finished"
        ]
    ) and not is_discontinuation

    if is_discontinuation or is_completion or "disposition" in q or "status" in q:
        kpi = KPIS["SUBJECT_DISPOSITION"]
        if ("percentage" in q or "percent" in q) and is_discontinuation:
            sql_disposition = "SELECT ROUND(COUNT(CASE WHEN EOSDT IS NULL THEN USUBJID END) * 100.0 / COUNT(DISTINCT USUBJID), 2) AS discontinuation_percentage_pct FROM adsl;"
            calc = "COUNT(CASE WHEN adsl.EOSDT IS NULL THEN USUBJID END) / COUNT(DISTINCT USUBJID) * 100"
            filters = []
        elif "percentage" in q or "percent" in q:
            sql_disposition = "SELECT ROUND(COUNT(CASE WHEN EOSDT IS NOT NULL THEN USUBJID END) * 100.0 / COUNT(DISTINCT USUBJID), 2) AS completion_percentage_pct FROM adsl;"
            calc = "COUNT(CASE WHEN adsl.EOSDT IS NOT NULL THEN USUBJID END) / COUNT(DISTINCT USUBJID) * 100"
            filters = []
        elif is_discontinuation:
            sql_disposition = "SELECT COUNT(DISTINCT USUBJID) AS discontinued_subjects FROM adsl WHERE EOSDT IS NULL;"
            calc = "COUNT(DISTINCT USUBJID) WHERE adsl.EOSDT IS NULL"
            filters = ["adsl.EOSDT IS NULL"]
        elif is_completion:
            sql_disposition = "SELECT COUNT(DISTINCT USUBJID) AS completed_subjects FROM adsl WHERE EOSDT IS NOT NULL;"
            calc = "COUNT(DISTINCT USUBJID) WHERE adsl.EOSDT IS NOT NULL"
            filters = ["adsl.EOSDT IS NOT NULL"]
        else:
            sql_disposition = kpi.sql_template.strip()
            calc = "COUNT(DISTINCT USUBJID) WHERE adsl.EOSDT IS NOT NULL"
            filters = []

        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="disposition",
            matched_kpi_id="SUBJECT_DISPOSITION",
            metric="subject_disposition",
            primary_dataset="adsl",
            datasets=["adsl"],
            dimensions=["TRT01A"],
            required_columns=["adsl.USUBJID", "adsl.TRT01A", "adsl.EOSDT"],
            calculation=calc,
            requires_join=False,
            join_tables=[],
            filter_conditions=filters,
            suggested_sql=sql_disposition,
            confidence=0.90,
            explanation="Matches subject disposition tracking in ADSL."
        )

    # ── 13. Total Subjects / Enrolled ────────────────────────────────────────
    if "joined" in q or "recruited" in q or "enrolled" in q or "how many patients" in q or "how many subjects" in q or "how many participants" in q or "total subjects" in q:
        kpi = KPIS["TOTAL_SUBJECTS"]
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="enrollment",
            matched_kpi_id="TOTAL_SUBJECTS",
            metric="total_subjects",
            primary_dataset="dm",
            datasets=["dm"],
            dimensions=[],
            required_columns=["dm.USUBJID"],
            calculation="COUNT(DISTINCT dm.USUBJID)",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=kpi.sql_template.strip(),
            confidence=0.95,
            explanation="Matches total subject enrollment query. Counts distinct USUBJID in DM."
        )

    # ── 13b. Clinical Sites / Participating Sites ────────────────────────────
    if ("site" in q or "sites" in q or "center" in q or "centers" in q) and ("participating" in q or "recorded" in q or "how many" in q or "count" in q or "total" in q or "number of" in q) and not any(k in q for k in ["subject", "patient", "recruited"]):
        kpi = KPIS.get("CLINICAL_SITES_COUNT")
        sql_sites = kpi.sql_template.strip() if kpi else "SELECT COUNT(DISTINCT SITEID) AS site_count FROM sites;"
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="enrollment",
            matched_kpi_id="CLINICAL_SITES_COUNT",
            metric="clinical_sites_count",
            primary_dataset="sites",
            datasets=["sites"],
            dimensions=[],
            required_columns=["sites.SITEID"],
            calculation="COUNT(DISTINCT sites.SITEID)",
            requires_join=False,
            join_tables=[],
            filter_conditions=[],
            suggested_sql=sql_sites,
            confidence=0.96,
            explanation="Counts total distinct participating clinical sites recorded in the SITES table."
        )

    # ── 13c. Safety Population Protocol Definition ───────────────────────────
    if ("safety population" in q or "saffl" in q) and ("definition" in q or "mean" in q or "protocol" in q or "criteria" in q or "what is" in q or "what does" in q):
        kpi = KPIS.get("SAFETY_POPULATION")
        sql_saf = kpi.sql_template.strip() if kpi else "SELECT COUNT(DISTINCT USUBJID) AS safety_population_count FROM adsl WHERE SAFFL = 'Y';"
        return ClinicalQuestionPlan(
            question=question,
            is_supported=True,
            question_type="demographics",
            matched_kpi_id="SAFETY_POPULATION",
            metric="safety_population",
            primary_dataset="adsl",
            datasets=["adsl"],
            dimensions=["SAFFL"],
            required_columns=["adsl.USUBJID", "adsl.SAFFL"],
            calculation="COUNT(DISTINCT adsl.USUBJID) WHERE adsl.SAFFL = 'Y'",
            requires_join=False,
            join_tables=[],
            filter_conditions=["adsl.SAFFL = 'Y'"],
            suggested_sql=sql_saf,
            confidence=0.95,
            explanation="Queries the safety population (SAFFL = 'Y') in ADSL."
        )

    # ── 14. Unsupported / Unknown Question Fallback ──────────────────────────
    return ClinicalQuestionPlan(
        question=question,
        is_supported=False,
        question_type="unknown",
        matched_kpi_id=None,
        metric="unrecognized_metric",
        primary_dataset="",
        datasets=[],
        dimensions=[],
        required_columns=[],
        calculation="",
        requires_join=False,
        join_tables=[],
        filter_conditions=[],
        suggested_sql=None,
        confidence=0.0,
        explanation=f"Question '{question}' could not be safely mapped to an approved clinical KPI or dataset."
    )
