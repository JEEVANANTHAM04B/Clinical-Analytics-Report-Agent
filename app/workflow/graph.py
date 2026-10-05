import re
from app.workflow import state
from langgraph.graph import StateGraph, START, END

from app.ai.llm import generate_response
from app.ai.insight_generator import generate_insight
from app.ai.insight_validator import validate_insight
from app.ai.insight_regenerator import regenerate_insight

from app.analytics.sql_generator import generate_sql
from app.analytics.sql_validator import validate_sql
from app.analytics.query_executor import execute_query
from app.analytics.result_validator import validate_results
from app.analytics.insight_evidence import build_insight_evidence
from app.database.schema_service import get_database_schema
from app.rag.insight_context import get_insight_context
from app.workflow.state import ClinicalAnalyticsState

from app.visualization.chart_generator import (
    create_chart_spec,
)
from app.audit.service import record_audit_event


# ============================================================
# 1. LOAD DATABASE SCHEMA
# ============================================================

def load_schema(state: ClinicalAnalyticsState):
    schema = get_database_schema()
    selected_tables = state.get("selected_tables")
    if selected_tables:
        selected_set = {t.strip().lower() for t in selected_tables}
        schema = {
            "tables": {k: v for k, v in schema.get("tables", {}).items() if k.lower() in selected_set},
            "relationships": [
                r for r in schema.get("relationships", [])
                if r["parent_table"].lower() in selected_set and r["child_table"].lower() in selected_set
            ],
        }

    return {
        "database_schema": schema,
        "human_feedback": state.get("human_feedback", ""),
        "feedback_history": state.get("feedback_history", []),
        "plan_version": state.get("plan_version", 1),
        "insight_retry_count": 0,
        "error": "",
    }

# ============================================================
# 2. DETERMINISTIC ANALYSIS PLAN FALLBACK
# ============================================================

def _deterministic_analysis_plan(
    question: str,
    database_schema: dict,
) -> str | None:
    """
    Generate a deterministic analysis plan for a supported
    clinical analytics pattern when the LLM is unavailable.

    This fallback is intentionally limited to a known,
    schema-supported analytics pattern.
    """

    normalized_question = question.lower()

    if (
        "average length of stay" in normalized_question
        and ("encounter class" in normalized_question or "encounterclass" in normalized_question)
    ):
        return """
### Clinical Analytics Analysis Plan

#### 1. Relevant Tables and Columns
* **`encounters`**:
  * `ID` (VARCHAR): Unique identifier for the encounter.
  * `START` (DATE): Start date/time of the medical encounter.
  * `STOP` (DATE): End date/time of the medical encounter.
  * `ENCOUNTERCLASS` (VARCHAR): Class of encounter (e.g., inpatient, ambulatory, emergency, outpatient, wellness).

#### 2. Join Conditions
* None (single-table query on `encounters`).

#### 3. Derived Calculations
* **Length of Stay**:
  Calculate using:
  `DATEDIFF(encounters.STOP, encounters.START)`

* **Average Length of Stay**:
  Calculate using:
  `AVG(DATEDIFF(encounters.STOP, encounters.START))`

#### 4. Aggregations & Grouping
* **Grouping**:
  Group results by `encounters.ENCOUNTERCLASS`.

* **Aggregation**:
  Calculate the average length of stay for each encounter class:
  `AVG(DATEDIFF(encounters.STOP, encounters.START))`

#### 5. Filtering
* **Valid Encounter Dates**:
  * Exclude NULL START and STOP values:
    * `encounters.START IS NOT NULL`
    * `encounters.STOP IS NOT NULL`

* **Length of Stay Range**:
  * Include only LOS values between 0 and 30 days:
    * `DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30`
""".strip()

    if (
        "average length of stay" in normalized_question
        and "diagnosis" in normalized_question
    ):
        return """
### Clinical Analytics Analysis Plan

#### 1. Relevant Tables and Columns
* **`encounters`**:
  * `ID` (VARCHAR): Unique identifier for the encounter.
  * `START` (DATE): Start date/time of the medical encounter.
  * `STOP` (DATE): End date/time of the medical encounter.
  * `ENCOUNTERCLASS` (VARCHAR): Class of encounter (e.g., inpatient).

* **`conditions`**:
  * `DESCRIPTION` (VARCHAR): Human-readable diagnosis description.
  * `ENCOUNTER` (VARCHAR): Foreign key referencing the encounter.

#### 2. Join Conditions
* Join `encounters` and `conditions` using the approved relationship:
  * `encounters.ID = conditions.ENCOUNTER`

#### 3. Derived Calculations
* **Length of Stay**:
  Calculate using:
  `DATEDIFF(encounters.STOP, encounters.START)`

* **Average Length of Stay**:
  Calculate using:
  `AVG(DATEDIFF(encounters.STOP, encounters.START))`

#### 4. Aggregations & Grouping
* **Grouping**:
  Group results by `conditions.DESCRIPTION`.

* **Aggregation**:
  Calculate the average length of stay for each diagnosis.

#### 5. Filtering
* **Inpatient Encounters Only**:
  * Use inpatient encounters only: `encounters.ENCOUNTERCLASS = 'inpatient'`

* **Valid Encounter Dates**:
  * Exclude NULL START and STOP values:
    * `encounters.START IS NOT NULL`
    * `encounters.STOP IS NOT NULL`

* **Length of Stay Range**:
  * Include only LOS values between 0 and 30 days:
    * `DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30`

* **Valid Diagnosis**:
  * Exclude records where diagnosis description is missing:
    * `conditions.DESCRIPTION IS NOT NULL`
""".strip()

    return None


# ============================================================
# 3. ANALYZE USER QUESTION
# ============================================================

