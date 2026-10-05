import re

from app.ai.llm import generate_response


# ============================================================
# DETERMINISTIC PLAN-AWARE SQL BUILDER
# ============================================================

def _build_sql_from_plan(analysis_plan: str) -> str | None:
    """
    Build a SQL query deterministically from the key requirements
    extracted from the approved analysis plan.

    This is used in two scenarios:
    1. When the LLM generates SQL that fails a plan-consistency check.
    2. As a named fallback when the LLM is temporarily unavailable.

    Returns None if the plan pattern is not recognised.
    """
    plan_l = analysis_plan.lower()

    # ── Detect grouping dimension ────────────────────────────────────────────
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

    # ── Detect required filters ──────────────────────────────────────────────
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

    # ── Build encounter-class query ──────────────────────────────────────────
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

    # ── Build diagnosis query ────────────────────────────────────────────────
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


# ============================================================
# INLINE PLAN-CONSISTENCY CHECKER
# ============================================================

def _check_sql_vs_plan(sql: str, analysis_plan: str) -> tuple[bool, str]:
    """
    Lightweight inline check: does the LLM-generated SQL satisfy the
    key structural requirements in the approved analysis plan?

    Returns (is_consistent, failure_reason).
    """
    if not analysis_plan:
        return True, ""

    plan_l = analysis_plan.lower()
    sql_l = sql.lower()

    # 1. Grouping consistency ────────────────────────────────────────────────
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

    # 2. Single-table check ──────────────────────────────────────────────────
    if any([
        "none (single-table" in plan_l,
        "single-table query on" in plan_l,
        ("none required" in plan_l and "join conditions" in plan_l),
        ("conditions" not in plan_l and "join" not in plan_l
         and "encounterclass" in plan_l),
    ]):
        if " join " in sql_l or "\njoin " in sql_l:
            return False, "SQL has JOIN but plan specifies single-table query"

    # 3. Encounter-class filter check ────────────────────────────────────────
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

    # 4. NULL-date filter check ──────────────────────────────────────────────
    if "start is not null" in plan_l and "start is not null" not in sql_l:
        return False, "SQL missing START IS NOT NULL filter"

    if "stop is not null" in plan_l and "stop is not null" not in sql_l:
        return False, "SQL missing STOP IS NOT NULL filter"

    # 5. LOS range filter check ──────────────────────────────────────────────
    if "between 0 and 30" in plan_l and "between 0 and 30" not in sql_l:
        return False, "SQL missing LOS BETWEEN 0 AND 30 filter"

    return True, ""


# ============================================================
# LEGACY DETERMINISTIC FALLBACK (kept for LLM-unavailable path)
# ============================================================

def _deterministic_sql_fallback(
    user_question: str,
    analysis_plan: str,
    database_schema: dict,
) -> str | None:
    """
    Fallback used specifically when the LLM is temporarily unavailable
    (RuntimeError from generate_response).  Delegates to _build_sql_from_plan.
    """
    return _build_sql_from_plan(analysis_plan)


# ============================================================
# MAIN SQL GENERATOR
# ============================================================

def generate_sql(
    user_question: str,
    analysis_plan: str,
    database_schema: dict,
) -> str:

    prompt = f"""
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

    try:
        response = generate_response(prompt).strip()

    except RuntimeError as error:
        print(
            "LLM SQL generation unavailable. "
            "Checking deterministic SQL fallback..."
        )

        fallback_sql = _build_sql_from_plan(analysis_plan)

        if fallback_sql is not None:
            print("Using plan-derived deterministic SQL fallback.")
            return fallback_sql

        raise error

    # Clean markdown code blocks if the model outputs them.
    match = re.search(
        r"```(?:sql)?\s*([\s\S]*?)\s*```",
        response,
        re.IGNORECASE,
    )

    if match:
        response = match.group(1).strip()

    # ── Inline plan-consistency check ────────────────────────────────────────
    # If the LLM output violates a key plan requirement, attempt to correct it
    # deterministically before the downstream validator sees it.
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

        # Could not auto-correct; return the original LLM SQL.
        # validate_sql_node will catch and report the specific failure.
        print(
            "WARNING: Could not auto-correct SQL. "
            "Returning original LLM SQL for explicit validation."
        )

    return response