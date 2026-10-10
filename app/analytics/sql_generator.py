import re
from typing import Optional, Tuple, Dict, Any, List

from app.ai.llm import generate_response
from app.clinical import (
    registry as clinical_registry,
    build_clinical_question_plan,
    ClinicalQuestionPlan,
)


# ============================================================
# SCHEMA CONTEXT DETECTION
# ============================================================

def _is_clinical_context(database_schema: Optional[Dict[str, Any]]) -> bool:
    """
    Detect whether the execution context targets CDISC clinical-trial schema
    or legacy EHR schema. Defaults to clinical-trial schema as active.
    """
    if not database_schema or not database_schema.get("tables"):
        return True

    tables = {t.lower() for t in database_schema.get("tables", {})}
    clinical_markers = {"dm", "adsl", "ae", "adae", "adlb", "advs", "adresp", "study", "sites"}
    legacy_markers = {"encounters", "conditions", "patients", "medications", "observations", "procedures"}

    if any(t in tables for t in clinical_markers):
        return True
    if any(t in tables for t in legacy_markers):
        return False

    return True


# ============================================================
# CLINICAL PROMPT BUILDER
# ============================================================

def _build_clinical_prompt(
    user_question: str,
    analysis_plan: str,
    database_schema: Optional[Dict[str, Any]],
    plan: Optional[ClinicalQuestionPlan],
) -> str:
    """
    Builds an authoritative prompt for Gemini targeting the 13 CDISC
    clinical-trial tables, including approved relationships, KPI logic,
    and few-shot examples.
    """
    # 1. Format schema context from ClinicalSchemaRegistry
    schema_context = clinical_registry.build_schema_context_for_prompt()

    # 2. Plan guidance
    plan_guidance_parts: List[str] = []
    if plan and plan.is_supported:
        plan_guidance_parts.append(f"Domain / Category: {plan.question_type.upper()}")
        if plan.matched_kpi_id:
            plan_guidance_parts.append(f"Matched Clinical KPI: {plan.matched_kpi_id}")
        plan_guidance_parts.append(f"Target Metric: {plan.metric}")
        plan_guidance_parts.append(f"Required Datasets: {', '.join(plan.datasets)}")
        plan_guidance_parts.append(f"Required Columns: {', '.join(plan.required_columns)}")
        plan_guidance_parts.append(f"Calculation Logic: {plan.calculation}")
        if plan.dimensions:
            plan_guidance_parts.append(f"Grouping Dimensions: {', '.join(plan.dimensions)}")
        if plan.filter_conditions:
            plan_guidance_parts.append(f"Filtering Conditions: {', '.join(plan.filter_conditions)}")
        if plan.requires_join:
            plan_guidance_parts.append(f"Join Required: Yes (between {', '.join(plan.join_tables)})")
        else:
            plan_guidance_parts.append("Join Required: No (single-table query)")

    plan_guidance_str = (
        "\n".join(f"- {p}" for p in plan_guidance_parts)
        if plan_guidance_parts
        else "- No predefined KPI plan matched. Follow standard CDISC SDTM/ADaM schema relationships."
    )

    analysis_plan_block = (
        analysis_plan.strip()
        if analysis_plan and analysis_plan.strip()
        else "None provided."
    )

    return f"""You are an expert MySQL query generator for a CDISC clinical-trial analytics platform.

Generate ONE valid, read-only MySQL SELECT query that answers the clinical question.

User Question:
{user_question}

Approved Analysis Plan:
{analysis_plan_block}

Clinical Question Plan Guidance:
{plan_guidance_str}

==================================================
CDISC CLINICAL TRIAL SCHEMA CONTEXT:
{schema_context}

==================================================
FEW-SHOT CLINICAL TRIAL QUERY EXAMPLES:

--- Example 1: Total Enrolled Patients ---
Question: How many patients are enrolled?
SQL:
SELECT COUNT(DISTINCT USUBJID) AS total_enrolled_patients
FROM dm;

--- Example 2: Mean / Average Age ---
Question: What is the average age of patients?
SQL:
SELECT ROUND(AVG(AGE), 2) AS average_age
FROM dm;

--- Example 3: Sex Breakdown ---
Question: What is the breakdown of subjects by sex?
SQL:
SELECT SEX AS sex, COUNT(DISTINCT USUBJID) AS subject_count
FROM dm
GROUP BY SEX;

--- Example 4: Treatment Arm AE Rate ---
Question: Which treatment arm has the highest adverse event rate?
SQL:
SELECT adsl.TRT01A AS treatment_arm,
       COUNT(DISTINCT adsl.USUBJID) AS total_subjects,
       COUNT(DISTINCT adae.USUBJID) AS ae_subjects,
       ROUND(COUNT(DISTINCT adae.USUBJID) * 100.0 / COUNT(DISTINCT adsl.USUBJID), 2) AS ae_rate_pct
FROM adsl
LEFT JOIN adae ON adsl.USUBJID = adae.USUBJID
GROUP BY adsl.TRT01A
ORDER BY ae_rate_pct DESC;

--- Example 5: Serious Adverse Events ---
Question: How many serious adverse events occurred?
SQL:
SELECT COUNT(*) AS serious_adverse_events
FROM ae
WHERE AESER = 'Y';

--- Example 6: Laboratory Change from Baseline ---
Question: What is the laboratory change from baseline?
SQL:
SELECT PARAMCD AS param_cd, TRT01A AS treatment_arm, AVISIT AS visit,
       ROUND(AVG(BASE), 2) AS mean_baseline,
       ROUND(AVG(AVAL), 2) AS mean_visit_value,
       ROUND(AVG(CHG), 2) AS mean_change,
       ROUND(AVG(PCHG), 2) AS mean_pct_change
FROM adlb
WHERE AVISIT = 'WEEK 8'
GROUP BY PARAMCD, TRT01A, AVISIT
ORDER BY PARAMCD, TRT01A;

--- Example 7: Vital Sign Change from Baseline ---
Question: What is the vital sign change from baseline?
SQL:
SELECT PARAMCD AS param_cd, TRT01A AS treatment_arm, AVISIT AS visit,
       ROUND(AVG(BASE), 2) AS mean_baseline,
       ROUND(AVG(AVAL), 2) AS mean_visit_val,
       ROUND(AVG(CHG), 2) AS mean_change,
       ROUND(AVG(PCHG), 2) AS mean_pct_change
FROM advs
WHERE AVISIT = 'WEEK 8'
GROUP BY PARAMCD, TRT01A, AVISIT
ORDER BY PARAMCD, TRT01A;

--- Example 8: Efficacy Response Rate by Treatment ---
Question: What is the efficacy response rate by treatment?
SQL:
SELECT TRT01A AS treatment_arm, AVISIT AS visit,
       COUNT(DISTINCT USUBJID) AS evaluable_subjects,
       COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) AS responders,
       ROUND(COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) * 100.0 / COUNT(DISTINCT USUBJID), 2) AS response_rate_pct
FROM adresp
WHERE AVISIT = 'WEEK 8'
GROUP BY TRT01A, AVISIT
ORDER BY response_rate_pct DESC;

--- Example 9: Site Enrollment Distribution ---
Question: Which site has the highest enrollment?
SQL:
SELECT sites.SITEID AS site_id, sites.SITE_NAME AS site_name, COUNT(DISTINCT dm.USUBJID) AS enrolled_subjects
FROM sites
JOIN dm ON sites.SITEID = dm.SITEID
GROUP BY sites.SITEID, sites.SITE_NAME
ORDER BY enrolled_subjects DESC;

==================================================
RULES FOR CLINICAL SQL GENERATION:

1. Clinical Schema Strictness (CRITICAL):
   - Query ONLY against the 13 clinical trial tables: study, sites, dm, ae, ex, lb, qs, vs, adsl, adae, adlb, advs, adresp.
   - Use ONLY valid column names defined in the schema for each table.
   - Do NOT invent tables, columns, or relationships. If the user question requires clinical tables, domains, or measurements not present in the clinical-trial schema (e.g., pharmacy billing, insurance claims, genomics), do NOT fabricate tables.

2. Plan & KPI Adherence:
   - When a Clinical Question Plan is provided, adhere strictly to the Required Datasets, Required Columns, Dimensions, and Calculation.
   - If single-table query is specified (join_required=false), query ONLY that single dataset without unnecessary joins.
   - If join is required, join ONLY using approved relationships (e.g., sites.SITEID = dm.SITEID, dm.USUBJID = adsl.USUBJID, adsl.USUBJID = adae.USUBJID).

3. Statistical & Metric Accuracy:
   - Adverse Event Rate: Numerator is distinct subjects with AE (from adae), Denominator is total subjects in trial or treatment arm (from adsl).
   - Treatment-Emergent Adverse Events (TEAE): Filtered on TRTEMFL = 'Y' (adae.TRTEMFL = 'Y').
   - Subject Completion: Filtered on EOSDT IS NOT NULL in adsl (adsl.EOSDT IS NOT NULL).
   - Subject Discontinuation / Dropout: Filtered on EOSDT IS NULL in adsl (adsl.EOSDT IS NULL).
   - Efficacy Response Rate: Calculated using adresp with RESPFL = 'Y' over evaluable subjects.
   - Change from Baseline: Calculated in ADLB or ADVS using CHG = AVAL - BASE and PCHG = (CHG / BASE) * 100, filtered for relevant visit (e.g. AVISIT = 'WEEK 8').
   - Serious Adverse Events: Filtered on AESER = 'Y'.

4. Aliasing & Formatting:
   - Place primary category/dimension column FIRST in SELECT.
   - Place aggregated metric(s) SECOND in SELECT.
   - Use clean, lower_snake_case column aliases.
   - Generate only ONE valid SELECT statement.
   - Do NOT return markdown code blocks, explanations, or comments. Return ONLY the raw MySQL query string.

5. Forbidden Constructs (CRITICAL):
   - Do NOT use window functions (OVER / PARTITION BY).
   - Do NOT use non-standard functions like STDDEV or MEDIAN (use standard AVG, COUNT, MIN, MAX, SUM).
   - Do NOT use UNION or subquery derived tables in JOIN clauses (e.g. JOIN (SELECT ...)).
   - Join tables directly using approved primary foreign key relationships (e.g. adsl.USUBJID = adae.USUBJID).
"""


