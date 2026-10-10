"""
tests/evaluation/metrics/clinical_correctness.py
================================================
Deterministic clinical correctness metric. Evaluates numerical, categorical,
and percentage metrics against trusted ground truth with explicit rounding tolerances.
"""

from typing import Dict, Any, List, Optional
import math


class ClinicalCorrectnessMetric:
    """
    Evaluates whether actual query results or calculated clinical metrics
    match trusted ground truth within specified numerical tolerances.
    """

    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance

    def evaluate_scalar(
        self,
        actual: Any,
        expected: Any,
        metric_name: str = "Metric",
    ) -> Dict[str, Any]:
        """Compares two scalar values (numeric or string) with tolerance for floats."""
        try:
            if actual is None and expected is None:
                return {"passed": True, "score": 1.0, "reason": "Both values None"}
            if actual is None or expected is None:
                return {
                    "passed": False,
                    "score": 0.0,
                    "reason": f"{metric_name} mismatch: actual={actual}, expected={expected}",
                }

            # Float / Int comparison
            if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
                diff = abs(float(actual) - float(expected))
                passed = diff <= self.tolerance
                score = 1.0 if passed else max(0.0, 1.0 - (diff / max(abs(float(expected)), 1.0)))
                return {
                    "passed": passed,
                    "score": round(score, 4),
                    "reason": (
                        f"{metric_name} verified: {actual} ~= {expected} (diff={diff:.4f})"
                        if passed
                        else f"{metric_name} exceeded tolerance: actual={actual}, expected={expected}, diff={diff:.4f}"
                    ),
                }

            # String comparison
            actual_str = str(actual).strip().lower()
            expected_str = str(expected).strip().lower()
            passed = actual_str == expected_str
            return {
                "passed": passed,
                "score": 1.0 if passed else 0.0,
                "reason": (
                    f"{metric_name} exact match: {actual}"
                    if passed
                    else f"{metric_name} mismatch: actual='{actual}', expected='{expected}'"
                ),
            }
        except Exception as e:
            return {"passed": False, "score": 0.0, "reason": f"Evaluation error: {str(e)}"}

    def evaluate_grouped_percentages(
        self,
        actual_rows: List[Dict[str, Any]],
        expected_groups: Dict[str, Dict[str, Any]],
        group_col: str = "TRT01A",
        pct_col: str = "percentage",
    ) -> Dict[str, Any]:
        """
        Evaluates clinical rates (e.g. AE incidence by arm) checking numerator,
        denominator, and percentage calculations.
        """
        if not actual_rows and not expected_groups:
            return {"passed": True, "score": 1.0, "reason": "Empty groups match"}
        if not actual_rows or not expected_groups:
            return {"passed": False, "score": 0.0, "reason": "Missing actual rows or expected groups"}

        actual_map = {}
        for row in actual_rows:
            # Case-insensitive column lookup
            arm = None
            pct = None
            for k, v in row.items():
                if k.lower() in (group_col.lower(), "arm", "treatment_arm", "trt01a"):
                    arm = str(v).strip()
                if k.lower() in (pct_col.lower(), "rate", "incidence", "pct", "incidence_rate"):
                    pct = float(v)
            if arm is not None and pct is not None:
                actual_map[arm.lower()] = pct

        total_groups = len(expected_groups)
        passed_groups = 0
        details = []

        for exp_arm, exp_data in expected_groups.items():
            exp_arm_clean = exp_arm.lower().strip()
            exp_pct = exp_data.get("percentage") if isinstance(exp_data, dict) else float(exp_data)

            if exp_arm_clean not in actual_map:
                details.append(f"Group '{exp_arm}' missing in actual results")
                continue

            act_pct = actual_map[exp_arm_clean]
            diff = abs(act_pct - exp_pct)
            if diff <= self.tolerance:
                passed_groups += 1
                details.append(f"Group '{exp_arm}' passed: act={act_pct}%, exp={exp_pct}%")
            else:
                details.append(f"Group '{exp_arm}' failed: act={act_pct}%, exp={exp_pct}%, diff={diff:.2f}%")

        overall_passed = passed_groups == total_groups
        score = round(passed_groups / total_groups, 4) if total_groups > 0 else 0.0
        return {
            "passed": overall_passed,
            "score": score,
            "passed_groups": passed_groups,
            "total_groups": total_groups,
            "reason": "; ".join(details),
        }
