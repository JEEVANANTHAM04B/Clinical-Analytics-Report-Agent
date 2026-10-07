import json
import sys
from pathlib import Path

# Ensure unbuffered standard output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.schema_service import get_database_schema
from app.workflow.graph import (
    build_graph,
    validate_sql_node,
    validate_sql_router,
    validate_insight_node,
    regenerate_insight_node,
    insight_validation_router,
)
from app.analytics.sql_validator import validate_sql
from app.ai.insight_validator import validate_insight
from langgraph.graph import END

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "e2e_test_cases.json"


def load_test_cases():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_e2e_evaluation():
    test_cases = load_test_cases()
    schema = get_database_schema()
    graph = build_graph()

    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = 0

    category_stats = {
        "complete_workflow": {"passed": 0, "total": 0, "label": "Complete Workflow Tests"},
        "human_approval": {"passed": 0, "total": 0, "label": "Human Approval Tests"},
        "safety_path": {"passed": 0, "total": 0, "label": "Safety Path Tests"},
        "recovery": {"passed": 0, "total": 0, "label": "Recovery Tests"},
    }

    print("=" * 80)
    print("DETERMINISTIC END-TO-END CLINICAL ANALYTICS WORKFLOW EVALUATION")
    print(f"Dataset: {DATASET_PATH.name} ({total_tests} test cases)")
    print("=" * 80)

    for idx, case in enumerate(test_cases, 1):
        case_id = case["id"]
        category = case.get("category", "general")
        name = case.get("name", "")
        question = case["question"]
        initial_state = case.get("initial_state", {})
        expected_checks = case.get("expected_checks", {})

        category_stats[category]["total"] += 1

        print(f"\n--- [{idx}/{total_tests}] Test ID: {case_id} ({category}) ---")
        print(f"Test Name   : {name}")
        print(f"Question    : \"{question}\"")

        test_passed = True
        failures = []

        # -------------------------------------------------------------
        # Tests 1-5: Real LangGraph Execution
        # -------------------------------------------------------------
        if case_id in ("e2e_001", "e2e_002", "e2e_003", "e2e_004", "e2e_005"):
            # Prepare state
            run_state = {**initial_state}
            try:
                final_state = graph.invoke(run_state)
            except Exception as exc:
                final_state = {"error": f"Graph execution exception: {exc}"}

            workflow_error = final_state.get("error", "")
            analysis_plan = final_state.get("analysis_plan", "")
            approval_status = final_state.get("approval_status", "")
            sql_query = final_state.get("sql_query", "")
            query_result = final_state.get("query_result", [])
            result_val = final_state.get("result_validation", {})
            rag_context = final_state.get("rag_context", "")
            insight = final_state.get("insight", "")
            chart_spec = final_state.get("chart_spec")

            # Check error
            if expected_checks.get("expect_error", False):
                if not workflow_error:
                    failures.append("Expected a workflow error, but none occurred.")
            else:
                if workflow_error:
                    failures.append(f"Unexpected workflow error: {workflow_error}")

            # Observable state summary
            observable_state = [
                f"approval_status={approval_status}",
                f"plan_version={final_state.get('plan_version')}",
                f"has_plan={bool(analysis_plan)}",
                f"has_sql={bool(sql_query)}",
                f"result_rows={len(query_result) if isinstance(query_result, list) else 0}",
                f"has_insight={bool(insight)}",
                f"has_chart={bool(chart_spec)}",
            ]

            print(f"Final Status: {'COMPLETED' if not workflow_error else 'ERROR'}")
            print(f"Observable  : {', '.join(observable_state)}")
            print(f"Plan Snippet: {analysis_plan[:100]}..." if analysis_plan else "Plan Snippet: [NONE]")

            # E2E 1 & 4 (Complete pipeline checks)
            if expected_checks.get("expect_plan"):
                if not analysis_plan:
                    failures.append("Analysis plan was expected but is missing.")

            if expected_checks.get("expect_approval_status"):
                exp_app = expected_checks["expect_approval_status"]
                if approval_status != exp_app:
                    failures.append(f"Expected approval_status '{exp_app}', got '{approval_status}'")

            if expected_checks.get("expect_sql"):
                if not sql_query:
                    failures.append("SQL query was expected but is missing.")
                else:
                    is_valid, val_msg = validate_sql(sql_query, approved_schema=schema, analysis_plan=analysis_plan)
                    print(f"SQL Validation: {'VALID' if is_valid else 'INVALID'} ({val_msg})")
                    if not is_valid:
                        failures.append(f"SQL validation failed: {val_msg}")

            if expected_checks.get("expect_results"):
                if not query_result or not isinstance(query_result, list):
                    failures.append("Expected non-empty query results list.")
                else:
                    print(f"Result Validation: {result_val.get('message', 'Valid')} ({len(query_result)} rows)")
                    if not result_val.get("valid", True):
                        failures.append(f"Result validation rejected rows: {result_val.get('message')}")

            if expected_checks.get("expect_rag"):
                print(f"RAG Context   : {'PRESENT' if rag_context else 'MISSING'}")
                if not rag_context:
                    failures.append("RAG context was expected but is missing.")

            if expected_checks.get("expect_insight"):
                if not insight:
                    failures.append("Insight was expected but is missing.")
                else:
                    evidence_to_use = final_state.get("insight_evidence") or {}
                    val_res = validate_insight(
                        insight=insight,
                        query_results=query_result if isinstance(query_result, list) else [],
                        insight_evidence=evidence_to_use,
                    )
                    print(f"Insight Val   : {'VALID' if val_res.get('valid') else 'INVALID'} ({val_res.get('message')})")
                    if not val_res.get("valid"):
                        failures.append(f"Insight validation failed: {val_res.get('message')}")

            if expected_checks.get("expect_chart"):
                if not chart_spec or not isinstance(chart_spec, dict):
                    failures.append("Chart specification was expected but is missing.")
                else:
                    x_col = chart_spec.get("x_column")
                    y_col = chart_spec.get("y_column")
                    print(f"Chart Status  : VALID (chart_type='{chart_spec.get('chart_type')}', x='{x_col}', y='{y_col}')")
                    if query_result and isinstance(query_result, list):
                        res_cols = list(query_result[0].keys())
                        if x_col not in res_cols or y_col not in res_cols:
                            failures.append(f"Chart columns ({x_col}, {y_col}) do not exist in query result columns: {res_cols}")

            # E2E 2 & 3 (Disallow execution checks)
            if expected_checks.get("disallow_sql") and sql_query:
                failures.append(f"SQL execution was NOT allowed, but query was generated: {sql_query}")
            if expected_checks.get("disallow_results") and query_result:
                failures.append(f"Query results were NOT allowed, but found: {query_result}")
            if expected_checks.get("disallow_insight") and insight:
                failures.append("Insight was NOT allowed, but was generated.")
            if expected_checks.get("disallow_chart") and chart_spec:
                failures.append("Chart spec was NOT allowed, but was generated.")

            if expected_checks.get("expect_version_increment"):
                if final_state.get("plan_version") != 2:
                    failures.append(f"plan_version expected 2, got {final_state.get('plan_version')}")

            if expected_checks.get("expect_feedback_history"):
                for fb in expected_checks["expect_feedback_history"]:
                    if fb not in final_state.get("feedback_history", []):
                        failures.append(f"Feedback history missing item: '{fb}'")

            # E2E 5 (Empty result set checks)
            if expected_checks.get("expect_zero_rows"):
                if len(query_result) != 0:
                    failures.append(f"Expected 0 result rows, but got {len(query_result)}")
                print(f"Empty Handling: 0 rows returned, handled safely without crash.")

            if expected_checks.get("safe_chart_handling"):
                print(f"Chart Handling: {final_state.get('visualization_error', 'Chart spec None as expected for 0 rows')}")

        # -------------------------------------------------------------
        # Test 6: Invalid SQL Safety Path
        # -------------------------------------------------------------
        elif case_id == "e2e_006":
            state_invalid = {
                "sql_query": initial_state["sql_query"],
                "database_schema": schema,
                "analysis_plan": initial_state.get("analysis_plan", ""),
            }
            res_node = validate_sql_node(state_invalid)
            has_error = bool(res_node.get("error"))
            failed_node = res_node.get("failed_node")
            print(f"SQL Node Result: {res_node}")
            if not has_error or failed_node != "validate_sql":
                failures.append(f"Expected validate_sql_node to reject SQL and set failed_node='validate_sql', got {res_node}")

            state_after = {**state_invalid, **res_node}
            routed_to = validate_sql_router(state_after)
            print(f"Router Decision: {routed_to}")
            if routed_to != END:
                failures.append(f"Expected router to terminate at END, but routed to '{routed_to}'")

        # -------------------------------------------------------------
        # Test 7: Invalid Insight Recovery & Retry Limit
        # -------------------------------------------------------------
        elif case_id == "e2e_007":
            # 1. Test invalid insight detection and regeneration routing
            val_node_res = validate_insight_node(initial_state)
            print(f"Initial Val Node: {val_node_res}")
            if not val_node_res.get("error") or val_node_res.get("failed_node") != "validate_insight":
                failures.append(f"Expected validate_insight_node to fail for ungrounded numbers, got {val_node_res}")

            state_failed = {**initial_state, **val_node_res}
            route_step = insight_validation_router(state_failed)
            print(f"Router Step 1   : '{route_step}'")
            if route_step != "regenerate_insight":
                failures.append(f"Expected router to route to 'regenerate_insight', got '{route_step}'")

            # 2. Test regeneration node execution
            regen_node_res = regenerate_insight_node(state_failed)
            corrected_insight = regen_node_res.get("insight", "")
            retry_count = regen_node_res.get("insight_retry_count", 0)
            print(f"Regen Node Res  : retry_count={retry_count}, insight='{corrected_insight[:80]}...'")
            if retry_count != 1 or not corrected_insight:
                failures.append("Expected regenerate_insight_node to increment retry counter to 1 and yield an insight.")

            # Validate corrected insight passes
            state_corrected = {**initial_state, "insight": corrected_insight, "insight_retry_count": retry_count, "error": ""}
            val_corrected = validate_insight_node(state_corrected)
            route_step_2 = insight_validation_router(val_corrected)
            print(f"Router Step 2   : '{route_step_2}' (after correction)")
            if route_step_2 != "generate_chart":
                failures.append(f"Expected router to proceed to 'generate_chart' after correction, got '{route_step_2}'")

            # 3. Test retry limit termination
            state_max_retries = {
                **initial_state,
                "insight_retry_count": 2,
            }
            val_max_res = validate_insight_node(state_max_retries)
            state_limit_failed = {**state_max_retries, **val_max_res}
            route_limit = insight_validation_router(state_limit_failed)
            print(f"Retry Limit Step: '{route_limit}' (max retries reached)")
            if route_limit != "stop":
                failures.append(f"Expected router to terminate with 'stop' when retry limit is reached, got '{route_limit}'")

        # -------------------------------------------------------------
        # Overall Test Result
        # -------------------------------------------------------------
        if failures:
            test_passed = False
            failed_tests += 1
            print(f"\nErrors: {len(failures)} error(s) encountered:")
            for err in failures:
                print(f"  [ERROR] {err}")
            print("Status: FAIL")
        else:
            passed_tests += 1
            category_stats[category]["passed"] += 1
            print("\nErrors: None")
            print("Status: PASS")

    # -------------------------------------------------------------
    # Final Summary
    # -------------------------------------------------------------
    pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0.0

    print("\n" + "=" * 50)
    print("FINAL END-TO-END EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total Tests : {total_tests}")
    print(f"Passed      : {passed_tests}")
    print(f"Failed      : {failed_tests}")
    print(f"Pass Rate   : {pass_rate:.1f}%")
    print("\nDetailed Category Breakdown:")
    for cat_key, stat in category_stats.items():
        print(f"  {stat['label']:<25}: {stat['passed']}/{stat['total']} passed")
    print("=" * 50)

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_e2e_evaluation()
    sys.exit(0 if success else 1)
