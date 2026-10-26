"""
tests/test_clinical_langgraph.py
================================
Comprehensive test suite verifying the migration of the LangGraph workflow
from legacy EHR to the CDISC clinical-trial dataset model.

Tests verify:
1. Preservation of exact LangGraph architecture (nodes, edges, routers, state).
2. Processing of the 9 canonical clinical questions through the workflow.
3. Proper generation and passage of ClinicalQuestionPlan through workflow state.
4. Correct CDISC datasets, columns, and relationships selected for all 9 queries.
5. SQL generation via SQL Generator and validation via SQL Validator.
6. Execution against active database (clinical_trial_analytics_db).
7. Flow of results through result validator, insight evidence, and chart spec generation.
8. Human-in-the-loop approval and plan regeneration logic.
9. Backward compatibility fallback for legacy EHR questions.
10. Strict protection against EHR table contamination in clinical queries.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
from unittest.mock import patch
from app.workflow.graph import (
    build_graph,
    clinical_analytics_graph,
    _is_clinical_context,
    _deterministic_analysis_plan,
    _sanitize_clinical_plan,
    _preserve_plan_requirements,
    _enforce_logical_consistency,
    regenerate_analysis_plan,
    format_clinical_analysis_plan,
    analyze_question,
    validate_results_router,
)
from app.workflow.state import ClinicalAnalyticsState
from app.clinical import build_clinical_question_plan, registry as clinical_registry
from app.database.schema_service import get_database_schema


@pytest.fixture(scope="module")
def active_schema():
    return get_database_schema()


# =============================================================================
# 1. GRAPH TOPOLOGY & NODE PRESERVATION TESTS
# =============================================================================

def test_langgraph_nodes_preserved():
    """Verify that the active LangGraph workflow nodes are registered."""
    graph = build_graph()
    expected_nodes = {
        "load_schema",
        "analyze_question",
        "human_approval",
        "regenerate_analysis_plan",
        "generate_sql",
        "validate_sql",
        "execute_sql",
        "validate_results",
        "generate_insight",
        "validate_insight",
        "regenerate_insight",
        "generate_chart",
    }
    # Check nodes in compiled graph or StateGraph
    graph_nodes = set(graph.nodes.keys())
    for node in expected_nodes:
        assert node in graph_nodes, f"Expected node '{node}' not found in LangGraph"
    assert "retrieve_rag" not in graph_nodes


def test_validated_results_route_to_insights_without_generic_eda():
    assert validate_results_router({"result_validation": {"valid": True}}) == "generate_insight"
    assert validate_results_router({}) == "__end__"


def test_schema_context_detection(active_schema):
    """Verify detection of CDISC clinical trial context vs legacy EHR context."""
    assert _is_clinical_context(active_schema) is True
    assert _is_clinical_context({"tables": {"dm": [], "ae": []}}) is True
    assert _is_clinical_context({"tables": {"encounters": [], "conditions": []}}) is False
    assert _is_clinical_context(None) is True


# =============================================================================
# 2. CANONICAL CLINICAL TRIAL QUESTIONS (9 TESTS)
# =============================================================================

CANONICAL_QUESTIONS = [
    (
        "How many subjects are enrolled?",
        {"dm"},
        {"USUBJID"},
        "TOTAL_SUBJECTS",
    ),
    (
        "What is the average age of subjects?",
        {"dm"},
        {"AGE"},
        "AVERAGE_AGE",
    ),
    (
        "How many adverse events occurred?",
        {"ae"},
        {"USUBJID"},
        "ADVERSE_EVENT_COUNT",
    ),
    (
        "How many serious adverse events occurred?",
        {"ae"},
        {"AESER"},
        "SERIOUS_AE_COUNT",
    ),
    (
        "What is the adverse event rate by treatment arm?",
        {"adsl", "adae"},
        {"USUBJID", "TRT01A"},
        "AE_RATE_BY_TREATMENT",
    ),
    (
        "What is the lab change from baseline to Week 8?",
        {"adlb"},
        {"CHG", "AVISIT"},
        "LAB_CHANGE_FROM_BASELINE",
    ),
    (
        "What is the vital sign change from baseline?",
        {"advs"},
        {"CHG", "AVISIT"},
        "VITAL_SIGN_CHANGE_FROM_BASELINE",
    ),
    (
        "What is the efficacy response rate by treatment?",
        {"adresp"},
        {"RESPFL", "TRT01A"},
        "EFFICACY_RESPONSE_RATE",
    ),
    (
        "Which site has the highest enrollment?",
        {"sites", "dm"},
        {"SITEID", "USUBJID"},
        "ENROLLMENT_BY_SITE",
    ),
]


@pytest.mark.parametrize("question,expected_datasets,expected_cols,expected_kpi", CANONICAL_QUESTIONS)
def test_canonical_questions_deterministic_plan(question, expected_datasets, expected_cols, expected_kpi, active_schema):
    """Verify deterministic clinical question plan generation and formatting for all 9 canonical questions."""
    plan_obj = build_clinical_question_plan(question)
    assert plan_obj.is_supported is True
    assert plan_obj.matched_kpi_id == expected_kpi
    assert expected_datasets.issubset(set(plan_obj.datasets))

    plan_text = _deterministic_analysis_plan(question, active_schema)
    assert plan_text is not None
    assert "### Clinical Analytics Analysis Plan" in plan_text
    assert "#### 1. Relevant Tables and Columns" in plan_text
    assert "#### 2. Join Conditions" in plan_text
    assert "#### 3. Derived Calculations" in plan_text
    assert "#### 4. Aggregations & Grouping" in plan_text
    assert "#### 5. Filtering" in plan_text

    # Verify no legacy EHR tables in plan
    for ehr_table in ["encounters", "conditions", "patients", "medications", "procedures"]:
        assert f"`{ehr_table}`" not in plan_text.lower()


def test_age_distribution_and_mean_plan_is_specific_and_executable(active_schema):
    question = "What is the age distribution of subjects across treatment groups, and what is the mean age in each group?"
    plan = build_clinical_question_plan(question)
    assert plan.is_supported
    assert plan.datasets == ["adsl"]
    assert plan.dimensions == ["TRT01A"]
    assert "AVG(adsl.AGE)" in plan.calculation
    assert "AGE BETWEEN 40 AND 59" in plan.calculation
    assert "median" not in plan.calculation.lower()

    from app.analytics.sql_validator import validate_sql
    valid, reason = validate_sql(plan.suggested_sql, analysis_plan=format_clinical_analysis_plan(plan))
    assert valid, reason

    with patch("app.workflow.graph.generate_response", side_effect=AssertionError("unexpected LLM call")), \
         patch("app.workflow.graph.record_audit_event"):
        result = analyze_question({"user_question": question, "database_schema": active_schema})
    assert not result["error"]
    assert "Age Distribution And Mean" in result["analysis_plan"]
    assert "AGE < 40" in result["analysis_plan"]


@pytest.mark.parametrize("question,expected_datasets,expected_cols,expected_kpi", CANONICAL_QUESTIONS)
def test_canonical_questions_pending_approval_flow(question, expected_datasets, expected_cols, expected_kpi):
    """Verify flow through load_schema -> analyze_question -> human_approval (pending)."""
    initial_state = {
        "user_question": question,
        "approval_status": "pending",
        "approval_source": "api",
    }
    result = clinical_analytics_graph.invoke(initial_state)

    assert result.get("approval_status") == "pending"
    assert result.get("analysis_plan") is not None
    assert len(result["analysis_plan"]) > 50

    # ClinicalQuestionPlan passed through state
    clinical_plan = result.get("clinical_question_plan")
    assert clinical_plan is not None
    assert clinical_plan.get("is_supported") is True
    assert clinical_plan.get("matched_kpi_id") == expected_kpi

    # Verify expected clinical datasets are present
    plan_datasets = set(clinical_plan.get("datasets", []))
    assert expected_datasets.issubset(plan_datasets)
    assert expected_datasets.issubset(set(result.get("selected_tables", [])))

    # Verify no SQL generated yet (awaiting human approval)
    assert not result.get("sql_query")


def test_pending_plan_with_explicitly_empty_selection_remains_blocked():
    """An explicitly empty selection must not be inferred as authorization."""
    result = clinical_analytics_graph.invoke({
        "user_question": "How many subjects are enrolled?",
        "selected_tables": [],
        "approval_status": "pending",
        "approval_source": "api",
    })

    assert result.get("validation_status") == "blocked"
    assert result.get("reason") == "invalid_table_selection"
    assert result.get("analysis_plan") is None


@pytest.mark.parametrize("question,expected_datasets,expected_cols,expected_kpi", CANONICAL_QUESTIONS)
def test_canonical_questions_full_approved_execution(question, expected_datasets, expected_cols, expected_kpi, monkeypatch):
    """Verify complete end-to-end execution of approved questions through the full LangGraph pipeline."""
    from app.ai.insight_generator import _deterministic_insight_fallback
    monkeypatch.setattr(
        "app.workflow.graph.generate_insight",
        lambda user_question, query_results, insight_evidence=None, **kwargs: _deterministic_insight_fallback(
            user_question, query_results, insight_evidence or {}
        ) or "Based on verified data.",
    )
    initial_state = {
        "user_question": question,
        "selected_tables": sorted(list(expected_datasets)),
        "approval_status": "approved",
        "approval_source": "api",
    }
    result = clinical_analytics_graph.invoke(initial_state)

    # 1. State integrity
    assert result.get("error") in (None, "")

    # 2. Analysis plan
    assert result.get("analysis_plan") is not None

    # 3. SQL query generated & validated
    sql = result.get("sql_query")
    assert sql is not None and len(sql) > 10
    sql_lower = sql.lower()

    # Ensure query targets clinical datasets
    assert any(ds in sql_lower for ds in expected_datasets)

    # Ensure query NEVER contains EHR tables
    for ehr_table in ["encounters", "conditions", "patients", "medications", "procedures"]:
        assert f" {ehr_table} " not in f" {sql_lower} "

    # 4. Query execution
    rows = result.get("query_result")
    assert rows is not None
    assert len(rows) > 0, f"Expected non-empty results for question: {question}"

    # 5. Result validation & evidence
    assert result.get("result_validation", {}).get("valid") is True
    evidence = result.get("insight_evidence")
    assert evidence is not None
    assert evidence.get("row_count") == len(rows)

    # 6. Chart specification
    chart_spec = result.get("chart_spec")
    assert chart_spec is not None
    assert "chart_type" in chart_spec


# =============================================================================
# 2b. SELECTION BOUNDARY TESTS
# =============================================================================

def test_execution_boundary_blocked_on_empty_selected_tables():
    """Verify execution is blocked when selected_tables is empty upon approval."""
    question = "How many subjects are enrolled?"
    initial_state = {
        "user_question": question,
        "selected_tables": [],
        "approval_status": "approved",
        "approval_source": "api",
    }
    result = clinical_analytics_graph.invoke(initial_state)

    assert result.get("validation_status") == "blocked"
    assert result.get("reason") == "invalid_table_selection"
    assert result.get("sql_query") is None
    assert result.get("query_result") is None or len(result.get("query_result", [])) == 0


def test_execution_boundary_blocked_on_missing_required_tables():
    """Verify execution is blocked when required tables (ADAE, ADSL) are not in selected_tables."""
    question = "What is the adverse event rate by treatment arm?"
    initial_state = {
        "user_question": question,
        "selected_tables": ["adsl"],  # adae missing
        "approval_status": "approved",
        "approval_source": "api",
    }
    result = clinical_analytics_graph.invoke(initial_state)

    assert result.get("validation_status") == "blocked"
    assert result.get("reason") == "required_tables_not_selected"
    assert "adae" in result.get("missing_tables", [])
    assert result.get("sql_query") is None
    assert result.get("query_result") is None or len(result.get("query_result", [])) == 0


def test_execution_boundary_blocked_on_unknown_tables():
    """Verify execution is blocked when unknown/arbitrary tables are in selected_tables."""
    question = "How many subjects are enrolled?"
    initial_state = {
        "user_question": question,
        "selected_tables": ["unknown_custom_data"],
        "approval_status": "approved",
        "approval_source": "api",
    }
    result = clinical_analytics_graph.invoke(initial_state)

    assert result.get("validation_status") == "blocked"
    assert result.get("reason") == "invalid_table_selection"
    assert result.get("sql_query") is None
    assert result.get("query_result") is None or len(result.get("query_result", [])) == 0


def test_execution_boundary_blocked_on_unapproved_custom_datasets():
    """Verify execution is blocked when unapproved custom datasets (e.g. biomarker_results) are selected."""
    question = "Analyze biomarker results."
    initial_state = {
        "user_question": question,
        "selected_tables": ["biomarker_results"],
        "approval_status": "approved",
        "approval_source": "api",
    }
    result = clinical_analytics_graph.invoke(initial_state)

    assert result.get("validation_status") == "blocked"
    assert result.get("reason") == "invalid_table_selection"
    assert result.get("sql_query") is None
    assert result.get("query_result") is None or len(result.get("query_result", [])) == 0


# =============================================================================
# 3. HUMAN-IN-THE-LOOP APPROVAL & REGENERATION TESTS
# =============================================================================

def test_plan_regeneration_on_rejection():
    """Verify that plan rejection triggers regenerate_analysis_plan and returns pending status."""
    question = "What is the adverse event rate by treatment arm?"
    initial_state = {
        "user_question": question,
        "approval_status": "rejected",
        "approval_source": "api",
        "human_feedback": "Filter for serious adverse events only",
        "plan_version": 1,
    }
    result = clinical_analytics_graph.invoke(initial_state)

    assert result.get("approval_status") == "pending"
    assert result.get("plan_version") == 2
    assert "Filter for serious adverse events only" in result.get("feedback_history", [])
    assert result.get("analysis_plan") is not None
    # No SQL execution when regenerating
    assert not result.get("sql_query")


# =============================================================================
# 4. LEGACY EHR FALLBACK TESTS
# =============================================================================

def test_legacy_ehr_deterministic_plan_fallback():
    """Verify backward compatibility fallback for legacy EHR questions when requested."""
    ehr_schema = {
        "tables": {
            "encounters": [
                {"name": "ID", "type": "VARCHAR", "nullable": False},
                {"name": "START", "type": "DATE", "nullable": False},
                {"name": "STOP", "type": "DATE", "nullable": False},
                {"name": "ENCOUNTERCLASS", "type": "VARCHAR", "nullable": False},
            ],
            "conditions": [
                {"name": "DESCRIPTION", "type": "VARCHAR", "nullable": False},
                {"name": "ENCOUNTER", "type": "VARCHAR", "nullable": False},
            ],
        },
        "relationships": [
            {
                "parent_table": "encounters",
                "parent_column": "ID",
                "child_table": "conditions",
                "child_column": "ENCOUNTER",
            }
        ],
    }

    # EHR fallback plan 1: LOS by encounter class
    plan_class = _deterministic_analysis_plan(
        "What is the average length of stay by encounter class?",
        ehr_schema,
    )
    assert plan_class is not None
    assert "encounters.ENCOUNTERCLASS" in plan_class
    assert "DATEDIFF(encounters.STOP, encounters.START)" in plan_class

    # EHR fallback plan 2: LOS by diagnosis
    plan_diag = _deterministic_analysis_plan(
        "What is the average length of stay by diagnosis?",
        ehr_schema,
    )
    assert plan_diag is not None
    assert "conditions.DESCRIPTION" in plan_diag
    assert "encounters.ID = conditions.ENCOUNTER" in plan_diag


# =============================================================================
# 5. ANALYSIS PLAN REJECTION / REGENERATION REGRESSION TESTS
# =============================================================================

def test_join_conditions_header_not_classified_as_ehr(active_schema):
    """
    1. Clinical plan containing '#### 2. Join Conditions' must NOT be classified as EHR,
    and must not trigger EHR table/filter injections.
    """
    clinical_plan_with_header = """### Clinical Analytics Analysis Plan

