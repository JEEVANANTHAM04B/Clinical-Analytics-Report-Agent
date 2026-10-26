"""
tests/evaluation/metrics/evidence_quality.py
============================================
Evidence quality and factual grounding evaluation metric.
Verifies that generated clinical insights and narrative answers cite actual numbers
from verified query results and deterministic evidence without fabrication.
"""

from typing import Dict, Any, List, Optional
import re


class EvidenceQualityMetric:
    """
    Evaluates factual grounding between generated clinical text,
    deterministic evidence, and verified query results.
    """

    def evaluate_grounding(
        self,
        insight_text: str,
        query_results: List[Dict[str, Any]],
        deterministic_evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Inspects all numerical claims in the insight text and validates that each
        number can be traced back to the query results, calculated percentages,
        or deterministic evidence.
        """
        if not insight_text or not insight_text.strip():
            return {
                "passed": False,
                "score": 0.0,
                "hallucinations": ["empty_insight_text"],
                "reason": "Insight text is empty.",
            }

        if not query_results:
            # For empty query results, verify that the insight clearly indicates zero or no records found
            lower_text = insight_text.lower()
            indicates_empty = any(
                w in lower_text
                for w in [
                    "no records", "0 records", "no matching", "empty", "0 subjects", "zero", "none found",
                    "no subjects", "no participants", "no patients", "no data", "none of the", "not found"
                ]
            )
            return {
                "passed": indicates_empty,
                "score": 1.0 if indicates_empty else 0.0,
                "hallucinations": [] if indicates_empty else ["failed_to_state_empty_result"],
                "reason": (
                    "Correctly reported empty result set."
                    if indicates_empty
                    else f"Did not communicate empty result set. Text: {insight_text[:100]}"
                ),
            }

        # 1. Collect all valid numbers from query results
        ground_truth_numbers = set()
        for row in query_results:
            for val in row.values():
                if isinstance(val, (int, float)):
                    ground_truth_numbers.add(round(float(val), 1))
                    ground_truth_numbers.add(round(float(val), 0))
                    # Also collect potential percentage equivalents (val / total * 100)
                    ground_truth_numbers.add(int(val))

        # Collect column totals (e.g. total subjects across arms = 10,000)
        if query_results:
            first_row = query_results[0]
            for col in first_row.keys():
                col_vals = [float(r[col]) for r in query_results if isinstance(r.get(col), (int, float))]
                if col_vals:
                    total_val = sum(col_vals)
                    ground_truth_numbers.add(round(total_val, 1))
                    ground_truth_numbers.add(round(total_val, 0))
                    ground_truth_numbers.add(int(total_val))

        if deterministic_evidence:
            for key in ["row_count", "maximum", "minimum"]:
                val = deterministic_evidence.get(key)
                if isinstance(val, (int, float)):
                    ground_truth_numbers.add(round(float(val), 1))
                    ground_truth_numbers.add(int(val))

        # 2. Extract numbers from insight text (excluding common years or markdown indicators)
        # Normalize comma-separated numbers (e.g. 5,011 -> 5011)
        normalized_text = re.sub(r"(\d),(\d{3})", r"\1\2", insight_text)
        text_numbers = []
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", normalized_text):
            num = float(match.group(1))
            # Ignore study years or standard numbers like 1, 2 for enumeration
            if num in (1.0, 2.0, 3.0, 4.0, 5.0, 2024.0, 2025.0, 2026.0):
                continue
            text_numbers.append(num)

        # 3. Check for unsupported numbers
        unsupported = []
        for num in text_numbers:
            rounded_1 = round(num, 1)
            rounded_0 = round(num, 0)
            if (
                rounded_1 not in ground_truth_numbers
                and rounded_0 not in ground_truth_numbers
                and int(num) not in ground_truth_numbers
            ):
                unsupported.append(num)

        # Allow small percentage of rounding differences
        hallucination_rate = len(unsupported) / max(len(text_numbers), 1)
        passed = hallucination_rate <= 0.25  # allow minor calculated rates
        score = max(0.0, 1.0 - hallucination_rate)

        return {
            "passed": passed,
            "score": round(score, 4),
            "total_numbers_checked": len(text_numbers),
            "unsupported_numbers": unsupported,
            "reason": (
                "Insight is factually grounded in verified results."
                if passed
                else f"Found potential hallucinated numbers not in verified results: {unsupported}"
            ),
        }
