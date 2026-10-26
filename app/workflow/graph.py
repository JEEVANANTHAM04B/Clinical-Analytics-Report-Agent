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
from app.analytics.result_validator import validate_results, result_contract
from app.analytics.cache import ResultCache

_result_cache = ResultCache()

def _cache_context(state):
    signature = state.get("data_signature", {})
    return {"dataset_versions": signature.get("versions", {}),
        "schema": signature.get("schema", {}), "question": state.get("user_question"),
        "plan": state.get("analysis_plan"), "sql": state.get("sql_query"),
        "tables": sorted(state.get("selected_tables", [])), "configuration": "result-quality-v1"}

from app.workflow.reliability import failure, retry_limit, transient
from app.analytics.insight_evidence import build_insight_evidence
from app.database.schema_service import get_database_schema
from app.workflow.state import ClinicalAnalyticsState

from app.visualization.chart_generator import (
    create_chart_spec,
)
from app.audit.service import record_audit_event
from dataclasses import asdict
from typing import Optional, Dict, Any, List
from app.clinical import (
    registry as clinical_registry,
    build_clinical_question_plan,
    ClinicalQuestionPlan,
)
from app.clinical.table_validator import (
    check_table_selection,
    enforce_sql_table_boundaries,
    extract_sql_tables_ast,
)


def _is_clinical_context(database_schema: Optional[Dict[str, Any]]) -> bool:
    """
    Detect whether the execution context targets CDISC clinical-trial schema
    or legacy EHR schema. Defaults to clinical-trial schema as active.
    """
    if not database_schema or not database_schema.get("tables"):
        return True

    tables = {t.lower() for t in database_schema.get("tables", {})}
    clinical_markers = {"dm", "adsl", "ae", "adae", "adlb", "advs", "adresp", "study", "sites", "lb", "ex", "qs", "vs"}
    legacy_markers = {"encounters", "conditions", "patients", "medications", "observations", "procedures"}

    if any(t in tables for t in clinical_markers):
        return True
    if any(t in tables for t in legacy_markers):
        return False

    return True


def format_clinical_analysis_plan(plan: ClinicalQuestionPlan) -> str:
    """
    Format a ClinicalQuestionPlan into the standard 5-section markdown analysis plan
    for the LangGraph workflow.
    """
    sections = ["### Clinical Analytics Analysis Plan\n"]

    # Section 1: Relevant Tables and Columns
    sections.append("#### 1. Relevant Tables and Columns")
    for ds_name in plan.datasets:
        ds_meta = clinical_registry.get_dataset(ds_name)
        sections.append(f"* **`{ds_name}`**:")
        ds_cols = []
        for col_ref in plan.required_columns:
            if "." in col_ref:
                t, c = col_ref.split(".", 1)
                if t.lower() == ds_name.lower():
                    ds_cols.append(c)
            else:
                ds_cols.append(col_ref)
        if not ds_cols and ds_meta:
            ds_cols = list(ds_meta.primary_key)
        for col_name in ds_cols:
            col_meta = clinical_registry.get_column(ds_name, col_name)
            dtype = col_meta.data_type if col_meta else "VARCHAR"
            desc = f" ({col_meta.description})" if col_meta and col_meta.description else ""
            sections.append(f"  * `{col_name.upper()}` ({dtype}):{desc}")
    sections.append("")

    # Section 2: Join Conditions
    sections.append("#### 2. Join Conditions")
    if plan.requires_join and len(plan.join_tables) >= 2:
        for i in range(len(plan.join_tables) - 1):
            t1, t2 = plan.join_tables[i], plan.join_tables[i + 1]
            join_sql = clinical_registry.get_join_sql(t1, t2)
            if join_sql:
                sections.append(f"* Join `{t1}` and `{t2}`: `{join_sql}`")
            else:
                sections.append(f"* Join `{t1}` and `{t2}` on approved relational key.")
    else:
        primary = plan.primary_dataset or (plan.datasets[0] if plan.datasets else "primary table")
        sections.append(f"* None (single-table query on `{primary}`).")
    sections.append("")

    # Section 3: Derived Calculations
    metric_title = plan.metric.replace("_", " ").title()
    sections.append("#### 3. Derived Calculations")
    sections.append(f"* **{metric_title}**:\n  Calculate using:\n  `{plan.calculation}`")
    sections.append("")

    # Section 4: Aggregations & Grouping
    sections.append("#### 4. Aggregations & Grouping")
    if plan.dimensions:
        dims_str = ", ".join(f"`{d}`" for d in plan.dimensions)
        sections.append(f"* **Grouping**:\n  Group results by {dims_str}.")
        sections.append(f"* **Aggregation**:\n  `{plan.calculation}`")
    else:
        sections.append("* **Grouping**:\n  None (overall clinical summary).")
        sections.append(f"* **Aggregation**:\n  `{plan.calculation}`")
    sections.append("")

    # Section 5: Filtering
    sections.append("#### 5. Filtering")
    if plan.filter_conditions:
        for f in plan.filter_conditions:
            sections.append(f"* Apply filter: `{f}`")
    else:
        sections.append("* None.")

    return "\n".join(sections).strip()



# ============================================================
# 0. VALIDATE TABLE SELECTION BOUNDARY
# ============================================================