def analyze_question(state: ClinicalAnalyticsState):
    question = state["user_question"]
    database_schema = state["database_schema"]
    existing_plan = state.get("analysis_plan")
    approval_status = state.get("approval_status")

    # If an analysis plan is already provided (e.g. approving a plan or rejecting to regenerate),
    # preserve it rather than overwriting it with an uncorrected initial plan!
    if existing_plan and approval_status in ("approved", "rejected"):
        return {
            "analysis_plan": existing_plan,
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
            "error": "",
        }

    prompt = f"""
You are a clinical analytics planning assistant.

Analyze the user's natural-language analytics question and generate a structured, precise analysis plan using ONLY the approved database schema provided below.

User question:
{question}

Approved database schema:
{database_schema}

==================================================
SEMANTIC MAPPING & CLINICAL DOMAIN RULES:

Map natural-language concepts to the actual approved database schema.

1. Diagnosis & Clinical Conditions:
   - "diagnosis", "diagnosis name", or "diagnosis description"
     refers to human-readable clinical text:
     use conditions.DESCRIPTION as the diagnosis.
   - "diagnosis code" specifically refers to standard medical codes:
     use conditions.CODE.
   - "code" refers to the appropriate code column based on context.
   - When grouping or presenting by diagnosis, always use
     conditions.DESCRIPTION unless standard codes were explicitly requested.

2. Encounters, Dates & Length of Stay (LOS) Rules:
   - "length of stay" (LOS) is NOT an existing raw column.
   - It is a DERIVED field computed from:
     DATEDIFF(encounters.STOP, encounters.START).
   - "average length of stay" is calculated as:
     AVG(DATEDIFF(encounters.STOP, encounters.START)).
   - Do NOT invent or assume a column named "length_of_stay".
   - For ANY question involving length of stay (LOS):
     * Relevant Tables and Columns:
       - Must include encounters.START, encounters.STOP, and encounters.ENCOUNTERCLASS.
     * Derived Calculations:
       - Length of stay = DATEDIFF(encounters.STOP, encounters.START)
       - Average length of stay = AVG(DATEDIFF(encounters.STOP, encounters.START)) (when average is requested).
     * Filtering Requirements (MUST be explicitly stated in the plan):
       - Use inpatient encounters only: encounters.ENCOUNTERCLASS = 'inpatient'
       - Exclude NULL START and STOP values: encounters.START IS NOT NULL AND encounters.STOP IS NOT NULL
       - Include only LOS values between 0 and 30 days: DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30
   - "count of patients" refers to COUNT(DISTINCT patient identifier).
   - "count of encounters" refers to COUNT(encounters.ID)
     or COUNT(DISTINCT encounters.ID).

3. Approved Relationships & Joins:
   - Join tables using ONLY approved relationships:
     * encounters.ID = conditions.ENCOUNTER
     * patients.ID = encounters.PATIENT

==================================================
ANALYSIS PLAN REQUIREMENTS:

The analysis plan must explicitly state:

1. Relevant Tables and Columns:
   - Exact tables and columns from the approved schema.
   - For length-of-stay questions, include encounters.START, encounters.STOP, and encounters.ENCOUNTERCLASS.
2. Join Conditions:
   - Approved relationships only (e.g., encounters.ID = conditions.ENCOUNTER).
3. Derived Calculations:
   - For length of stay, explicitly state:
     * Length of stay = DATEDIFF(encounters.STOP, encounters.START)
     * Average length of stay = AVG(DATEDIFF(encounters.STOP, encounters.START)) (if average is requested).
4. Aggregations & Grouping:
   - Exact grouping column (e.g., group by conditions.DESCRIPTION for diagnosis).
5. Filtering:
   - For length-of-stay questions, MUST explicitly include:
     * Use inpatient encounters only: encounters.ENCOUNTERCLASS = 'inpatient'.
     * Exclude NULL START and STOP values.
     * Include only LOS values between 0 and 30 days.

STRICT RULES:

- Map natural-language terms ONLY to actual schema columns.
- NEVER invent tables, columns, relationships, metrics, or functions.
- Do NOT calculate or invent numerical results.
- Do NOT generate SQL.

MOST IMPORTANT RULE:
- Answer ONLY what the user explicitly asked for.
- Do NOT add additional metrics or analyses that were not requested.
- Do NOT add median, IQR, minimum, maximum, count, percentage,
  ranking, trend analysis, statistical tests, or other metrics
  unless the user explicitly asks for them.
- Do NOT add optional visualizations unless the user explicitly
  asks for a chart or visualization.
- Do NOT expand the analysis scope beyond the user's question.
- Every calculation in the plan must directly correspond to
  something requested by the user.

For example:
If the user asks:
"What is the average length of stay by diagnosis?"

The plan MUST explicitly specify:
1. Relevant Tables and Columns:
   - conditions.DESCRIPTION
   - conditions.ENCOUNTER
   - encounters.ID
   - encounters.START
   - encounters.STOP
   - encounters.ENCOUNTERCLASS
2. Join Conditions:
   - encounters.ID = conditions.ENCOUNTER
3. Derived Calculations:
   - Length of stay = DATEDIFF(encounters.STOP, encounters.START)
   - Average length of stay = AVG(DATEDIFF(encounters.STOP, encounters.START))
4. Aggregations & Grouping:
   - Group by conditions.DESCRIPTION
5. Filtering:
   - Use inpatient encounters only (encounters.ENCOUNTERCLASS = 'inpatient').
   - Exclude NULL START and STOP values.
   - Include only LOS values between 0 and 30 days.

It MUST NOT introduce:
- median
- IQR
- encounter count
- ranking
- minimum/maximum
- additional statistics
- optional charts

Return ONLY the concise, structured analysis plan.
"""

    try:
        response = generate_response(prompt)
        record_audit_event(
            action="ANALYSIS_PLAN_GENERATED",
            details=f"Generated clinical analysis plan (v{state.get('plan_version', 1)}) for query: '{question[:60]}...'",
            user_agent="AI Planner",
            entity_type="PLAN",
            entity_name=f"plan_v{state.get('plan_version', 1)}",
        )

        return {
            "analysis_plan": response,
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
            "error": "",
        }
    except RuntimeError as error:
        print(
            "LLM analysis planning unavailable. "
            "Checking deterministic analysis-plan fallback..."
        )

        fallback_plan = _deterministic_analysis_plan(
            question=question,
            database_schema=database_schema,
        )

        if fallback_plan is not None:
            print("Using deterministic analysis-plan fallback.")
            record_audit_event(
                action="ANALYSIS_PLAN_GENERATED",
                details=f"Generated deterministic fallback analysis plan (v{state.get('plan_version', 1)}) for query: '{question[:60]}...'",
                user_agent="AI Planner (Deterministic)",
                entity_type="PLAN",
                entity_name=f"plan_v{state.get('plan_version', 1)}",
            )

            return {
                "analysis_plan": fallback_plan,
                "human_feedback": state.get("human_feedback", ""),
                "feedback_history": state.get("feedback_history", []),
                "plan_version": state.get("plan_version", 1),
                "error": "",
            }

        raise error


# ============================================================
# 4. HUMAN APPROVAL
# ============================================================

