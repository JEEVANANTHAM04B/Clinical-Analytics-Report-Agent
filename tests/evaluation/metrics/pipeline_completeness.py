"""
tests/evaluation/metrics/pipeline_completeness.py
=================================================
Pipeline completeness evaluation metric. Evaluates whether the LangGraph
workflow executed the expected stages and transitioned through states correctly,
including proper early termination when inputs are blocked or unapproved.
"""

from typing import Dict, Any, List, Optional


class PipelineCompletenessMetric:
    """
    Evaluates whether the clinical analytics LangGraph execution trace
    or final state demonstrates complete and valid stage execution.
    """

    def evaluate_state(
        self,
        final_state: Dict[str, Any],
        expected_outcome: str = "authorized",
        category: str = "STRUCTURED",
    ) -> Dict[str, Any]:
        """
        Validates the state attributes against the expected outcome:
        - For 'authorized': question parsed, plan generated, SQL produced & validated,
          query executed, results returned, and visualization / evidence present.
        - For 'blocked': validation_status is 'blocked', reason provided,
          no SQL executed, no hallucinated charts or results.
        - For 'CLINICAL_KNOWLEDGE_RAG': RAG context retrieved and insight generated.
        """
        issues = []
        stages_completed = []

        val_status = final_state.get("validation_status")

        if expected_outcome == "blocked":
            if val_status != "blocked":
                issues.append(f"Expected validation_status='blocked', got '{val_status}'")
            else:
                stages_completed.append("table_boundary_guard_blocked")

            # Crucial security guarantee: NO SQL executed, NO results produced
            if final_state.get("sql_query"):
                issues.append("Security failure: SQL query was generated for a blocked request")
            if final_state.get("results") or final_state.get("query_result"):
                issues.append("Security failure: Query results were produced for a blocked request")
            if final_state.get("chart_spec"):
                issues.append("Security failure: Chart spec was generated for a blocked request")

            passed = len(issues) == 0
            return {
                "passed": passed,
                "score": 1.0 if passed else 0.0,
                "expected_outcome": "blocked",
                "stages_completed": stages_completed,
                "issues": issues,
                "reason": "Request successfully and safely blocked before analytical execution." if passed else "; ".join(issues),
            }

        # Expected outcome is 'authorized'
        if val_status == "blocked":
            issues.append(f"Request was unexpectedly blocked: {final_state.get('validation_message') or final_state.get('reason')}")

        is_rag_only = category == "CLINICAL_KNOWLEDGE_RAG"

        if final_state.get("analysis_plan"):
            stages_completed.append("analysis_plan")
        elif not is_rag_only:
            issues.append("Missing analysis_plan")

        if not is_rag_only:
            if final_state.get("sql_query"):
                stages_completed.append("sql_query")
            else:
                issues.append("Missing sql_query")

            executed_results = (
                final_state.get("results")
                if final_state.get("results") is not None
                else final_state.get("query_result")
            )
            if executed_results is not None:
                stages_completed.append("results_validated")
            else:
                issues.append("Missing results/query execution")

            if final_state.get("chart_spec"):
                stages_completed.append("chart_spec")

        if final_state.get("rag_context"):
            stages_completed.append("rag_retrieved")
        elif is_rag_only:
            issues.append("Missing rag_context")

        if final_state.get("insight"):
            stages_completed.append("insight_generated")
        elif is_rag_only:
            issues.append("Missing insight")

        passed = len(issues) == 0
        total_expected = 4
        score = min(1.0, len(stages_completed) / total_expected)

        return {
            "passed": passed,
            "score": round(score, 4),
            "expected_outcome": "authorized",
            "stages_completed": stages_completed,
            "issues": issues,
            "reason": (
                f"Pipeline completed stages: {', '.join(stages_completed)}"
                if passed
                else f"Incomplete pipeline: {'; '.join(issues)}"
            ),
        }