# ============================================================
# CLINICAL PLAN CONSISTENCY CHECKER
# ============================================================

def _check_sql_vs_clinical_plan(sql: str, plan: Optional[ClinicalQuestionPlan]) -> Tuple[bool, str]:
    """
    Lightweight inline validation: does the LLM-generated SQL satisfy
    the structural requirements of the clinical question plan?
    """
    if not plan or not plan.is_supported:
        return True, ""

    sql_l = sql.lower()

    # 1. Required datasets
    for ds in plan.datasets:
        if not re.search(rf"\b{re.escape(ds.lower())}\b", sql_l):
            return False, f"SQL is missing required clinical dataset: {ds}"

    # 2. Single-table vs join constraint
    if not plan.requires_join and (" join " in sql_l or "\njoin " in sql_l):
        return False, f"SQL introduces unexpected JOIN for single-table metric '{plan.metric}'"

    # 3. Filter check (e.g. AESER = 'Y' for serious adverse events)
    if plan.matched_kpi_id == "SERIOUS_AE_COUNT":
        if "aeser" not in sql_l or "'y'" not in sql_l:
            return False, "SQL missing AESER = 'Y' filter for serious adverse events"

    # 4. Filter check (e.g. RESPFL = 'Y' for efficacy response)
    if plan.matched_kpi_id in ("EFFICACY_RESPONSE_COUNT", "EFFICACY_RESPONSE_RATE"):
        if "respfl" not in sql_l or "'y'" not in sql_l:
            return False, "SQL missing RESPFL = 'Y' filter for efficacy response"

    # 5. Filter check (TRTEMFL = 'Y' for treatment-emergent adverse events)
    if any("trtemfl = 'y'" in f.lower() for f in plan.filter_conditions):
        if "trtemfl" not in sql_l or "'y'" not in sql_l:
            return False, "SQL missing TRTEMFL = 'Y' filter for treatment-emergent adverse events"

    # 6. Filter check (EOSDT IS NULL for discontinuation, EOSDT IS NOT NULL for completion)
    if any("eosdt is null" in f.lower() for f in plan.filter_conditions):
        if "eosdt is not null" in sql_l:
            return False, "SQL incorrectly uses EOSDT IS NOT NULL for discontinued subjects (requires EOSDT IS NULL)"
    if any("eosdt is not null" in f.lower() for f in plan.filter_conditions):
        if "eosdt is null" in sql_l and "eosdt is not null" not in sql_l:
            return False, "SQL incorrectly uses EOSDT IS NULL for completed subjects (requires EOSDT IS NOT NULL)"

    # 7. Guard against forbidden constructs that cause validation failure
    if " over " in sql_l or " over(" in sql_l or " over\n" in sql_l:
        return False, "SQL uses unauthorized window function OVER ()"
    if "stddev" in sql_l or "median" in sql_l:
        return False, "SQL uses unauthorized statistical function STDDEV/MEDIAN"
    if " union " in sql_l:
        return False, "SQL uses unauthorized UNION construct"
    if "join (" in sql_l or "join (select" in sql_l or "join\n(" in sql_l:
        return False, "SQL uses unapproved subquery derived table in JOIN"

    return True, ""