def human_approval_node(state: ClinicalAnalyticsState):
    """
    Human reviews the analysis plan.

    YES (approved):
        Continue to SQL generation.

    NO (rejected):
        Collect human feedback and regenerate the plan.

    PENDING:
        Stop and await human review.
    """
    approval_status = state.get("approval_status")
    approval_source = state.get("approval_source", "api")
    human_feedback = (state.get("human_feedback") or "").strip()
    feedback_history = state.get("feedback_history", [])
    plan_version = state.get("plan_version", 1)

    if approval_status == "approved":
        print("\nAnalysis plan approved.")
        record_audit_event(
            action="ANALYSIS_PLAN_APPROVED",
            details=f"Analysis plan (v{plan_version}) approved by analyst via {approval_source.upper()}",
            user_agent=f"Analyst ({approval_source.upper()})",
            status="APPROVED",
            entity_type="PLAN",
            entity_name=f"plan_v{plan_version}",
        )
        return {
            "approval_status": "approved",
            "approval_source": approval_source,
            "human_feedback": "",
            "feedback_history": feedback_history,
            "plan_version": plan_version,
            "error": "",
        }

    if approval_status == "rejected":
        print("\nAnalysis plan rejected.")
        if human_feedback:
            print("Human feedback:", human_feedback)
        else:
            print("No specific feedback provided; regenerating plan.")

        fb_snip = f": '{human_feedback[:60]}'" if human_feedback else ""
        record_audit_event(
            action="ANALYSIS_PLAN_REJECTED",
            details=f"Analysis plan (v{plan_version}) rejected by analyst via {approval_source.upper()}{fb_snip}",
            user_agent=f"Analyst ({approval_source.upper()})",
            status="REJECTED",
            entity_type="PLAN",
            entity_name=f"plan_v{plan_version}",
        )

        return {
            "approval_status": "rejected",
            "approval_source": approval_source,
            "human_feedback": human_feedback,
            "feedback_history": feedback_history,
            "plan_version": plan_version,
            "error": "",
        }

    if approval_status == "pending" or approval_source == "api":
        print("\nAnalysis plan waiting for human approval.")
        return {
            "approval_status": "pending",
            "approval_source": approval_source,
            "human_feedback": "",
            "feedback_history": feedback_history,
            "plan_version": plan_version,
            "error": "",
        }

    print("\n" + "=" * 70)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 70)

    print("\nAnalysis Plan:")
    print(state.get("analysis_plan", ""))

    print("\n" + "-" * 70)

    while True:
        approval = input(
            "\nApprove this analysis plan? (yes/no): "
        ).strip().lower()

        if approval in {"yes", "y"}:
            print("\nAnalysis plan approved.")
            return {
                "approval_status": "approved",
                "approval_source": "cli",
                "human_feedback": "",
                "feedback_history": feedback_history,
                "plan_version": plan_version,
                "error": "",
            }

        if approval in {"no", "n"}:
            print("\nAnalysis plan needs correction.")
            feedback = input(
                "\nWhat should be corrected? (Optional, press Enter to skip)\n> "
            ).strip()

            print("\nHuman feedback received:", feedback)

            return {
                "approval_status": "rejected",
                "approval_source": "cli",
                "human_feedback": feedback,
                "feedback_history": feedback_history,
                "plan_version": plan_version,
                "error": "",
            }

        print("Please enter 'yes' or 'no'.")


# ============================================================
# 5. REGENERATE ANALYSIS PLAN
# ============================================================

def _is_explicitly_removed(target_type: str, all_feedback: str) -> bool:
    """
    Check if the user explicitly requested the removal of a specific requirement.
    Only explicit removal commands (e.g. 'remove the 30-day restriction')
    authorize removing an established requirement.
    """
    all_fb = all_feedback.lower()
    if target_type == "los_30":
        return any(
            phrase in all_fb
            for phrase in [
                "remove the 30-day", "remove 30-day", "remove the 30 day", "remove 30 day",
                "remove the 30", "remove 30", "drop 30", "delete 30", "without 30", "no 30",
                "remove the los restriction", "remove los restriction", "remove los 30",
                "remove the 0-30", "remove 0-30", "remove the 0 to 30", "remove 0 to 30",
                "remove 30-day los restriction", "remove the 30-day los restriction",
                "remove 30 day los restriction", "remove the 30 day los restriction",
                "do not restrict to 30", "don't restrict to 30", "no los limit",
                "remove los limit", "unlimited los", "drop los restriction",
            ]
        )
    if target_type == "inpatient":
        return any(
            phrase in all_fb
            for phrase in [
                "remove inpatient", "drop inpatient", "without inpatient",
                "all encounter classes", "all encounters", "not just inpatient",
                "do not filter by inpatient", "don't filter by inpatient",
                "include outpatient", "include all encounters",
                "do not restrict encounters.encounterclass to 'inpatient'",
                "do not restrict to inpatient",
            ]
        )
    if target_type == "null_dates":
        return any(
            phrase in all_fb
            for phrase in [
                "allow null", "include null", "do not exclude null",
                "don't exclude null", "remove null date filter", "remove null filter",
                "allow missing date", "include missing date",
            ]
        )
    if target_type == "diagnosis_grouping":
        return any(
            phrase in all_fb
            for phrase in [
                "remove diagnosis grouping", "do not group by diagnosis",
                "don't group by diagnosis", "remove grouping", "ungrouped",
                "overall average without diagnosis", "instead of grouping by diagnosis",
            ]
        )
    return False


def _remove_inpatient_filter(plan: str) -> str:
    """
    Remove any inpatient filter from the plan when it conflicts with the analysis.
    """
    lines = plan.splitlines()
    filtered_lines = []
    skip_block = False
    for line in lines:
        lower = line.lower()
        if any(k in lower for k in [
            "inpatient encounters only",
            "use inpatient encounters only",
            "encounters.encounterclass = 'inpatient'",
            "encounters.encounterclass='inpatient'",
            "encounterclass = 'inpatient'",
            "encounterclass='inpatient'",
        ]):
            skip_block = True
            continue
        if skip_block:
            if (line.startswith("  ") or line.startswith("\t") or line.strip().startswith("* `") or line.strip().startswith("- `")) and any(k in lower for k in ["inpatient", "encounterclass"]):
                continue
            elif line.strip() == "":
                continue
            else:
                skip_block = False
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _remove_conditions_table_and_join(plan: str) -> str:
    """
    Remove the conditions table and encounters-conditions join when
    diagnosis is no longer part of the analysis.
    """
    lines = plan.splitlines()
    new_lines = []
    skip_table_block = False
    in_join_section = False

    for line in lines:
        lower = line.lower()

        # Check if entering join conditions section
        if re.search(r'(?i)#{1,4}\s*(?:2[\.\s]*)?Join\s*Conditions', line) or line.strip().lower().startswith("2. join"):
            in_join_section = True
            skip_table_block = False
            new_lines.append(line)
            new_lines.append("* None (single-table query on `encounters`).")
            continue
        elif re.search(r'(?i)#{1,4}\s*(?:3[\.\s]*)?Derived\s*Calculations', line) or line.strip().lower().startswith("3. derived"):
            in_join_section = False

        if in_join_section:
            if any(k in lower for k in ["conditions", "encounter", "="]):
                continue
            elif line.strip() == "":
                continue
            else:
                in_join_section = False

        # In Relevant Tables section:
        if "conditions" in lower and any(h in lower for h in ["**`conditions`**", "**conditions**", "* conditions", "- conditions", "* **`conditions`"]):
            skip_table_block = True
            continue
        if skip_table_block:
            if (line.startswith("  ") or line.startswith("\t") or line.strip().startswith("*") or line.strip().startswith("-")) and any(k in lower for k in ["description", "encounter", "diagnosis"]):
                continue
            elif line.strip() == "":
                continue
            else:
                skip_table_block = False

        if "conditions.description" in lower and "encounters" not in lower:
            continue

        new_lines.append(line)

    return "\n".join(new_lines)