def validate_table_selection_node(state: ClinicalAnalyticsState):
    """
    Strict boundary check: ensures user table selection covers all datasets
    required to answer the clinical question. Blocks pipeline if missing.
    """
    question = state.get("user_question", "")
    selected_tables = state.get("selected_tables", [])
    current_plan = state.get("analysis_plan")

    # API plan creation may omit table selection because the plan itself
    # determines the minimum datasets. Explicit selections and execution
    # requests still go through the same strict selection boundary.
    if (
        "selected_tables" not in state
        and state.get("approval_source", "api") == "api"
        and state.get("approval_status") in {"pending", "rejected"}
    ):
        clinical_plan = build_clinical_question_plan(question)
        if clinical_plan.is_supported:
            selected_tables = clinical_plan.datasets

    validation = check_table_selection(
        question=question,
        selected_tables=selected_tables,
        current_plan=current_plan,
    )

    if validation["status"] == "blocked":
        err_msg = validation["message"]
        record_audit_event(
            action="TABLE_SELECTION_BLOCKED",
            details=f"Analysis blocked. Reason: {validation['reason']}. Missing: {', '.join(validation['missing_tables'])}",
            user_agent="Table Boundary Guard",
            status="BLOCKED",
            entity_type="BOUNDARY",
            entity_name="table_selection",
        )
        return {
            "validation_status": "blocked",
            "reason": validation["reason"],
            "required_tables": validation["required_tables"],
            "selected_tables": validation["selected_tables"],
            "missing_tables": validation["missing_tables"],
            "validation_message": validation["message"],
            "next_action": validation["next_action"],
            "error": err_msg,
            "failed_node": "validate_table_selection",
            "exception_type": "TableSelectionBoundaryError",
        }

    return {
        "validation_status": "passed",
        "reason": None,
        "required_tables": validation["required_tables"],
        "selected_tables": validation["selected_tables"],
        "missing_tables": [],
        "validation_message": "All required tables are selected and authorized.",
        "next_action": None,
        "error": "",
    }


def table_selection_router(state: ClinicalAnalyticsState):
    """
    Conditional edge router after table selection validation at the execution boundary.
    If validation blocked, terminate immediately at END without running downstream stages.
    """
    if state.get("validation_status") == "blocked" or state.get("error"):
        return END
    return "generate_sql"


# ============================================================
# 1. LOAD DATABASE SCHEMA
# ============================================================

