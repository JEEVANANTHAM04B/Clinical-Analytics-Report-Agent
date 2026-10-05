import sys
from pprint import pprint

from app.workflow.graph import clinical_analytics_graph

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    initial_state = {
        "user_question": "What is the average length of stay by diagnosis?"
    }

    result = clinical_analytics_graph.invoke(initial_state)

    print("\n=== LANGGRAPH RESULT ===\n")

    print("=== ANALYSIS PLAN ===")
    print(result.get("analysis_plan", ""))

    print("\n=== SQL QUERY ===")
    print(result.get("sql_query", ""))

    print("\n=== QUERY RESULT ===")
    pprint(result.get("query_result", []))

    print("\n=== RESULT VALIDATION ===")
    pprint(result.get("result_validation", {}))

    print("\n=== RAG CONTEXT ===")
    print(result.get("rag_context", ""))

    print("\n=== FINAL INSIGHT ===")
    print(result.get("insight", ""))

    print("\n=== CHART SPEC ===")
    pprint(result.get("chart_spec", {}))

    print("\n=== CHART FIGURE ===")
    print(
        "Plotly figure generated:",
        result.get("chart_figure") is not None
    )

    print("\n=== ERROR ===")
    print(result.get("error", ""))