def _remove_filter_from_plan(plan: str, target_type: str) -> str:
    """
    Remove a filter block or line from the plan if explicitly requested.
    """
    if target_type == "los_30":
        lines = plan.splitlines()
        filtered_lines = []
        skip_block = False
        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["between 0 and 30", "0 and 30 days", "0 to 30 days", "length of stay range", "0–30 days"]):
                skip_block = True
                continue
            if skip_block:
                if (line.startswith("  ") or line.startswith("\t") or line.strip().startswith("* `datediff") or line.strip().startswith("- `datediff")) and any(k in lower for k in ["datediff", "los", "30", "between"]):
                    continue
                elif line.strip() == "":
                    continue
                else:
                    skip_block = False
            filtered_lines.append(line)
        return "\n".join(filtered_lines)
    return plan


def _inject_filter_into_plan(plan: str, filter_block: str) -> str:
    """
    Insert a filter block cleanly under the 'Filtering' section.
    """
    match = re.search(r'(?i)(?:^|\n)(#{1,4}\s*(?:5[\.\s]*)?Filtering[^\n]*|(?:\d+\.\s*)?Filtering:?)', plan)
    if not match:
        return plan.rstrip() + "\n\n#### 5. Filtering\n" + filter_block + "\n"

    start_pos = match.end()
    next_section = re.search(r'\n(#{1,4}\s+[^\n]+|\d+\.\s+[A-Z][^\n]+)', plan[start_pos:])
    if next_section:
        insert_idx = start_pos + next_section.start()
        return plan[:insert_idx].rstrip() + "\n\n" + filter_block + "\n\n" + plan[insert_idx:].lstrip()
    else:
        return plan.rstrip() + "\n\n" + filter_block + "\n"


def _enforce_logical_consistency(
    plan: str,
    question: str,
    human_feedback: str,
    feedback_history: list[str],
) -> str:
    """
    Perform a comprehensive logical consistency check on the regenerated analysis plan:
    1. Does grouping match user feedback?
    2. Do any filters conflict with the grouping? (e.g. grouping by encounter class conflicts with inpatient filter)
    3. Are all tables and joins necessary?
    4. Are required data-quality rules (LOS 0-30, valid dates) preserved?
    """
    all_fb = " ".join(feedback_history + ([human_feedback] if human_feedback else [])).lower()

    is_grouping_by_encounter_class = (
        "encounter class" in all_fb
        or "encounterclass" in all_fb
        or "by encounter class" in all_fb
        or "by encounter_class" in all_fb
    )

    if is_grouping_by_encounter_class:
        # A. Grouping must be by encounters.ENCOUNTERCLASS
        plan = re.sub(
            r'(?i)(group\s+(?:results\s+)?by\s+)`?conditions\.DESCRIPTION`?',
            r'\1`encounters.ENCOUNTERCLASS`',
            plan
        )
        plan = re.sub(
            r'(?i)(group\s+(?:results\s+)?by\s+)diagnosis',
            r'\1encounter class (`encounters.ENCOUNTERCLASS`)',
            plan
        )
        plan = re.sub(
            r'(?i)average length of stay for each diagnosis',
            r'average length of stay for each encounter class',
            plan
        )

        # B. Conflict Resolution: Remove inpatient encounters filter!
        # Grouping by encounter class requires multiple encounter classes to remain in the dataset.
        plan = _remove_inpatient_filter(plan)

        # C. Remove unnecessary tables and joins:
        # If diagnosis is not being filtered or grouped, conditions is unnecessary!
        if "instead of grouping by diagnosis" in all_fb or "by encounter class" in all_fb:
            plan = _remove_conditions_table_and_join(plan)

    # D. Preserve Length of Stay Data Quality Rules (0-30 days and valid dates)
    if not _is_explicitly_removed("los_30", all_fb):
        if not any(k in plan.lower() for k in ["between 0 and 30", "0 and 30 days", "0 to 30 days", "0–30 days", "los values between"]):
            los_block = (
                "* **Length of Stay Range**:\n"
                "  * Include only LOS values between 0 and 30 days:\n"
                "    * `DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30`"
            )
            plan = _inject_filter_into_plan(plan, los_block)

    if not _is_explicitly_removed("null_dates", all_fb):
        if not any(k in plan.lower() for k in ["start is not null", "null start", "valid encounter dates", "missing admission or discharge"]):
            null_block = (
                "* **Valid Encounter Dates**:\n"
                "  * Exclude NULL START and STOP values:\n"
                "    * `encounters.START IS NOT NULL`\n"
                "    * `encounters.STOP IS NOT NULL`"
            )
            plan = _inject_filter_into_plan(plan, null_block)

    return plan.strip()