def load_schema(state: ClinicalAnalyticsState):
    schema = get_database_schema()
    return {
        "database_schema": schema,
        "clinical_question_plan": state.get("clinical_question_plan", {}),
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
    human_feedback: str = "",
) -> str | None:
    """
    Generate a deterministic analysis plan for a supported
    clinical trial analytics pattern or legacy EHR pattern when the LLM is unavailable.
    """
    normalized_question = question.lower()

    # Clinical trial analytics schema path
    if _is_clinical_context(database_schema):
        cplan = None
        if human_feedback:
            cplan_with_fb = build_clinical_question_plan(f"{question} {human_feedback}")
            if cplan_with_fb and cplan_with_fb.is_supported:
                cplan = cplan_with_fb
        if cplan is None:
            cplan = build_clinical_question_plan(question)

        # Strengthen plan if feedback indicates treatment-arm stratification
        if cplan and cplan.is_supported:
            fb_lower = (human_feedback or "").lower()
            if any(term in fb_lower for term in [
                "treatment arm", "treatment arms", "trt01a", "treatment-arm", "adsl", "arm", "arms", "cohort", "cohorts"
            ]):
                if "adae" in cplan.datasets and "adsl" not in cplan.datasets:
                    datasets = list(cplan.datasets)
                    if "adsl" not in datasets:
                        datasets.insert(0, "adsl")
                    required_columns = list(cplan.required_columns)
                    if "adsl.USUBJID" not in required_columns:
                        required_columns.insert(0, "adsl.USUBJID")
                    if "adsl.TRT01A" not in required_columns:
                        required_columns.insert(1, "adsl.TRT01A")
                    dimensions = list(cplan.dimensions)
                    if "TRT01A" not in dimensions:
                        dimensions.insert(0, "TRT01A")
                    join_tables = ["adsl", "adae"]
                    calculation = (
                        "COUNT(*) GROUP BY adsl.TRT01A, adae.AESEV"
                        if "AESEV" in dimensions
                        else "COUNT(*) GROUP BY adsl.TRT01A"
                    )
                    cplan = ClinicalQuestionPlan(
                        question=cplan.question,
                        is_supported=True,
                        question_type=cplan.question_type,
                        matched_kpi_id="AE_SEVERITY_DISTRIBUTION" if "AESEV" in dimensions else cplan.matched_kpi_id,
                        metric=cplan.metric,
                        primary_dataset="adae",
                        datasets=datasets,
                        dimensions=dimensions,
                        required_columns=required_columns,
                        calculation=calculation,
                        requires_join=True,
                        join_tables=join_tables,
                        filter_conditions=cplan.filter_conditions,
                        suggested_sql="""SELECT adsl.TRT01A AS treatment_arm, adae.AESEV AS severity, COUNT(*) AS event_count
FROM adsl
JOIN adae ON adsl.USUBJID = adae.USUBJID
GROUP BY adsl.TRT01A, adae.AESEV
ORDER BY adsl.TRT01A, event_count DESC;""".strip(),
                        confidence=cplan.confidence,
                        explanation=f"{cplan.explanation} Updated with treatment-arm stratification from reviewer feedback."
                    )
            return format_clinical_analysis_plan(cplan)
        return (
            "### Clinical Analytics Analysis Plan (Unsupported Domain)\n\n"
            "This question is not supported by the active Clinical Trial CDISC dataset. "
            "Please ask a question related to enrollment, demographics, treatment arms, "
            "adverse events, laboratory values, vital signs, efficacy, or subject disposition.\n\n"
            "#### 1. Relevant Tables and Columns\n"
            "* None (Question outside CDISC clinical trial schema scope)\n\n"
            "#### 2. Join Conditions\n"
            "* None\n\n"
            "#### 3. Derived Calculations\n"
            "* None\n\n"
            "#### 4. Aggregations & Grouping\n"
            "* None\n\n"
            "#### 5. Filtering\n"
            "* None"
        )

    # If the schema context is explicitly legacy EHR, check legacy EHR patterns first
    if not _is_clinical_context(database_schema):
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

    # 1. CDISC Clinical Trial Question Plan
    clinical_plan = build_clinical_question_plan(question)
    if clinical_plan.is_supported:
        return format_clinical_analysis_plan(clinical_plan)

    # 2. Legacy EHR analytics pattern fallback
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
    if state.get("error"):
        return {
            "analysis_plan": "",
            "clinical_question_plan": state.get("clinical_question_plan", {}),
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
            "error": state["error"],
            "failed_node": state.get("failed_node", "load_schema"),
            "exception_type": state.get("exception_type", "WorkflowExecutionError"),
        }

    question = state["user_question"]
    database_schema = state.get("database_schema") or {}
    existing_plan = state.get("analysis_plan") or state.get("current_plan")
    approval_status = state.get("approval_status")

    # The backend must never pass an empty schema to analysis-plan generation without an explicit error
    if not database_schema.get("tables"):
        err_msg = state.get("error") or "Cannot generate analysis plan: active database schema is empty or contains no valid clinical tables."
        return {
            "analysis_plan": "",
            "clinical_question_plan": state.get("clinical_question_plan", {}),
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
            "error": err_msg,
            "failed_node": state.get("failed_node", "load_schema"),
            "exception_type": state.get("exception_type", "SchemaValidationError"),
        }

    # If an analysis plan is already provided (e.g. approving a plan or rejecting to regenerate),
    # preserve it rather than overwriting it with an uncorrected initial plan!
    if existing_plan and approval_status in ("approved", "rejected"):
        cplan_sync = state.get("clinical_question_plan")
        if not cplan_sync and question:
            q_plan = build_clinical_question_plan(question)
            if q_plan and q_plan.is_supported:
                cplan_sync = asdict(q_plan)
        return {
            "analysis_plan": existing_plan,
            "current_plan": existing_plan,
            "clinical_question_plan": cplan_sync or {},
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
            "error": "",
        }

    is_clinical = _is_clinical_context(database_schema)
    clinical_plan = build_clinical_question_plan(question)
    plan_dict = asdict(clinical_plan) if (clinical_plan and clinical_plan.is_supported) else {}

    if is_clinical and clinical_plan.is_supported and clinical_plan.metric == "age_distribution_and_mean":
        # This multi-measure question needs explicit age bands and a mean per arm.
        # A deterministic plan keeps the preview aligned with the safe SQL mapping.
        plan = format_clinical_analysis_plan(clinical_plan)
        record_audit_event(
            action="ANALYSIS_PLAN_GENERATED",
            details=f"Generated age-distribution analysis plan (v{state.get('plan_version', 1)}) for query: '{question[:60]}...'",
            user_agent="AI Planner (Deterministic)",
            entity_type="PLAN",
            entity_name=f"plan_v{state.get('plan_version', 1)}",
        )
        return {
            "analysis_plan": plan,
            "clinical_question_plan": plan_dict,
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
            "error": "",
        }

    if is_clinical:
        schema_context = clinical_registry.build_schema_context_for_prompt()
        prompt = f"""
You are a senior clinical analytics planning assistant specialized in CDISC SDTM and ADaM clinical trials.

Analyze the user's natural-language clinical analytics question and generate a structured, precise analysis plan using ONLY the approved CDISC database schema provided below.

User question:
{question}

Approved clinical database schema:
{database_schema}

==================================================
CDISC CLINICAL TRIAL DOMAIN RULES:

1. Subject Population & Demographics (DM / ADSL):
   - "subjects", "enrolled", "patients", "total subjects" refers to distinct subject count:
     use DM table, calculate COUNT(DISTINCT dm.USUBJID).
   - "age", "average age", "mean age" refers to subject age:
     use DM table, calculate AVG(dm.AGE) or ROUND(AVG(dm.AGE), 2).
   - "treatment arm", "cohort", "arm" refers to treatment group:
     use ADSL (TRT01A) or DM (ARM).

2. Safety & Adverse Events (AE / ADAE):
   - "adverse events", "AE count", "total AEs" refers to incident adverse events:
     use AE table, calculate COUNT(*).
   - "serious adverse events", "serious AEs", "SAE" refers to serious events:
     use AE table, filter WHERE ae.AESER = 'Y', calculate COUNT(*).
   - "adverse event rate by treatment arm" refers to incidence proportion:
     join ADSL and ADAE on USUBJID, calculate COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID) * 100 grouped by adsl.TRT01A.

3. Laboratory & Biomarkers (LB / ADLB):
   - "lab change", "change from baseline", "laboratory change to Week 8" refers to analysis laboratory results:
     use ADLB table, calculate AVG(adlb.CHG) and AVG(adlb.PCHG) with filter adlb.AVISIT = 'WEEK 8' grouped by adlb.PARAMCD, adlb.TRT01A, adlb.AVISIT.

4. Vital Signs (VS / ADVS):
   - "vital sign change", "vital signs change from baseline" refers to analysis vitals:
     use ADVS table, calculate AVG(advs.CHG) and AVG(advs.PCHG) with filter advs.AVISIT = 'WEEK 8' grouped by advs.PARAMCD, advs.TRT01A, advs.AVISIT.

5. Efficacy & Clinical Response (ADRESP):
   - "efficacy response rate", "response rate by treatment", "responders" refers to clinical responder rate:
     use ADRESP table, calculate COUNT(DISTINCT CASE WHEN RESPFL = 'Y' THEN USUBJID END) / COUNT(DISTINCT USUBJID) * 100 with filter adresp.AVISIT = 'WEEK 8' grouped by adresp.TRT01A, adresp.AVISIT.

6. Study Sites & Centers (SITES / DM):
   - "site enrollment", "highest enrollment", "enrollment by site" refers to subject recruitment per site:
     join SITES and DM on sites.SITEID = dm.SITEID, calculate COUNT(DISTINCT dm.USUBJID) grouped by sites.SITEID, sites.SITE_NAME.

==================================================
ANALYSIS PLAN REQUIREMENTS:

The analysis plan must explicitly state:
1. Relevant Tables and Columns:
   - Exact tables and columns from the approved CDISC schema.
2. Join Conditions:
   - Approved clinical relationships only (e.g., sites.SITEID = dm.SITEID, adsl.USUBJID = adae.USUBJID). If single-table, state None.
   - For joins between subject-level clinical tables (e.g. ADSL and ADAE), specify ONLY USUBJID (adsl.USUBJID = adae.USUBJID). NEVER specify or suggest STUDYID in join conditions.
3. Derived Calculations:
   - Explicit statistical calculation formulas.
4. Aggregations & Grouping:
   - Exact grouping columns and aggregations.
5. Filtering:
   - Explicit filtering conditions (e.g., AESER = 'Y', AVISIT = 'WEEK 8').

STRICT RULES:
- Map natural-language terms ONLY to actual CDISC schema columns.
- NEVER invent tables or columns (do NOT use EHR tables like encounters or conditions).
- For clinical joins, join ONLY on approved foreign keys (e.g. USUBJID). Do NOT include STUDYID in join conditions.
- Do NOT generate SQL.
- Return ONLY the concise, structured analysis plan.
"""
    else:
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
            "clinical_question_plan": plan_dict,
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
                "clinical_question_plan": plan_dict,
                "human_feedback": state.get("human_feedback", ""),
                "feedback_history": state.get("feedback_history", []),
                "plan_version": state.get("plan_version", 1),
                "error": "",
            }

        return {
            "analysis_plan": "",
            "clinical_question_plan": plan_dict,
            "error": str(error),
            "human_feedback": state.get("human_feedback", ""),
            "feedback_history": state.get("feedback_history", []),
            "plan_version": state.get("plan_version", 1),
        }



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

    if state.get("error"):
        return {
            "approval_status": "pending",
            "approval_source": approval_source,
            "human_feedback": "",
            "feedback_history": feedback_history,
            "plan_version": plan_version,
            "error": state["error"],
            "failed_node": state.get("failed_node", "load_schema"),
            "exception_type": state.get("exception_type", "WorkflowExecutionError"),
        }

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