# ============================================================
# LEGACY EHR PROMPT & CONSISTENCY CHECKER (BACKWARD COMPATIBILITY)
# ============================================================

def _build_legacy_ehr_prompt(
    user_question: str,
    analysis_plan: str,
    database_schema: Optional[Dict[str, Any]],
) -> str:
    """Builds prompt for legacy EHR schema queries."""
    return f"""
You are an expert MySQL query generator for a clinical healthcare analytics platform.

Generate ONE valid, read-only MySQL SELECT query that strictly implements the approved analysis plan.

User question:
{user_question}

Approved analysis plan:
{analysis_plan}

Approved database schema:
{database_schema}

==================================================
RULES FOR SQL GENERATION:

1. Strict Plan Adherence (CRITICAL):
   - The APPROVED ANALYSIS PLAN is the authoritative human-reviewed specification and STRICTLY OVERRIDES any conflicting wording in the original user question.
   - Use ONLY the tables listed in "1. Relevant Tables and Columns" of the approved analysis plan.
   - If "2. Join Conditions" specifies "None", do NOT join any tables; query ONLY the single table specified.
   - Group by the EXACT column specified in "4. Aggregations & Grouping" of the analysis plan.
     * If the plan groups by encounters.ENCOUNTERCLASS, group by encounters.ENCOUNTERCLASS and select encounters.ENCOUNTERCLASS AS encounter_class. Do NOT join conditions!
     * If the plan groups by conditions.DESCRIPTION, group by conditions.DESCRIPTION and select conditions.DESCRIPTION AS diagnosis.
   - Do NOT use single-letter table aliases like e or c; use full table names (e.g., encounters.ENCOUNTERCLASS).

2. Encounter-Class Filter (CRITICAL):
   - If the approved plan specifies encounters.ENCOUNTERCLASS IN ('inpatient', 'emergency'), you MUST include exactly:
       WHERE encounters.ENCOUNTERCLASS IN ('inpatient', 'emergency')
     Do NOT omit this filter or replace it with a different filter.
   - If the plan says "inpatient encounters only", include: WHERE encounters.ENCOUNTERCLASS = 'inpatient'
   - If grouping by encounter class, do NOT restrict ENCOUNTERCLASS to a single value.

3. Length of Stay Rules:
   - When calculating length of stay, use:
     DATEDIFF(encounters.STOP, encounters.START)
   - Follow the filtering rules in the approved analysis plan strictly.
   - Include only clinically valid configured LOS values:
     DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30
   - Always exclude NULL START and STOP values:
     encounters.START IS NOT NULL AND encounters.STOP IS NOT NULL

4. Average Length of Stay:
   - If the analysis plan requests average length of stay, calculate:
     AVG(DATEDIFF(encounters.STOP, encounters.START))
     AS average_length_of_stay.

5. Column Aliasing & Ordering for Visualization:
   - Place the primary category / grouping dimension as the FIRST
     column in SELECT.
   - Place the aggregated metric as the SECOND column in SELECT.
   - Use clean, lower_snake_case aliases.

6. Schema & Syntax Safety:
   - Use ONLY tables and columns that exist in the approved schema.
   - Join tables using ONLY approved relationships.
   - Generate only ONE valid SELECT statement.
   - Do NOT use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
     TRUNCATE, REPLACE, GRANT, REVOKE, or multiple statements.
   - Do NOT invent tables, columns, or relationships.
   - Do NOT return markdown code fences.
   - Do NOT include explanations or commentary.
   - Return ONLY the raw MySQL query string.
"""