def _preserve_plan_requirements(
    current_plan: str,
    revised_plan: str,
    human_feedback: str,
    feedback_history: list[str],
    question: str,
) -> str:
    """
    Ensure that regenerating an analysis plan preserves all valid requirements
    from the current/previous plan UNLESS the human feedback explicitly or
    logically overrides them.

    Human feedback overrides conflicting parts of the previous plan.
    Do not blindly preserve filters that conflict with the revised grouping.
    """
    all_feedback_texts = list(feedback_history) + ([human_feedback] if human_feedback else [])
    combined_feedback = " ".join(all_feedback_texts).lower()
    current_lower = current_plan.lower()
    revised_lower = revised_plan.lower()
    question_lower = question.lower()

    # Check if grouping dimension changed to encounter class
    is_grouping_by_encounter_class = (
        "encounter class" in combined_feedback
        or "encounterclass" in combined_feedback
        or "by encounter class" in combined_feedback
        or "by encounter_class" in combined_feedback
    )

    # 1. Length of Stay Range (0 to 30 days)
    los_explicitly_removed = _is_explicitly_removed("los_30", combined_feedback)
    if los_explicitly_removed:
        revised_plan = _remove_filter_from_plan(revised_plan, "los_30")
        revised_lower = revised_plan.lower()
    else:
        los_in_current = any(
            k in current_lower
            for k in [
                "between 0 and 30", "0 and 30 days", "0 to 30 days", "0–30 days",
                "los values between", "between 0 and 30", "0 and 30"
            ]
        ) or ("length of stay" in question_lower and "30" in current_lower)

        los_in_revised = any(
            k in revised_lower
            for k in [
                "between 0 and 30", "0 and 30 days", "0 to 30 days", "0–30 days",
                "los values between"
            ]
        )

        if los_in_current and not los_in_revised:
            los_block = (
                "* **Length of Stay Range**:\n"
                "  * Include only LOS values between 0 and 30 days:\n"
                "    * `DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30`"
            )
            revised_plan = _inject_filter_into_plan(revised_plan, los_block)
            revised_lower = revised_plan.lower()

    # 2. Inpatient Encounters Only
    # CONFLICT RESOLUTION: If grouping by encounter class, filtering by inpatient is contradictory!
    inpatient_conflicted = is_grouping_by_encounter_class
    inpatient_explicitly_removed = _is_explicitly_removed("inpatient", combined_feedback) or inpatient_conflicted

    if inpatient_explicitly_removed:
        revised_plan = _remove_inpatient_filter(revised_plan)
        revised_lower = revised_plan.lower()
    else:
        inpatient_in_current = "inpatient" in current_lower or "inpatient" in combined_feedback
        inpatient_in_revised = "inpatient" in revised_lower

        if inpatient_in_current and not inpatient_in_revised:
            inpatient_block = (
                "* **Inpatient Encounters Only**:\n"
                "  * Use inpatient encounters only: `encounters.ENCOUNTERCLASS = 'inpatient'`"
            )
            revised_plan = _inject_filter_into_plan(revised_plan, inpatient_block)
            revised_lower = revised_plan.lower()

    # 3. Valid Encounter Dates (NULL START/STOP exclusion)
    null_dates_explicitly_removed = _is_explicitly_removed("null_dates", combined_feedback)
    if not null_dates_explicitly_removed:
        null_in_current = (
            "start is not null" in current_lower
            or "null start" in current_lower
            or "valid encounter dates" in current_lower
            or "missing" in combined_feedback
            or "null" in combined_feedback
            or "admission or discharge" in combined_feedback
        )
        null_in_revised = (
            "start is not null" in revised_lower
            or "null start" in revised_lower
            or "stop is not null" in revised_lower
            or "missing admission or discharge" in revised_lower
        )

        if null_in_current and not null_in_revised:
            null_block = (
                "* **Valid Encounter Dates**:\n"
                "  * Exclude NULL START and STOP values:\n"
                "    * `encounters.START IS NOT NULL`\n"
                "    * `encounters.STOP IS NOT NULL`"
            )
            revised_plan = _inject_filter_into_plan(revised_plan, null_block)
            revised_lower = revised_plan.lower()

    # 4. Valid Diagnosis Description Exclusion (only if diagnosis is used!)
    is_diagnosis_replaced = (
        "instead of grouping by diagnosis" in combined_feedback
        or ("group" in combined_feedback and is_grouping_by_encounter_class)
    )
    if not is_diagnosis_replaced:
        diag_null_in_current = "conditions.description is not null" in current_lower or "diagnosis description is missing" in current_lower
        if diag_null_in_current and "conditions.description is not null" not in revised_lower:
            diag_null_block = (
                "* **Valid Diagnosis**:\n"
                "  * Exclude records where diagnosis description is missing:\n"
                "    * `conditions.DESCRIPTION IS NOT NULL`"
            )
            revised_plan = _inject_filter_into_plan(revised_plan, diag_null_block)
            revised_lower = revised_plan.lower()

    # 5. Diagnosis Grouping
    diag_explicitly_removed = _is_explicitly_removed("diagnosis_grouping", combined_feedback) or is_diagnosis_replaced

    if not diag_explicitly_removed:
        diag_in_current = (
            "conditions.description" in current_lower
            or "group by diagnosis" in current_lower
            or "diagnosis" in question_lower
            or "diagnosis" in combined_feedback
        )
        diag_in_revised = (
            "conditions.description" in revised_lower
            or ("group" in revised_lower and "diagnosis" in revised_lower)
        )

        if diag_in_current and not diag_in_revised:
            group_match = re.search(r'(?i)(?:^|\n)(#{1,4}\s*(?:4[\.\s]*)?Aggregations[^\n]*|(?:\d+\.\s*)?Aggregations:?)', revised_plan)
            if group_match:
                g_start = group_match.end()
                diag_group_block = "\n* **Grouping**:\n  * Group results by `conditions.DESCRIPTION`."
                revised_plan = revised_plan[:g_start] + diag_group_block + revised_plan[g_start:]
            else:
                revised_plan += "\n\n#### 4. Aggregations & Grouping\n* Group results by `conditions.DESCRIPTION`."
            revised_lower = revised_plan.lower()

    # 6. Join Condition (Only keep conditions if required!)
    if not is_diagnosis_replaced:
        if ("conditions" in revised_lower or "diagnosis" in revised_lower) and "encounters" in revised_lower:
            if "encounters.id = conditions.encounter" not in revised_lower and "conditions.encounter = encounters.id" not in revised_lower:
                join_match = re.search(r'(?i)(?:^|\n)(#{1,4}\s*(?:2[\.\s]*)?Join\s*Conditions[^\n]*|(?:\d+\.\s*)?Join\s*Conditions:?)', revised_plan)
                join_line = "\n* `encounters.ID = conditions.ENCOUNTER`"
                if join_match:
                    j_start = join_match.end()
                    revised_plan = revised_plan[:j_start] + join_line + revised_plan[j_start:]
                else:
                    revised_plan += "\n\n#### 2. Join Conditions\n* `encounters.ID = conditions.ENCOUNTER`"

    # Enforce overall logical consistency
    revised_plan = _enforce_logical_consistency(
        plan=revised_plan,
        question=question,
        human_feedback=human_feedback,
        feedback_history=feedback_history,
    )

    return revised_plan.strip()


