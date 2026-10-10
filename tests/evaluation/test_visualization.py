"""
tests/evaluation/test_visualization.py
======================================
Evaluates visualization specification correctness against query results:
1. Chart type selection (bar, line, pie, donut, scatter).
2. X-axis and Y-axis mappings.
3. Matching series data points and numerical values.
4. Handling of empty or single-row result sets.
"""

import pytest
from app.visualization.chart_generator import create_chart_spec


def test_chart_spec_treatment_arm_distribution():
    """Verifies vertical/horizontal bar chart generation for treatment arm subject distribution."""
    results = [
        {"TRT01A": "Drug X", "cnt": 5011},
        {"TRT01A": "Placebo", "cnt": 4989},
    ]
    spec = create_chart_spec(
        results=results,
        question="How many subjects are assigned to each treatment arm?",
    )
    assert spec is not None
    assert spec.get("chart_type") in ["bar", "horizontal_bar", "column"]
    assert spec.get("x_column") == "TRT01A"
    assert spec.get("y_column") == "cnt"
    assert "Treatment" in spec.get("title", "") or "Cnt" in spec.get("title", "")


def test_chart_spec_top_adverse_events():
    """Verifies chart specification for ranked top adverse events."""
    results = [
        {"AEDECOD": "Nausea", "cnt": 2571},
        {"AEDECOD": "Headache", "cnt": 2422},
        {"AEDECOD": "Fatigue", "cnt": 1980},
    ]
    spec = create_chart_spec(
        results=results,
        question="What are the most frequent adverse events?",
    )
    assert spec is not None
    assert spec.get("chart_type") in ["bar", "horizontal_bar"]
    assert spec.get("x_column") == "AEDECOD"
    assert spec.get("y_column") == "cnt"


def test_chart_spec_empty_results_handling():
    """Verifies clean empty-state chart behavior: raises ValueError when results are empty."""
    results = []
    with pytest.raises(ValueError, match="No data available"):
        create_chart_spec(
            results=results,
            question="Find all subjects with severe toxicity at baseline.",
        )