#### 1. Relevant Tables and Columns
* **`adae`**:
  * `USUBJID` (VARCHAR): Unique Subject Identifier
  * `AESEV` (VARCHAR): Severity/Intensity

#### 2. Join Conditions
* None (single-table query on `adae`).

#### 3. Derived Calculations
* **Adverse Event Severity Distribution**:
  Calculate using:
  `COUNT(*) GROUP BY adae.AESEV`

#### 4. Aggregations & Grouping
* **Grouping**:
  Group results by `AESEV`.
* **Aggregation**:
  `COUNT(*) GROUP BY adae.AESEV`

#### 5. Filtering
* None.
"""
    result = _preserve_plan_requirements(
        current_plan=clinical_plan_with_header,
        revised_plan=clinical_plan_with_header,
        human_feedback="Refine the grouping",
        feedback_history=[],
        question="What is the distribution of adverse event severity?",
        database_schema=active_schema,
    )

    # Must NOT inject legacy EHR elements
    assert "encounters" not in result.lower()
    assert "conditions.description" not in result.lower()
    assert "datediff" not in result.lower()
    assert "length of stay" not in result.lower()
    assert "#### 2. Join Conditions" in result


def test_clinical_ae_severity_unstratified():
    """
    2. Clinical AE severity question:
       'What is the distribution of adverse event severity?'
       remains valid and does NOT add ADSL join.
    """
    plan = build_clinical_question_plan("What is the distribution of adverse event severity?")
    assert plan.is_supported is True
    assert plan.datasets == ["adae"]
    assert "AESEV" in plan.dimensions
    assert plan.requires_join is False
    assert "adsl" not in plan.datasets


def test_clinical_ae_severity_stratified():
    """
    3. Clinical treatment-arm severity question:
       'What is the distribution of adverse event severity across treatment arms?'
       must produce:
       ADSL + ADAE
       TRT01A + AESEV
       USUBJID join
    """
    question = "What is the distribution of adverse event severity across treatment arms?"
    plan = build_clinical_question_plan(question)
    assert plan.is_supported is True
    assert "adsl" in plan.datasets
    assert "adae" in plan.datasets
    assert "TRT01A" in plan.dimensions
    assert "AESEV" in plan.dimensions
    assert "adsl.USUBJID" in plan.required_columns
    assert "adsl.TRT01A" in plan.required_columns
    assert "adae.USUBJID" in plan.required_columns
    assert "adae.AESEV" in plan.required_columns
    assert plan.requires_join is True
    assert "adsl" in plan.join_tables
    assert "adae" in plan.join_tables
    assert "GROUP BY adsl.TRT01A, adae.AESEV" in plan.calculation


@pytest.mark.parametrize("phrasing", [
    "What is the distribution of adverse event severity across treatment arms?",
    "What is the distribution of adverse event severity by treatment arm?",
    "What is the distribution of adverse event severity by treatment group?",
    "What is the distribution of adverse event severity across treatment groups?",
    "What is the distribution of adverse event severity by arm?",
    "What is the distribution of adverse event severity by cohort?",
])
def test_clinical_ae_severity_equivalent_phrasings(phrasing):
    """
    7. Test multiple equivalent phrasings:
       - across treatment arms
       - by treatment arm
       - by treatment group
       - across treatment groups
       - by arm
       - by cohort
    """
    plan = build_clinical_question_plan(phrasing)
    assert plan.is_supported is True
    assert "adsl" in plan.datasets
    assert "adae" in plan.datasets
    assert "TRT01A" in plan.dimensions
    assert "AESEV" in plan.dimensions
    assert plan.requires_join is True


def test_regeneration_with_gemini_unavailable_incorporates_feedback(active_schema):
    """
    4 & 5. Regeneration with Gemini unavailable / 429:
    human feedback must still affect deterministic regeneration,
    and regenerated clinical plan must contain zero legacy EHR references.
    """
    question = "What is the distribution of adverse event severity across treatment arms?"
    rejection_feedback = (
        "The plan is missing treatment-arm stratification. It must use "
        "ADSL.TRT01A together with ADAE.AESEV and join ADSL to ADAE using "
        "USUBJID. Group the results by TRT01A and AESEV. Remove all legacy "
        "EHR references such as encounters, conditions, START, STOP, DATEDIFF, "
        "and length-of-stay filters because they are unrelated to this "
        "clinical-trial question."
    )
    initial_draft_plan = """### Clinical Analytics Analysis Plan