def regenerate_analysis_plan(state: ClinicalAnalyticsState):
    """
    Regenerate the analysis plan using:

    - Original user question
    - Current analysis plan (draft)
    - Approved database schema & relationships
    - Human feedback (current + cumulative history)

    CRITICAL RULES:
    1. Human feedback OVERRIDES CONFLICTING PARTS of the previous analysis plan.
    2. Treat original analysis plan as a draft, not as fixed instructions.
    3. If feedback changes the grouping dimension, replace the old grouping dimension.
    4. If feedback conflicts with an existing filter (e.g. grouping by encounter class
       conflicts with filtering by inpatient), remove the conflicting filter!
    5. Do not blindly preserve filters from the previous plan.
    6. Keep valid data-quality bounds (e.g. LOS 0-30 days, valid START/STOP dates).
    7. Only keep tables and joins actually required by the revised analysis.
    8. Perform a logical consistency check before returning.
    """

    question = state["user_question"]
    database_schema = state["database_schema"]
    current_plan = state.get("analysis_plan", "")
    human_feedback = (state.get("human_feedback") or "").strip()
    feedback_history = list(state.get("feedback_history") or [])
    plan_version = state.get("plan_version", 1) + 1

    # Accumulate feedback into feedback_history so successive rejections are preserved
    if human_feedback and human_feedback not in feedback_history:
        feedback_history.append(human_feedback)

    print("\n" + "=" * 70)
    print(f"REGENERATING ANALYSIS PLAN (Version {plan_version})")
    print("=" * 70)
    print("\nFeedback history:", feedback_history)
    print("\nLatest feedback:", human_feedback)

    # Format feedback history for the prompt
    if feedback_history:
        feedback_prompt_section = "Human reviewer requested the following corrections across review iterations:\n"
        for idx, fb in enumerate(feedback_history, 1):
            feedback_prompt_section += f"  {idx}. {fb}\n"
    elif human_feedback:
        feedback_prompt_section = f"Human feedback:\n{human_feedback}\n"
    else:
        feedback_prompt_section = "Human feedback:\n(No specific correction text provided. Refine and enhance the plan for clinical accuracy and strict schema adherence.)\n"

    prompt = f"""
You are a senior clinical analytics planning architect.

The human reviewer reviewed the previous analysis plan and rejected it, providing specific feedback.

Your objective: Generate a REVISED, COMPLETE, AND INTERNALLY CONSISTENT analysis plan that implements the human reviewer's feedback.

User clinical question:
{question}

Approved database schema & relationships:
{database_schema}

Current analysis plan (draft):
{current_plan}

{feedback_prompt_section}

==================================================
CRITICAL RULES FOR REGENERATION:
==================================================

1. HUMAN FEEDBACK OVERRIDES CONFLICTING PARTS OF THE PREVIOUS PLAN:
   - Treat the original analysis plan as a draft, NOT as fixed instructions.
   - Carefully interpret the human feedback.
   - If the feedback changes the grouping dimension (e.g., 'Instead of grouping by diagnosis, group the results by encounter class and calculate the average length of stay for each encounter class'), REPLACE the old grouping dimension with the new grouping dimension.
   - If the feedback conflicts with an existing filter, REMOVE OR MODIFY THE CONFLICTING FILTER. Do NOT blindly preserve conflicting filters!
   - For example: Grouping by encounter class requires multiple encounter classes to remain in the dataset. Therefore, do NOT restrict encounters.ENCOUNTERCLASS to 'inpatient'! REMOVE the inpatient filter when grouping by encounter class, so the result can contain multiple encounter classes.

2. KEEP DATA-QUALITY RULES:
   - Preserve valid data-quality bounds:
     * DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30 (unless the user explicitly asked to remove the 30-day LOS restriction).
     * Exclude NULL START and STOP values: encounters.START IS NOT NULL AND encounters.STOP IS NOT NULL.

3. ONLY KEEP NECESSARY TABLES AND JOINS:
   - Only keep tables and columns that are actually required by the revised analysis.
   - For example: If diagnosis is replaced with encounter class, and diagnosis is no longer needed, REMOVE conditions.DESCRIPTION, conditions.ENCOUNTER, and the join encounters.ID = conditions.ENCOUNTER. Set join conditions to: None (single-table query on encounters).
   - Do NOT include unnecessary tables or joins.

4. LOGICAL CONSISTENCY CHECK BEFORE RETURNING:
   - Does the grouping match the user's request?
   - Do filters conflict with the grouping? (Ensure no filter restricts the grouping column to a single value).
   - Are all selected tables/columns necessary?
   - Does the calculation answer the user's requested metric?

5. SCHEMA INTEGRITY:
   - Use ONLY tables and columns from the approved schema. Never invent non-existent column or table names.

6. DO NOT GENERATE SQL:
   - Do NOT generate SQL during analysis plan regeneration.

7. RETURN ONLY THE REVISED ANALYSIS PLAN with these sections:
   - 1. Relevant Tables and Columns
   - 2. Join Conditions
   - 3. Derived Calculations
   - 4. Aggregations & Grouping
   - 5. Filtering
"""

    try:
        revised_plan = generate_response(prompt)

    except RuntimeError as error:
        print("LLM analysis-plan regeneration unavailable. Using deterministic fallback.")

        # Check if feedback requested grouping by encounter class
        combined_fb = " ".join(feedback_history + [human_feedback]).lower()
        if "encounter class" in combined_fb or "encounterclass" in combined_fb:
            fallback_plan = _deterministic_analysis_plan(
                question="What is the average length of stay by encounter class?",
                database_schema=database_schema,
            )
        else:
            fallback_plan = _deterministic_analysis_plan(
                question=question,
                database_schema=database_schema,
            )

        if fallback_plan is not None:
            revised_plan = fallback_plan
        else:
            raise error

    # Deterministically enforce preservation and logical consistency
    revised_plan = _preserve_plan_requirements(
        current_plan=current_plan,
        revised_plan=revised_plan,
        human_feedback=human_feedback,
        feedback_history=feedback_history,
        question=question,
    )

    print("\nRevised Analysis Plan:")
    print(revised_plan)

    approval_source = state.get("approval_source", "api")

    record_audit_event(
        action="ANALYSIS_PLAN_REGENERATED",
        details=f"Regenerated analysis plan to v{plan_version} incorporating human review feedback",
        user_agent="AI Planner",
        entity_type="PLAN",
        entity_name=f"plan_v{plan_version}",
    )

    return {
        "user_question": question,
        "database_schema": database_schema,
        "analysis_plan": revised_plan,
        "approval_status": "pending",
        "approval_source": approval_source,
        "human_feedback": human_feedback,
        "feedback_history": feedback_history,
        "plan_version": plan_version,
        "error": "",
    }


# ============================================================
# 6. REGENERATION ROUTER
# ============================================================

def regeneration_router(state: ClinicalAnalyticsState):
    """
    Route the workflow after analysis plan regeneration.

    For API requests, terminate at END so the API returns the revised plan
    with approval_status='pending' and waits for human action.

    For interactive CLI requests, route to human_approval so the human can review
    and approve or reject the revised plan in the terminal.
    """
    approval_source = state.get("approval_source")
    if approval_source == "api" or state.get("approval_status") == "pending":
        return END

    return "human_approval"


# ============================================================
# 7. APPROVAL ROUTER
# ============================================================

def approval_router(state: ClinicalAnalyticsState):

    if state.get("approval_status") == "approved":
        return "generate_sql"

    if state.get("approval_status") == "rejected":
        return "regenerate_analysis_plan"

    if state.get("approval_status") == "pending":
        return END

    return END

# ============================================================
# 7. GENERATE SQL
# ============================================================