def _build_sql_from_plan(analysis_plan: str) -> Optional[str]:
    """
    Build a SQL query deterministically from the key requirements
    extracted from the approved analysis plan for legacy EHR encounters.
    """
    if not analysis_plan:
        return None

    plan_l = analysis_plan.lower()

    # Detect grouping dimension
    groups_by_encounterclass = any([
        "group by encounters.encounterclass" in plan_l,
        "group by `encounters.encounterclass`" in plan_l,
        "group results by encounters.encounterclass" in plan_l,
        "group results by `encounters.encounterclass`" in plan_l,
        "grouping**:\n  * group results by `encounters.encounterclass`" in plan_l,
        ("encounterclass" in plan_l and "group by" in plan_l
         and "conditions.description" not in plan_l.split("group by")[-1]),
    ])

    groups_by_diagnosis = any([
        "group by conditions.description" in plan_l,
        "group by `conditions.description`" in plan_l,
        "group results by conditions.description" in plan_l,
        "group results by `conditions.description`" in plan_l,
    ])

    # Detect required filters
    needs_inpatient_emergency = any([
        "in ('inpatient', 'emergency')" in plan_l,
        'in ("inpatient", "emergency")' in plan_l,
        "both inpatient and emergency" in plan_l,
        "inpatient and emergency encounters" in plan_l,
        "inpatient' and 'emergency'" in plan_l,
        "inpatient and emergency" in plan_l and "encounterclass" in plan_l,
    ])

    needs_inpatient_only = (
        "encounterclass = 'inpatient'" in plan_l
        and not needs_inpatient_emergency
    )

    needs_null_exclusion = any([
        "start is not null" in plan_l,
        "null start" in plan_l,
        "exclude null" in plan_l,
        "valid encounter dates" in plan_l,
    ])

    needs_los_30 = "between 0 and 30" in plan_l

    # Build encounter-class query
    if groups_by_encounterclass:
        where_parts = []
        if needs_inpatient_emergency:
            where_parts.append("encounters.ENCOUNTERCLASS IN ('inpatient', 'emergency')")
        if needs_null_exclusion:
            where_parts.append("encounters.START IS NOT NULL")
            where_parts.append("encounters.STOP IS NOT NULL")
        if needs_los_30:
            where_parts.append("DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30")

        where_clause = ""
        if where_parts:
            where_clause = "\nWHERE " + "\n  AND ".join(where_parts)

        return (
            "SELECT\n"
            "    encounters.ENCOUNTERCLASS AS encounter_class,\n"
            "    AVG(DATEDIFF(encounters.STOP, encounters.START)) AS average_length_of_stay\n"
            f"FROM encounters{where_clause}\n"
            "GROUP BY encounters.ENCOUNTERCLASS"
        )

    # Build diagnosis query
    if groups_by_diagnosis:
        where_parts = []
        if needs_inpatient_only:
            where_parts.append("encounters.ENCOUNTERCLASS = 'inpatient'")
        if needs_null_exclusion:
            where_parts.append("encounters.START IS NOT NULL")
            where_parts.append("encounters.STOP IS NOT NULL")
        if needs_los_30:
            where_parts.append("DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30")
        where_parts.append("conditions.DESCRIPTION IS NOT NULL")

        where_clause = "\nWHERE " + "\n  AND ".join(where_parts)

        return (
            "SELECT\n"
            "    conditions.DESCRIPTION AS diagnosis,\n"
            "    AVG(DATEDIFF(encounters.STOP, encounters.START)) AS average_length_of_stay\n"
            "FROM encounters\n"
            "JOIN conditions\n"
            f"    ON encounters.ID = conditions.ENCOUNTER{where_clause}\n"
            "GROUP BY conditions.DESCRIPTION"
        )

    return None