def _sanitize_clinical_plan(plan: str) -> str:
    """
    Apply clinical safety validation to an analysis plan:
    Removes any accidentally injected legacy EHR references (encounters,
    conditions, START, STOP, DATEDIFF, LOS) while strictly preserving CDISC content.
    """
    if not plan:
        return plan

    lines = plan.splitlines()
    sanitized_lines = []
    skip_ehr_block = False

    for line in lines:
        lower = line.lower()
        stripped = line.strip()

        # Check if line starts an EHR table block in Section 1
        if re.search(r'^\s*[*+-]\s*\*\*`?(?:encounters|conditions)`?\*\*', lower):
            skip_ehr_block = True
            continue

        # Check if line is an EHR filter header in Section 5
        if re.search(r'^\s*[*+-]\s*\*\*(?:length of stay range|inpatient encounters only|valid encounter dates|valid diagnosis)\*\*', lower):
            skip_ehr_block = True
            continue

        # Check if line is an EHR derived calculation header in Section 3
        if re.search(r'^\s*[*+-]\s*\*\*(?:length of stay|average length of stay)\*\*', lower):
            skip_ehr_block = True
            continue

        # If inside an EHR block, check if we exited it
        if skip_ehr_block:
            if line.startswith("  ") or line.startswith("\t") or stripped.startswith("* `") or stripped.startswith("- `") or stripped == "":
                continue
            if stripped.startswith("#") or (stripped.startswith("* ") or stripped.startswith("- ")):
                skip_ehr_block = False
            else:
                continue

        # Individual line checks for legacy EHR artifacts
        if any(ehr_artifact in lower for ehr_artifact in [
            "encounters.id = conditions.encounter",
            "conditions.encounter = encounters.id",
            "encounters.start",
            "encounters.stop",
            "encounters.encounterclass",
            "conditions.description",
            "conditions.code",
            "conditions.encounter",
            "datediff(encounters",
            "datediff(",
            "between 0 and 30",
            "0 and 30 days",
            "include only los values",
            "use inpatient encounters only",
            "exclude null start and stop",
            "exclude records where diagnosis description is missing",
        ]):
            continue

        sanitized_lines.append(line)

    result = "\n".join(sanitized_lines).strip()

    # Clean up empty filter or join sections if they were left blank
    result = re.sub(
        r'(#### 5\. Filtering\s*\n)(?:\s*\n)*(#{1,4}|\Z)',
        r'\1* None.\n\n\2',
        result
    )
    result = re.sub(
        r'(#### 2\. Join Conditions\s*\n)(?:\s*\n)*(#{1,4}|\Z)',
        r'\1* None.\n\n\2',
        result
    )
    return result.strip()