def generate_sql_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    # If SQL query already exists (e.g. during query execution retry) and regenerate_sql is not requested, preserve it!
    if state.get("sql_query") and not state.get("regenerate_sql"):
        print("\nPreserving existing SQL query for execution retry:")
        print(state["sql_query"])
        return {
            "sql_query": state["sql_query"]
        }

    try:
        sql = generate_sql(
            user_question=state["user_question"],
            analysis_plan=state["analysis_plan"],
            database_schema=state["database_schema"],
        )
        record_audit_event(
            action="SQL_GENERATED",
            details=f"Synthesized SQL query ({len(sql)} chars) adhering to approved schema rules",
            user_agent="Text-to-SQL Engine",
            entity_type="QUERY",
            entity_name="sql_query",
        )
        return {
            "sql_query": sql
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        error_msg = str(exc)
        exc_type = type(exc).__name__
        print(f"SQL Generation failed: {error_msg}")
        return {
            "error": f"SQL generation failed: {error_msg}",
            "failed_node": "generate_sql",
            "exception_type": exc_type,
        }


# ============================================================
# 8. VALIDATE SQL
# ============================================================

def validate_sql_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    is_valid, message = validate_sql(
        state["sql_query"],
        approved_schema=state["database_schema"],
        analysis_plan=state.get("analysis_plan"),
    )

    if not is_valid:
        record_audit_event(
            action="SQL_VALIDATED",
            details=f"SQL validation failed: {message[:120]}",
            user_agent="SQL Validator",
            status="FAILED",
            entity_type="QUERY",
            entity_name="sql_query",
        )
        return {
            "error": f"SQL validation failed: {message}",
            "failed_node": "validate_sql",
            "exception_type": "SQLValidationError",
        }

    record_audit_event(
        action="SQL_VALIDATED",
        details="SQL query passed syntax and schema validation against approved catalog",
        user_agent="SQL Validator",
        status="SUCCESS",
        entity_type="QUERY",
        entity_name="sql_query",
    )
    return {
        "error": ""
    }


# ============================================================
# 9. EXECUTE SQL
# ============================================================

def execute_sql_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    try:
        results = execute_query(
            state["sql_query"]
        )
        record_audit_event(
            action="SQL_EXECUTED",
            details=f"Read-only SQL query executed successfully, returned {len(results)} rows",
            user_agent="Query Executor",
            status="SUCCESS",
            entity_type="QUERY",
            entity_name="sql_query",
        )

        return {
            "query_result": results,
            "error": "",
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        error_msg = str(exc)
        exc_type = type(exc).__name__
        print("\n" + "=" * 70)
        print("QUERY EXECUTION ERROR DIAGNOSTICS")
        print("=" * 70)
        print(f"Failed Node: execute_sql")
        print(f"Exception Type: {exc_type}")
        print(f"Database Error: {error_msg}")
        print(f"SQL Query:\n{state.get('sql_query')}")
        print("=" * 70 + "\n")

        record_audit_event(
            action="SQL_EXECUTED",
            details=f"SQL query execution failed: {error_msg[:120]}",
            user_agent="Query Executor",
            status="FAILED",
            entity_type="QUERY",
            entity_name="sql_query",
        )

        return {
            "error": f"Query execution failed: {error_msg}",
            "failed_node": "execute_sql",
            "exception_type": exc_type,
        }


# ============================================================
# 10. VALIDATE RESULTS
# ============================================================

def validate_results_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    validation = validate_results(
        state.get("query_result", [])
    )

    if not validation["valid"]:
        record_audit_event(
            action="RESULT_VALIDATED",
            details=f"Result validation failed: {validation.get('message', '')[:120]}",
            user_agent="Result Validator",
            status="FAILED",
            entity_type="RESULTS",
            entity_name="query_results",
        )
        return {
            "result_validation": validation,
            "error": validation["message"],
        }

    validated_rows = validation.get("rows", [])

    insight_evidence = build_insight_evidence(
        validated_rows
    )

    record_audit_event(
        action="RESULT_VALIDATED",
        details=f"Verified {len(validated_rows)} rows against data quality and clinical consistency checks",
        user_agent="Result Validator",
        status="SUCCESS",
        entity_type="RESULTS",
        entity_name="query_results",
    )

    print("\n" + "=" * 70)
    print("DETERMINISTIC INSIGHT EVIDENCE")
    print("=" * 70)
    print(insight_evidence)

    return {
        "result_validation": validation,
        "insight_evidence": insight_evidence,
        "error": "",
    }


# ============================================================
# 11. RETRIEVE RAG CONTEXT
# ============================================================

def retrieve_rag_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    try:
        context = get_insight_context(
            user_question=state["user_question"],
            analysis_plan=state.get("analysis_plan"),
            k=2,
        )
        record_audit_event(
            action="RAG_RETRIEVAL",
            details=f"Retrieved clinical domain context ({len(context)} chars) from knowledge base",
            user_agent="RAG Agent",
            status="SUCCESS",
            entity_type="RAG",
            entity_name="clinical_knowledge",
        )

    except Exception as e:
        print(f"RAG context retrieval note: {e}")
        context = ""

    return {
        "rag_context": context
    }


# ============================================================
# 12. GENERATE INSIGHT
# ============================================================

def generate_insight_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    insight = generate_insight(
        user_question=state["user_question"],
        query_results=state["query_result"],
        rag_context=state["rag_context"],
        insight_evidence=state.get(
            "insight_evidence",
            {},
        ),
    )

    record_audit_event(
        action="INSIGHT_GENERATED",
        details=f"Synthesized evidence-backed clinical insights ({len(insight)} chars)",
        user_agent="Clinical Insight Engine",
        status="SUCCESS",
        entity_type="INSIGHT",
        entity_name="clinical_insight",
    )

    return {
        "insight": insight
    }


# ============================================================
# 13. VALIDATE INSIGHT
# ============================================================

def validate_insight_node(state: ClinicalAnalyticsState):
    """
    Deterministically validate the generated insight
    against verified SQL results.
    """

    if state.get("error"):
        return {}

    validation = validate_insight(
        insight=state["insight"],
        query_results=state["query_result"],
        insight_evidence=state.get(
            "insight_evidence",
            {},
        ),
    )

    if not validation["valid"]:

        retry_count = state.get(
            "insight_retry_count",
            0,
        )

        if retry_count >= 2:
            return {
                "error": (
                    "Insight validation failed after "
                    "maximum regeneration attempts."
                ),
                "failed_node": "validate_insight",
                "exception_type": "InsightValidationError",
            }

        return {
            "error": (
                "Insight validation failed: "
                f"{validation['message']}"
            ),
            "failed_node": "validate_insight",
            "exception_type": "InsightValidationError",
        }

    return {
        "error": "",
        "failed_node": None,
        "exception_type": None,
    }


# ============================================================
# 14. REGENERATE INSIGHT
# ============================================================

def regenerate_insight_node(state: ClinicalAnalyticsState):
    """
    Regenerate the insight after deterministic validation fails.
    """

    retry_count = state.get(
        "insight_retry_count",
        0,
    )

    if retry_count >= 2:
        return {
            "error": (
                "Insight validation failed after "
                "maximum regeneration attempts."
            )
        }

    validation_message = state.get(
        "error",
        "Insight validation failed."
    )

    try:
        corrected_insight = regenerate_insight(
            user_question=state["user_question"],
            query_results=state["query_result"],
            rag_context=state.get(
                "rag_context",
                "",
            ),
            validation_message=validation_message,
            insight_evidence=state.get(
                "insight_evidence",
                {},
            ),
        )

    except RuntimeError:

        # If the LLM is unavailable during regeneration,
        # reuse the deterministic insight generator.
        corrected_insight = generate_insight(
            user_question=state["user_question"],
            query_results=state["query_result"],
            rag_context=state.get(
                "rag_context",
                "",
            ),
            insight_evidence=state.get(
                "insight_evidence",
                {},
            ),
        )

    return {
        "insight": corrected_insight,
        "insight_retry_count": retry_count + 1,
        "error": "",
    }


# ============================================================
# 15. PIPELINE & INSIGHT ROUTERS
# ============================================================

def generate_sql_router(state: ClinicalAnalyticsState):
    if state.get("error"):
        return END
    return "validate_sql"


def validate_sql_router(state: ClinicalAnalyticsState):
    if state.get("error"):
        return END
    return "execute_sql"


def execute_sql_router(state: ClinicalAnalyticsState):
    if state.get("error"):
        return END
    return "validate_results"


def validate_results_router(state: ClinicalAnalyticsState):
    if state.get("error"):
        return END
    return "retrieve_rag"


def insight_validation_router(state: ClinicalAnalyticsState):

    error = state.get("error", "")
    retry_count = state.get(
        "insight_retry_count",
        0,
    )

    if not error:
        return "generate_chart"

    if state.get("failed_node") == "validate_insight" and retry_count < 2:
        return "regenerate_insight"

    return "stop"


# ============================================================
# 16. GENERATE CHART
# ============================================================

def generate_chart_node(state: ClinicalAnalyticsState):
    """
    Generate a chart specification from ONLY validated SQL results.

    NOTE: We build only the lightweight chart *specification* dict here.
    The frontend renders the chart itself from that spec + the raw result rows.
    We intentionally do NOT call create_bar_chart / px.bar() here because
    loading Plotly's full validator JSON is memory-intensive and not needed
    server-side (the Plotly Figure object is never serialised or returned).
    """

    if state.get("error"):
        return {}

    result_validation = state.get(
        "result_validation",
        {}
    )

    validated_rows = result_validation.get(
        "rows",
        []
    )

    # Fallback to query_result if result_validation rows is empty
    if not validated_rows:
        validated_rows = state.get("query_result", [])

    if not validated_rows:
        return {
            "chart_spec": None,
            "visualization_error": "No verified result rows available for chart generation",
            "error": "",
        }

    try:
        chart_spec = create_chart_spec(
            results=validated_rows,
        )
        record_audit_event(
            action="CHART_GENERATED",
            details=f"Constructed visualization spec ({chart_spec.get('chart_type', 'bar')} chart) from validated query data",
            user_agent="Visualization Engine",
            status="SUCCESS",
            entity_type="CHART",
            entity_name=chart_spec.get('chart_type', 'bar'),
        )
        return {
            "chart_spec": chart_spec,
            "error": "",
        }
    except Exception as exc:
        print(f"Chart spec generation fallback triggered: {exc}")
        first_row = validated_rows[0]
        cols = list(first_row.keys())
        x_col = cols[0] if cols else "category"
        y_col = cols[1] if len(cols) > 1 else x_col
        fallback_spec = {
            "chart_type": "bar",
            "title": f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
            "x_column": x_col,
            "y_column": y_col,
        }
        record_audit_event(
            action="CHART_GENERATED",
            details=f"Constructed fallback visualization spec ({fallback_spec.get('chart_type', 'bar')} chart)",
            user_agent="Visualization Engine",
            status="SUCCESS",
            entity_type="CHART",
            entity_name="fallback_chart",
        )
        return {
            "chart_spec": fallback_spec,
            "visualization_error": f"Generated fallback chart spec: {exc}",
            "error": "",
        }


# ============================================================
# 17. BUILD LANGGRAPH
# ============================================================

def build_graph():

    workflow = StateGraph(
        ClinicalAnalyticsState
    )

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    workflow.add_node(
        "load_schema",
        load_schema
    )

    workflow.add_node(
        "analyze_question",
        analyze_question
    )

    workflow.add_node(
        "human_approval",
        human_approval_node
    )

    workflow.add_node(
        "regenerate_analysis_plan",
        regenerate_analysis_plan
    )

    workflow.add_node(
        "generate_sql",
        generate_sql_node
    )

    workflow.add_node(
        "validate_sql",
        validate_sql_node
    )

    workflow.add_node(
        "execute_sql",
        execute_sql_node
    )

    workflow.add_node(
        "validate_results",
        validate_results_node
    )

    workflow.add_node(
        "retrieve_rag",
        retrieve_rag_node
    )

    workflow.add_node(
        "generate_insight",
        generate_insight_node
    )

    workflow.add_node(
        "validate_insight",
        validate_insight_node
    )

    workflow.add_node(
        "regenerate_insight",
        regenerate_insight_node
    )

    workflow.add_node(
        "generate_chart",
        generate_chart_node
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    workflow.add_edge(
        START,
        "load_schema"
    )

    # --------------------------------------------------------
    # QUESTION ANALYSIS
    # --------------------------------------------------------

    workflow.add_edge(
        "load_schema",
        "analyze_question"
    )

    # --------------------------------------------------------
    # HUMAN REVIEW
    # --------------------------------------------------------

    workflow.add_edge(
        "analyze_question",
        "human_approval"
    )

    # --------------------------------------------------------
    # HUMAN APPROVAL ROUTING
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "human_approval",
        approval_router,
        {
            "generate_sql": "generate_sql",
            "regenerate_analysis_plan": "regenerate_analysis_plan",
            END: END,
        },
    )

    # --------------------------------------------------------
    # REGENERATION ROUTING
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "regenerate_analysis_plan",
        regeneration_router,
        {
            "human_approval": "human_approval",
            END: END,
        },
    )

    # --------------------------------------------------------
    # SQL PIPELINE
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "generate_sql",
        generate_sql_router,
        {
            "validate_sql": "validate_sql",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "validate_sql",
        validate_sql_router,
        {
            "execute_sql": "execute_sql",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "execute_sql",
        execute_sql_router,
        {
            "validate_results": "validate_results",
            END: END,
        },
    )

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "validate_results",
        validate_results_router,
        {
            "retrieve_rag": "retrieve_rag",
            END: END,
        },
    )

    workflow.add_edge(
        "retrieve_rag",
        "generate_insight"
    )

    # --------------------------------------------------------
    # INSIGHT VALIDATION & VISUALIZATION
    # --------------------------------------------------------

    workflow.add_edge(
        "generate_insight",
        "validate_insight"
    )

    workflow.add_conditional_edges(
        "validate_insight",
        insight_validation_router,
        {
            "generate_chart": "generate_chart",
            "regenerate_insight": "regenerate_insight",
            "stop": END,
        },
    )

    workflow.add_edge(
        "regenerate_insight",
        "validate_insight"
    )

    workflow.add_edge(
        "generate_chart",
        END
    )

    return workflow.compile()


# ============================================================
# COMPILED GRAPH
# ============================================================

clinical_analytics_graph = build_graph()