def _check_sql_vs_plan(sql: str, analysis_plan: str) -> Tuple[bool, str]:
    """Lightweight inline check for legacy EHR plan consistency."""
    if not analysis_plan:
        return True, ""

    plan_l = analysis_plan.lower()
    sql_l = sql.lower()

    if any([
        "group by encounters.encounterclass" in plan_l,
        "group by `encounters.encounterclass`" in plan_l,
        "group results by `encounters.encounterclass`" in plan_l,
        "group results by encounters.encounterclass" in plan_l,
    ]):
        if "encounterclass" not in sql_l or "group by" not in sql_l:
            return False, "SQL must GROUP BY encounters.ENCOUNTERCLASS"
        if (
            "group by conditions.description" in sql_l
            or "group by c.description" in sql_l
        ):
            return False, (
                "SQL groups by conditions.DESCRIPTION but plan requires "
                "GROUP BY encounters.ENCOUNTERCLASS"
            )

    if any([
        "none (single-table" in plan_l,
        "single-table query on" in plan_l,
        ("none required" in plan_l and "join conditions" in plan_l),
        ("conditions" not in plan_l and "join" not in plan_l
         and "encounterclass" in plan_l),
    ]):
        if " join " in sql_l or "\njoin " in sql_l:
            return False, "SQL has JOIN but plan specifies single-table query"

    needs_ie_filter = any([
        "in ('inpatient', 'emergency')" in plan_l,
        'in ("inpatient", "emergency")' in plan_l,
        "both inpatient and emergency" in plan_l,
        "inpatient and emergency encounters" in plan_l and "encounterclass" in plan_l,
    ])
    if needs_ie_filter:
        if (
            "encounterclass in ('inpatient'" not in sql_l
            and 'encounterclass in ("inpatient"' not in sql_l
            and "encounterclass in ('inpatient','emergency')" not in sql_l
        ):
            return False, (
                "SQL missing ENCOUNTERCLASS IN ('inpatient', 'emergency') "
                "filter required by approved plan"
            )

    if "start is not null" in plan_l and "start is not null" not in sql_l:
        return False, "SQL missing START IS NOT NULL filter"

    if "stop is not null" in plan_l and "stop is not null" not in sql_l:
        return False, "SQL missing STOP IS NOT NULL filter"

    if "between 0 and 30" in plan_l and "between 0 and 30" not in sql_l:
        return False, "SQL missing LOS BETWEEN 0 AND 30 filter"

    return True, ""