def _enforce_logical_consistency(
    plan: str,
    question: str,
    human_feedback: str,
    feedback_history: list[str],
    database_schema: Optional[dict] = None,
) -> str:
    """
    Perform a comprehensive logical consistency check on the regenerated analysis plan:
    1. Does grouping match user feedback?
    2. Do any filters conflict with the grouping?
    3. Are all tables and joins necessary?
    4. Are required data-quality rules preserved?
    """
    if database_schema is not None and _is_clinical_context(database_schema):
        return plan.strip()

    all_fb = " ".join(feedback_history + ([human_feedback] if human_feedback else [])).lower()
    is_ehr = (
        not (database_schema and _is_clinical_context(database_schema))
        and any(
            k in plan.lower() or k in question.lower()
            for k in ["encounter", "encounters", "encounterclass", "length of stay", "los", "datediff(", "conditions."]
        )
    )

    if is_ehr:
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
            plan = _remove_inpatient_filter(plan)

            # C. Remove unnecessary tables and joins:
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
    database_schema: Optional[dict] = None,
) -> str:
    """
    Ensure that regenerating an analysis plan preserves all valid requirements
    from the current/previous plan UNLESS the human feedback explicitly or
    logically overrides them.
    """
    if database_schema is not None and _is_clinical_context(database_schema):
        return revised_plan.strip()

    all_feedback_texts = list(feedback_history) + ([human_feedback] if human_feedback else [])
    combined_feedback = " ".join(all_feedback_texts).lower()
    current_lower = current_plan.lower()
    revised_lower = revised_plan.lower()
    question_lower = question.lower()

    is_ehr = (
        not (database_schema and _is_clinical_context(database_schema))
        and any(
            k in current_lower or k in question_lower
            for k in ["encounter", "encounters", "encounterclass", "length of stay", "los", "datediff(", "conditions."]
        )
    )

    if is_ehr:
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

        # 4. Valid Diagnosis Description Exclusion
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

        # 6. Join Condition
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
        database_schema=database_schema,
    )

    return revised_plan.strip()


def regenerate_analysis_plan(state: ClinicalAnalyticsState):
    """
    Regenerate the analysis plan using:

    - Original user question
    - Current analysis plan (draft)
    - Approved database schema & relationships
    - Human feedback (current + cumulative history)
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

    is_clinical = _is_clinical_context(database_schema)

    if is_clinical:
        prompt = f"""
You are a senior clinical analytics planning architect specializing in CDISC SDTM and ADaM clinical trials.

The human reviewer reviewed the previous analysis plan and requested revisions.
Generate a REVISED, COMPLETE, AND INTERNALLY CONSISTENT clinical analysis plan that implements the human reviewer's feedback.

User clinical question:
{question}

Approved database schema & relationships:
{database_schema}

Current analysis plan (draft):
{current_plan}

{feedback_prompt_section}

CRITICAL RULES:
1. Apply the human reviewer's feedback to update tables, columns, grouping, or filters.
2. Use ONLY tables and columns from the approved CDISC schema.
3. Do NOT invent non-existent column or table names. Do NOT use EHR tables (e.g. encounters, conditions).
4. Do NOT generate SQL.
5. Return ONLY the revised analysis plan with these sections:
   - 1. Relevant Tables and Columns
   - 2. Join Conditions
   - 3. Derived Calculations
   - 4. Aggregations & Grouping
   - 5. Filtering