#### 1. Relevant Tables and Columns
* **`adae`**:
  * `USUBJID` (VARCHAR): Unique Subject Identifier
  * `AESEV` (VARCHAR): Severity/Intensity

#### 2. Join Conditions
* None (single-table query on `adae`).

#### 3. Derived Calculations
* **Adverse Event Severity Distribution**:
  Calculate using:
  `COUNT(*) GROUP BY adae.AESEV`

#### 4. Aggregations & Grouping
* **Grouping**:
  Group results by `AESEV`.
* **Aggregation**:
  `COUNT(*) GROUP BY adae.AESEV`

#### 5. Filtering
* None.
"""
    state: ClinicalAnalyticsState = {
        "user_question": question,
        "database_schema": active_schema,
        "analysis_plan": initial_draft_plan,
        "approval_status": "rejected",
        "approval_source": "api",
        "human_feedback": rejection_feedback,
        "feedback_history": [],
        "plan_version": 1,
    }

    # Simulate Gemini 429 / resource exhausted
    with patch("app.workflow.graph.generate_response", side_effect=RuntimeError("Resource exhausted: 429")):
        result = regenerate_analysis_plan(state)

    regen_plan = result.get("analysis_plan", "")

    # Must produce ADSL + ADAE
    assert "adsl" in regen_plan.lower()
    assert "adae" in regen_plan.lower()
    assert "trt01a" in regen_plan.lower()
    assert "aesev" in regen_plan.lower()
    assert "usubjid" in regen_plan.lower()

    # Must contain proper join
    assert "adsl.usubjid = adae.usubjid" in regen_plan.lower() or "join `adsl` and `adae`" in regen_plan.lower()

    # Grouping must include TRT01A and AESEV
    assert "trt01a" in regen_plan.lower()
    assert "aesev" in regen_plan.lower()
    assert "count(*)" in regen_plan.lower()

    # Must NOT contain legacy EHR references
    for ehr_forbidden in [
        "encounters",
        "conditions.description",
        "conditions.encounter",
        "encounters.id = conditions.encounter",
        "datediff",
        "length of stay",
        "los",
        "inpatient",
    ]:
        assert ehr_forbidden not in regen_plan.lower(), f"Forbidden EHR element '{ehr_forbidden}' found in regenerated plan!"

    # Clinical question plan in state must be updated with stratification
    cplan_state = result.get("clinical_question_plan", {})
    assert "adsl" in cplan_state.get("datasets", [])
    assert "adae" in cplan_state.get("datasets", [])
    assert "TRT01A" in cplan_state.get("dimensions", [])
    assert "AESEV" in cplan_state.get("dimensions", [])


def test_clinical_plan_sanitization():
    """Verify _sanitize_clinical_plan purges EHR contamination from clinical plans."""
    contaminated_plan = """### Clinical Analytics Analysis Plan

