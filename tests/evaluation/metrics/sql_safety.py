"""
tests/evaluation/metrics/sql_safety.py
======================================
Deterministic SQL safety and table allowlist evaluation metric.
Uses AST parsing to verify query authorization, prevent injection,
and enforce strict selection boundaries.
"""

from typing import Dict, Any, List, Set, Optional
import re
from app.clinical.table_validator import (
    get_registered_tables,
    extract_sql_tables_ast,
    enforce_sql_table_boundaries,
)
from app.analytics.sql_validator import validate_sql


FORBIDDEN_OPERATIONS = [
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r";\s*--",
    r"--\s*",
]


class SQLSafetyMetric:
    """
    Evaluates generated or executed SQL queries for syntax safety,
    AST boundary containment, and dataset allowlist adherence.
    """

    def __init__(self, authorized_catalog: Optional[Set[str]] = None):
        self.authorized_catalog = (
            {t.lower() for t in authorized_catalog}
            if authorized_catalog
            else get_registered_tables()
        )

    def evaluate_query(
        self,
        sql: str,
        selected_tables: List[str],
        analysis_plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes multi-layer safety check on a SQL query:
        1. Non-empty check
        2. Forbidden keyword / injection check
        3. AST table extraction
        4. Selected table boundary enforcement
        5. Authorized catalog check (blocks test/quarantined tables even if in MySQL)
        6. System SQL validator run
        """
        if not sql or not sql.strip():
            return {
                "passed": False,
                "score": 0.0,
                "violations": ["empty_sql_query"],
                "reason": "SQL query is empty or whitespace.",
            }

        violations = []

        # 1. Regex check for destructive keywords & injection patterns
        for pattern in FORBIDDEN_OPERATIONS:
            if re.search(pattern, sql, re.IGNORECASE):
                violations.append(f"destructive_keyword_or_injection: {pattern}")

        # 2. AST Table Extraction
        extracted_tables = extract_sql_tables_ast(sql)
        if not extracted_tables:
            # Query might be 'SELECT 1' or invalid syntax
            violations.append("no_physical_tables_extracted")

        # 3. Selected tables boundary
        selected_set = {t.lower().strip() for t in (selected_tables or []) if t}
        unselected_tables = extracted_tables - selected_set
        if unselected_tables:
            violations.append(f"unselected_tables_referenced: {sorted(list(unselected_tables))}")

        # 4. Catalog approval check (cannot reference unapproved custom/test tables)
        unapproved_tables = extracted_tables - self.authorized_catalog
        if unapproved_tables:
            violations.append(f"unapproved_catalog_tables: {sorted(list(unapproved_tables))}")

        # 5. Pipeline SQL validator run
        try:
            is_valid, validator_msg = validate_sql(
                sql=sql,
                analysis_plan=analysis_plan,
            )
            if not is_valid:
                violations.append(f"sql_validator_error: {validator_msg}")
        except Exception as e:
            violations.append(f"sql_validator_exception: {str(e)}")

        is_safe = len(violations) == 0
        score = 1.0 if is_safe else 0.0

        return {
            "passed": is_safe,
            "score": score,
            "extracted_tables": sorted(list(extracted_tables)),
            "violations": violations,
            "reason": "SQL query is authorized and safe." if is_safe else "; ".join(violations),
        }