"""
    else:
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
   - If the feedback changes the grouping dimension, REPLACE the old grouping dimension.
   - If the feedback conflicts with an existing filter, REMOVE OR MODIFY THE CONFLICTING FILTER.

2. KEEP DATA-QUALITY RULES:
   - Preserve valid data-quality bounds:
     * DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30
     * Exclude NULL START and STOP values: encounters.START IS NOT NULL AND encounters.STOP IS NOT NULL.

3. ONLY KEEP NECESSARY TABLES AND JOINS.
4. DO NOT GENERATE SQL.
5. RETURN ONLY THE REVISED ANALYSIS PLAN with these sections:
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
        fallback_plan = _deterministic_analysis_plan(
            question=question,
            database_schema=database_schema,
            human_feedback=human_feedback,
        )

        if fallback_plan is not None:
            revised_plan = fallback_plan
        else:
            raise error

    # Deterministically enforce preservation and logical consistency
    if not is_clinical:
        revised_plan = _preserve_plan_requirements(
            current_plan=current_plan,
            revised_plan=revised_plan,
            human_feedback=human_feedback,
            feedback_history=feedback_history,
            question=question,
            database_schema=database_schema,
        )
    else:
        # Clinical plans must remain completely clinical.
        # Apply clinical safety validation to reject/remove any legacy EHR references.
        revised_plan = _sanitize_clinical_plan(revised_plan)

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

    # Update clinical_question_plan if in clinical context
    if is_clinical:
        combined_q = f"{question} {human_feedback}" if human_feedback else question
        cplan_regen = build_clinical_question_plan(combined_q)
        if not cplan_regen or not cplan_regen.is_supported:
            cplan_regen = build_clinical_question_plan(question)
        if cplan_regen and cplan_regen.is_supported:
            plan_dict = asdict(cplan_regen)
        else:
            plan_dict = state.get("clinical_question_plan", {})
    else:
        plan_dict = state.get("clinical_question_plan", {})

    return {
        "user_question": question,
        "database_schema": database_schema,
        "analysis_plan": revised_plan,
        "clinical_question_plan": plan_dict,
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
    if state.get("error"):
        return END

    if state.get("approval_status") == "approved":
        return "validate_table_selection"

    if state.get("approval_status") == "rejected":
        return "regenerate_analysis_plan"

    if state.get("approval_status") == "pending":
        return END

    return END

# ============================================================
# 7. GENERATE SQL
# ============================================================

def _resolve_authorized_clinical_schema(state: ClinicalAnalyticsState) -> Dict[str, Any]:
    """
    Derives the authorized database schema scope for SQL generation and validation.
    For a clinical question, derives authorization scope from the approved clinical analysis plan
    and clinical question plan, validating all required datasets against ClinicalSchemaRegistry.
    Preserves custom selected tables while preventing stale/default UI selections from
    incorrectly overriding the approved analysis plan.
    """
    current_schema = dict(state.get("database_schema") or {})
    if not _is_clinical_context(current_schema):
        return current_schema

    required_datasets: List[str] = []

    # 1. Datasets from approved analysis_plan (the authoritative specification)
    plan_text = state.get("analysis_plan", "")
    if plan_text:
        from app.analytics.sql_validator import _extract_plan_datasets
        required_datasets.extend(_extract_plan_datasets(plan_text))

    # 2. Datasets from clinical_question_plan if not provided by plan
    if not required_datasets:
        cplan_state = state.get("clinical_question_plan")
        if isinstance(cplan_state, dict):
            required_datasets.extend(cplan_state.get("datasets", []))
        elif hasattr(cplan_state, "datasets"):
            required_datasets.extend(getattr(cplan_state, "datasets", []))

    # 3. Fallback to question planner if not yet extracted
    if not required_datasets and state.get("user_question"):
        q_plan = build_clinical_question_plan(state["user_question"])
        if q_plan.is_supported:
            required_datasets.extend(q_plan.datasets)

    # 4. Strict validation against ClinicalSchemaRegistry and selected_tables boundary
    selected_tables = state.get("selected_tables", [])
    selected_set = {t.lower().strip() for t in selected_tables if t and t.strip()}

    if not selected_set:
        return {"tables": {}, "relationships": []}

    req_set = {ds.lower().strip() for ds in required_datasets if ds and isinstance(ds, str)}

    # A dataset is AUTHORIZED if and only if:
    # 1. It is approved in ClinicalSchemaRegistry
    # 2. It is explicitly selected by the user (selected_set)
    # 3. It is required by the question/analysis plan (or in the approved selection)
    authorized_clinical_datasets = [
        ds for ds in selected_set
        if clinical_registry.has_dataset(ds) and (not req_set or ds in req_set)
    ]

    # 5. Build enriched schema with live database columns & relationships strictly within boundary
    full_db_schema = get_database_schema()
    existing_tables = {}

    for ds in authorized_clinical_datasets:
        if ds in full_db_schema.get("tables", {}):
            existing_tables[ds] = full_db_schema["tables"][ds]
        else:
            ds_meta = clinical_registry.get_dataset(ds)
            if ds_meta:
                existing_tables[ds] = [
                    {"name": col, "type": "VARCHAR", "nullable": True}
                    for col in ds_meta.important_columns
                ]

    # Include relationships between all authorized tables
    all_auth_tables = {k.lower() for k in existing_tables}
    relationships = [
        r for r in full_db_schema.get("relationships", [])
        if r["parent_table"].lower() in all_auth_tables and r["child_table"].lower() in all_auth_tables
    ]

    return {
        "tables": existing_tables,
        "relationships": relationships,
    }


def generate_sql_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    authorized_schema = _resolve_authorized_clinical_schema(state)

    # Safety check: do not generate SQL for unsupported clinical questions or out-of-scope plans
    cplan = build_clinical_question_plan(state["user_question"])
    if _is_clinical_context(authorized_schema) and not cplan.is_supported:
        return {
            "sql_query": None,
            "error": (
                "SQL generation stopped: This question is not supported by the active "
                "Clinical Trial CDISC dataset. Please ask a question related to enrollment, "
                "demographics, treatment arms, adverse events, laboratory values, vital signs, "
                "efficacy, or subject disposition."
            ),
            "failed_node": "generate_sql",
            "exception_type": "UnsupportedClinicalQuestionError",
        }

    # If SQL query already exists (e.g. during query execution retry) and regenerate_sql is not requested, preserve it!
    if state.get("sql_query") and not state.get("regenerate_sql"):
        return {
            "sql_query": state["sql_query"],
            "database_schema": authorized_schema,
        }

    try:
        sql = generate_sql(
            user_question=state["user_question"],
            analysis_plan=state["analysis_plan"],
            database_schema=authorized_schema,
            **({"validation_feedback": state["validation_feedback"]} if state.get("validation_feedback") else {}),
        )
        record_audit_event(
            action="SQL_GENERATED",
            details=f"Synthesized SQL query ({len(sql)} chars) adhering to approved schema rules",
            user_agent="Text-to-SQL Engine",
            entity_type="QUERY",
            entity_name="sql_query",
        )
        return {
            "sql_query": sql,
            "database_schema": authorized_schema,
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

    # Strict AST table boundary check against selected_tables
    selected_tables = state.get("selected_tables", [])
    if selected_tables:
        is_auth, unauth = enforce_sql_table_boundaries(state["sql_query"], selected_tables)
        if not is_auth:
            err_msg = f"SQL validation failed: Query references unauthorized/unselected table(s): {', '.join(sorted(unauth))}. Allowed tables: {', '.join(sorted(selected_tables))}."
            record_audit_event(
                action="SQL_VALIDATED",
                details=err_msg[:120],
                user_agent="SQL Validator",
                status="FAILED",
                entity_type="QUERY",
                entity_name="sql_query",
            )
            return {
                "error": err_msg,
                "failed_node": "validate_sql",
                "exception_type": "UnauthorizedTableAccessError",
            }

    authorized_schema = _resolve_authorized_clinical_schema(state)

    is_valid, message = validate_sql(
        state["sql_query"],
        approved_schema=authorized_schema,
        analysis_plan=state.get("analysis_plan"),
        clinical_question_plan=state.get("clinical_question_plan"),
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
            "validation_feedback": f"SQL validation failed: {message}",
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
        "error": "",
        "database_schema": authorized_schema,
    }


# ============================================================
# 9. EXECUTE SQL
# ============================================================

def execute_sql_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    selected_tables = state.get("selected_tables", [])
    if selected_tables:
        is_auth, unauth = enforce_sql_table_boundaries(state["sql_query"], selected_tables)
        if not is_auth:
            return {
                "error": f"Query execution stopped: Unauthorized table access attempt for: {', '.join(sorted(unauth))}",
                "failed_node": "execute_sql",
                "exception_type": "UnauthorizedTableAccessError",
            }

    context = _cache_context(state)
    cached, cache_status = _result_cache.get(context)
    record_audit_event(action="CACHE_LOOKUP", details=cache_status, status="INFO")
    if cached is not None:
        check = validate_results(cached.get("rows"), result_contract(state["sql_query"]))
        if check["valid"]:
            return {"query_result": check["rows"], "cache_status": "hit", "error": ""}
        _result_cache.invalidate(context)

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
            "cache_status": cache_status,
            "error": "",
        }
    except Exception as exc:
        # Let the common wrapper classify database error codes without publishing
        # SQL, credentials or clinical values in logs or API notifications.
        raise exc


# ============================================================
# 10. VALIDATE RESULTS
# ============================================================

def validate_results_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    contract = result_contract(state.get("sql_query", "")) if state.get("sql_query") else {}
    validation = validate_results(state.get("query_result", []), contract)
    attempts = [*state.get("validation_attempts", []), {"attempt": len(state.get("validation_attempts", [])) + 1,
        "valid": validation["valid"], "code": validation["code"], "correction": "Lossless transport normalization only"}]
    record_audit_event(action="RESULT_VALIDATED", details=validation["code"],
        status="SUCCESS" if validation["valid"] else "FAILED", entity_type="RESULTS")
    if not validation["valid"]:
        return {"result_validation": validation, "validation_attempts": attempts,
                "error": validation["message"], "failed_node": "validate_results", "exception_type": "ResultValidationError"}
    evidence = build_insight_evidence(validation["rows"])
    if state.get("sql_query"):
        evidence["sql_query"] = state["sql_query"]
    return {"result_validation": validation, "query_result": validation["rows"], "validation_attempts": attempts,
            "insight_evidence": evidence, "eda_findings": {}, "error": "",
            "cache_status": _cache_result(state, validation["rows"])}


def _cache_result(state, rows):
    if state.get("cache_status") == "hit":
        return "hit"
    status = _result_cache.put(_cache_context(state), {"rows": rows})
    record_audit_event(action="CACHE_POPULATION", details=status, status="INFO")
    return status


def correct_results_node(state):
    # Only regenerate a query with a structural output mismatch. Never rewrite rows,
    # change clinical assumptions, or try to cure source-integrity failures.
    return {"sql_query": None, "query_result": [], "result_validation": {}, "insight_evidence": {},
        "eda_findings": {}, "insight": "", "chart_spec": None, "chart_validation": {}, "cache_status": "miss", "error": "",
        "failed_node": None, "regenerate_sql": True,
        "result_retry_count": state.get("result_retry_count", 0)+1,
        "validation_feedback": "The output columns did not match the SELECT projection. Use explicit unique aliases and retain the approved objective."}


# ============================================================
# 11. GENERATE INSIGHT
# ============================================================

def generate_insight_node(state: ClinicalAnalyticsState):

    if state.get("error"):
        return {}

    if not state.get("result_validation", {}).get("valid"):
        raise ValueError("Validated results are required")

    insight = generate_insight(
        user_question=state["user_question"],
        query_results=state["query_result"],
        insight_evidence=state.get(
            "insight_evidence",
            {},
        ),
        clinical_plan=state.get("clinical_question_plan"),
        analysis_plan=state.get("analysis_plan"),
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

        validation_feedback = validation["message"]

        if retry_count >= 2:
            return {
                "insight_validation": validation,
                "validation_feedback": validation_feedback,
                "error": (
                    "Insight validation failed after "
                    "maximum regeneration attempts: "
                    f"{validation_feedback}"
                ),
                "failed_node": "validate_insight",
                "exception_type": "InsightValidationError",
            }

        return {
            "insight_validation": validation,
            "validation_feedback": validation_feedback,
            "error": (
                "Insight validation failed: "
                f"{validation_feedback}"
            ),
            "failed_node": "validate_insight",
            "exception_type": "InsightValidationError",
        }

    return {
        "insight_validation": validation,
        "validation_feedback": "",
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

    validation_message = (
        state.get("validation_feedback")
        or state.get("insight_validation", {}).get("message")
        or state.get("error", "Insight validation failed.")
    )

    try:
        corrected_insight = regenerate_insight(
            user_question=state["user_question"],
            query_results=state["query_result"],
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
        if state.get("result_validation", {}).get("code") == "RESULT_SCHEMA" and state.get("result_retry_count", 0) < retry_limit("RESULT_MAX_RETRIES"):
            return "correct_results"
        return END
    if not state.get("result_validation", {}).get("valid"):
        return END
    return "generate_insight"


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

    if not result_validation.get("valid") or not validated_rows:
        raise ValueError("No verified result rows available for chart generation")
    from app.visualization.validation import validate_chart
    clinical_plan = state.get("clinical_question_plan") or {}
    chart_spec = create_chart_spec(results=validated_rows, target_metric=clinical_plan.get("metric"), question=state.get("user_question"))
    validate_chart(chart_spec, validated_rows)
    return {"chart_spec": chart_spec, "chart_validation": {"valid": True}, "error": ""}


# ============================================================
# 17. BUILD LANGGRAPH
# ============================================================

def build_graph(on_stage=None):

    from app.workflow.runtime import stage_wrapper

    workflow = StateGraph(
        ClinicalAnalyticsState
    )

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    workflow.add_node("validate_table_selection", stage_wrapper("validate_table_selection", validate_table_selection_node, on_stage))

    workflow.add_node("load_schema", stage_wrapper("load_schema", load_schema, on_stage))

    workflow.add_node("analyze_question", stage_wrapper("analyze_question", analyze_question, on_stage))

    workflow.add_node("human_approval", stage_wrapper("human_approval", human_approval_node, on_stage))

    workflow.add_node("regenerate_analysis_plan", stage_wrapper("regenerate_analysis_plan", regenerate_analysis_plan, on_stage))

    workflow.add_node("generate_sql", stage_wrapper("generate_sql", generate_sql_node, on_stage))

    workflow.add_node("validate_sql", stage_wrapper("validate_sql", validate_sql_node, on_stage))

    workflow.add_node("execute_sql", stage_wrapper("execute_sql", execute_sql_node, on_stage))

    workflow.add_node("validate_results", stage_wrapper("validate_results", validate_results_node, on_stage))

    workflow.add_node("generate_insight", stage_wrapper("generate_insight", generate_insight_node, on_stage))

    workflow.add_node("validate_insight", stage_wrapper("validate_insight", validate_insight_node, on_stage))

    workflow.add_node("regenerate_insight", stage_wrapper("regenerate_insight", regenerate_insight_node, on_stage))

    workflow.add_node("generate_chart", stage_wrapper("generate_chart", generate_chart_node, on_stage))

    workflow.add_node("correct_results", stage_wrapper("correct_results", correct_results_node, on_stage))
    workflow.add_edge("correct_results", "generate_sql")
    workflow.add_node("preflight_table_selection", stage_wrapper("preflight_table_selection", validate_table_selection_node, on_stage))

    # --------------------------------------------------------
    # START & QUESTION ANALYSIS
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        START,
        lambda s: s.get("entry_stage", "preflight_table_selection")
    )

    workflow.add_conditional_edges("preflight_table_selection", lambda s: END if s.get("error") else "load_schema")

    workflow.add_conditional_edges("load_schema", lambda s: END if s.get("error") else "analyze_question")

    # --------------------------------------------------------
    # HUMAN REVIEW
    # --------------------------------------------------------

    workflow.add_conditional_edges("analyze_question", lambda s: END if s.get("error") else "human_approval")

    # --------------------------------------------------------
    # HUMAN APPROVAL ROUTING
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "human_approval",
        approval_router,
        {
            "validate_table_selection": "validate_table_selection",
            "regenerate_analysis_plan": "regenerate_analysis_plan",
            END: END,
        },
    )

    # --------------------------------------------------------
    # EXECUTION BOUNDARY: TABLE SELECTION VALIDATION
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "validate_table_selection",
        table_selection_router,
        {
            "generate_sql": "generate_sql",
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

    workflow.add_conditional_edges(
        "validate_results",
        validate_results_router,
        {
            "generate_insight": "generate_insight",
            "correct_results": "correct_results",
            END: END,
        },
    )

    # --------------------------------------------------------
    # INSIGHT VALIDATION & VISUALIZATION
    # --------------------------------------------------------

    workflow.add_conditional_edges("generate_insight", lambda s: END if s.get("error") else "validate_insight")

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