# ============================================================
# DETERMINISTIC SQL FALLBACK DISPATCHER
# ============================================================

def _deterministic_sql_fallback(
    user_question: str,
    analysis_plan: str,
    database_schema: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Fallback used specifically when the LLM is temporarily unavailable.
    Checks clinical schema question plan first, then falls back to _build_sql_from_plan.
    """
    # 1. Check clinical trial question plan
    clinical_plan = build_clinical_question_plan(user_question)
    if clinical_plan.is_supported and clinical_plan.suggested_sql:
        return clinical_plan.suggested_sql.strip()

    # 2. Check legacy EHR plan parser
    return _build_sql_from_plan(analysis_plan)


# ============================================================
# MAIN SQL GENERATOR
# ============================================================

def generate_sql(
    user_question: str,
    analysis_plan: str,
    database_schema: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Main SQL generation engine.
    Translates user clinical questions and approved analysis plans into valid MySQL SELECT queries.
    Uses ClinicalSchemaRegistry and ClinicalQuestionPlan for CDISC clinical-trial queries,
    with automatic deterministic fallback when the LLM is offline or quota-limited.
    """
    is_clinical = _is_clinical_context(database_schema)

    if is_clinical:
        # Build deterministic clinical question plan
        clinical_plan = build_clinical_question_plan(user_question)

        prompt = _build_clinical_prompt(
            user_question=user_question,
            analysis_plan=analysis_plan,
            database_schema=database_schema,
            plan=clinical_plan,
        )

        try:
            response = generate_response(prompt).strip()
        except RuntimeError as error:
            print(
                "LLM SQL generation unavailable. "
                "Checking deterministic clinical SQL fallback..."
            )
            fallback_sql = _deterministic_sql_fallback(
                user_question, analysis_plan, database_schema
            )
            if fallback_sql is not None:
                print("Using clinical plan-derived deterministic SQL fallback.")
                return fallback_sql
            raise error

        # Clean markdown code blocks if the model outputs them
        match = re.search(
            r"```(?:sql)?\s*([\s\S]*?)\s*```",
            response,
            re.IGNORECASE,
        )
        if match:
            response = match.group(1).strip()

        # Inline clinical plan-consistency check
        is_ok, reason = _check_sql_vs_clinical_plan(response, clinical_plan)
        if not is_ok:
            print(
                f"\nLLM-generated SQL fails clinical plan check: {reason}\n"
                "Attempting deterministic clinical SQL auto-correction..."
            )
            if clinical_plan.is_supported and clinical_plan.suggested_sql:
                print("Using deterministic verified clinical SQL.")
                return clinical_plan.suggested_sql.strip()

            print(
                "WARNING: Could not auto-correct clinical SQL. "
                "Returning original LLM SQL for explicit validation."
            )

        return response

    else:
        # Legacy EHR path
        prompt = _build_legacy_ehr_prompt(
            user_question, analysis_plan, database_schema
        )

        try:
            response = generate_response(prompt).strip()
        except RuntimeError as error:
            print(
                "LLM SQL generation unavailable. "
                "Checking legacy deterministic SQL fallback..."
            )
            fallback_sql = _build_sql_from_plan(analysis_plan)
            if fallback_sql is not None:
                print("Using plan-derived deterministic SQL fallback.")
                return fallback_sql
            raise error

        match = re.search(
            r"```(?:sql)?\s*([\s\S]*?)\s*```",
            response,
            re.IGNORECASE,
        )
        if match:
            response = match.group(1).strip()

        is_ok, reason = _check_sql_vs_plan(response, analysis_plan)
        if not is_ok:
            print(
                f"\nLLM-generated SQL fails plan-consistency check: {reason}\n"
                "Attempting deterministic plan-based SQL correction..."
            )
            plan_sql = _build_sql_from_plan(analysis_plan)
            if plan_sql is not None:
                print("Using deterministic plan-based SQL.")
                return plan_sql

            print(
                "WARNING: Could not auto-correct SQL. "
                "Returning original LLM SQL for explicit validation."
            )

        return response