#### 1. Relevant Tables and Columns
* **`adsl`**:
  * `USUBJID` (VARCHAR): Unique Subject Identifier
  * `TRT01A` (VARCHAR): Treatment Arm
* **`adae`**:
  * `USUBJID` (VARCHAR): Unique Subject Identifier
  * `AESEV` (VARCHAR): Severity
* **`encounters`**:
  * `ID` (VARCHAR): ID
  * `START` (DATE): Start
* **`conditions`**:
  * `DESCRIPTION` (VARCHAR): Description

#### 2. Join Conditions
* Join `adsl` and `adae`: `adsl.USUBJID = adae.USUBJID`
* `encounters.ID = conditions.ENCOUNTER`

#### 3. Derived Calculations
* **Adverse Event Severity Distribution**:
  `COUNT(*) GROUP BY adsl.TRT01A, adae.AESEV`
* **Length of Stay**:
  `DATEDIFF(encounters.STOP, encounters.START)`

#### 4. Aggregations & Grouping
* **Grouping**:
  Group results by `TRT01A`, `AESEV`.

#### 5. Filtering
* **Length of Stay Range**:
  * Include only LOS values between 0 and 30 days:
    * `DATEDIFF(encounters.STOP, encounters.START) BETWEEN 0 AND 30`
* **Valid Encounter Dates**:
  * Exclude NULL START and STOP values:
    * `encounters.START IS NOT NULL`
"""
    clean_plan = _sanitize_clinical_plan(contaminated_plan)

    assert "encounters" not in clean_plan.lower()
    assert "conditions" not in clean_plan.lower().replace("#### 2. join conditions", "")
    assert "datediff" not in clean_plan.lower()
    assert "length of stay" not in clean_plan.lower()
    assert "adsl" in clean_plan.lower()
    assert "adae" in clean_plan.lower()
    assert "#### 2. Join Conditions" in clean_plan
