"""
app/clinical/table_validator.py
===============================
Implements selection-aware table validation for the clinical analytics platform.
Treats user table selection as a strict data access boundary:
  1. Identifies minimum required datasets for a clinical question.
  2. Validates selected tables against registered database tables (allowlist).
  3. Detects missing tables and blocks unauthorized or incomplete pipeline execution.
  4. Enforces table boundaries at SQL execution using AST-based parsing.
"""

from typing import Set, List, Dict, Tuple, Optional, Any
import re
import sqlglot
from sqlglot import exp

from app.clinical.question_mapping import build_clinical_question_plan
from app.clinical import registry as clinical_registry
from app.database.schema_service import get_database_schema


def get_registered_tables() -> Set[str]:
    """
    Returns the set of registered lowercase database table names in the active clinical database.
    Only approved clinical datasets are included.
    """
    try:
        from app.clinical.dataset_registry_service import get_approved_clinical_tables
        approved = get_approved_clinical_tables()
        if approved:
            return set(approved)
    except Exception:
        pass

    try:
        db_schema = get_database_schema(approved_only=True)
        if db_schema and "tables" in db_schema and db_schema["tables"]:
            return {tbl.lower() for tbl in db_schema["tables"].keys()}
    except Exception:
        pass

    # Fallback to clinical registry dataset names
    return {ds.name.lower() for ds in clinical_registry.list_datasets()}


def validate_selected_table_allowlist(selected_tables: List[str]) -> Tuple[bool, Set[str], Set[str]]:
    """
    Validates user-selected tables against the registered database allowlist.
    Returns: (is_valid, valid_tables_set, unknown_tables_set)
    """
    registered = get_registered_tables()
    cleaned = {t.strip().lower() for t in (selected_tables or []) if t and t.strip()}

    if not cleaned:
        return False, set(), set()

    unknown = cleaned - registered
    valid = cleaned & registered
    return len(unknown) == 0 and len(valid) > 0, valid, unknown


def identify_required_tables(
    question: str,
    selected_tables: Optional[List[str]] = None,
    current_plan: Optional[str] = None,
) -> Tuple[Set[str], bool, str]:
    """
    Identifies the minimum required tables to answer the clinical question.
    Returns: (required_tables, is_available_in_database, error_message)
    """
    if not question or not question.strip():
        return set(), False, "No clinical question provided."

    q_lower = question.strip().lower()
    registered = get_registered_tables()
    required: Set[str] = set()

    # 1. Deterministic clinical question mapping
    cplan = build_clinical_question_plan(question)
    if cplan and cplan.is_supported:
        required.update(ds.lower() for ds in cplan.datasets)

    # 2. Domain-specific requirements for multi-table relationships:
    has_treatment_arm = bool(
        re.search(r'\b(treatment[\s_-]*arms?|treatment[\s_-]*groups?|by[\s_-]*arm|by[\s_-]*treatment|arms?)\b', q_lower)
    )
    is_lab = any(k in q_lower for k in ["lab", "laboratory", "hemoglobin", "hgb", "alanine", "alt", "ast", "creatinine"])
    is_vital = any(k in q_lower for k in ["vital", "vitals", "blood pressure", "sysbp", "diabp", "pulse", "temp", "heart rate"])
    is_ae = any(k in q_lower for k in ["adverse event", "adverse events", "ae", "safety", "toxic", "sae", "teae"])
    is_enrollment = any(k in q_lower for k in ["enroll", "enrolled", "enrollment", "site", "center", "sites", "centers"])
    is_subject = any(k in q_lower for k in ["subject", "subjects", "patient", "patients", "demographic", "demographics", "age", "sex", "race"])

    if is_ae and has_treatment_arm:
        required.update(["adsl", "adae"])
    elif is_lab and has_treatment_arm:
        # Lab change from baseline by treatment arm requires adlb (analysis lab) and adsl (treatment arm/population)
        required.update(["adlb", "adsl"])
    elif is_vital and has_treatment_arm:
        required.update(["advs", "adsl"])
    elif is_ae and "severity" in q_lower:
        if has_treatment_arm:
            required.update(["adsl", "adae"])
        else:
            required.add("adae")
    elif is_ae and any(k in q_lower for k in ["rate", "incidence", "percent", "proportion"]):
        required.update(["adsl", "adae"])
    elif is_ae:
        if not required:
            required.add("adae" if "adae" in registered else "ae")
    elif is_lab:
        if not required:
            required.add("adlb" if "adlb" in registered else "lb")
    elif is_vital:
        if not required:
            required.add("advs" if "advs" in registered else "vs")
    elif is_enrollment and any(k in q_lower for k in ["site", "center"]):
        if not required:
            if any(w in q_lower for w in ["subject", "patient", "recruited"]):
                required.update(["sites", "dm" if "dm" in registered else "adsl"])
            else:
                required.add("sites")
    elif is_subject:
        if not required:
            required.add("adsl" if "adsl" in registered else "dm")

    # 3. If an explicit analysis plan is provided, extract proposed tables
    if current_plan:
        from app.analytics.sql_validator import _extract_plan_datasets
        plan_datasets = _extract_plan_datasets(current_plan)
        for ds in plan_datasets:
            if ds.lower() in registered:
                required.add(ds.lower())

    # 4. Detect questions requesting non-existent or unsupported data sources (e.g. Test D)
    unregistered_indicators = {
        "genomic": "genomic sequencing table (e.g. gv/genomics)",
        "sequencing": "genomic sequencing table",
        "protocol document": "protocol document store",
        "inclusion criteria": "protocol criteria document",
        "exclusion criteria": "protocol criteria document",
        "concomitant": "cm (concomitant medications)",
        "imaging": "radiology/imaging table (e.g. img/dicom)",
        "radiology": "radiology table",
    }
    for keyword, desc in unregistered_indicators.items():
        if keyword in q_lower:
            short_tbl = keyword.split()[0]
            if short_tbl not in registered:
                return required or {short_tbl}, False, f"The required data source ({desc}) is unavailable in the active clinical dataset."

    if not required:
        return set(), False, "Could not determine the required clinical data sources for this question."

    # Check if any identified required table is not in registered tables
    unregistered = required - registered
    if unregistered:
        return required, False, f"The required data source ({', '.join(sorted(unregistered)).upper()}) is unavailable in the active clinical dataset."

    return required, True, ""


def check_table_selection(
    question: str,
    selected_tables: List[str],
    current_plan: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validates that user-selected tables fulfill the strict boundary required by the question.
    Returns structured validation response according to platform conventions.
    """
    clean_selected = [t.strip().lower() for t in (selected_tables or []) if t and t.strip()]

    # 1. Validate allowlist
    is_valid_allowlist, valid_selected, unknown_selected = validate_selected_table_allowlist(clean_selected)
    if not clean_selected or not is_valid_allowlist:
        unknown_msg = f"Unknown or unregistered table(s): {', '.join(sorted(unknown_selected))}. " if unknown_selected else "No dataset tables are selected. "
        return {
            "status": "blocked",
            "reason": "invalid_table_selection",
            "question": question,
            "required_tables": [],
            "selected_tables": clean_selected,
            "missing_tables": [],
            "message": f"{unknown_msg}Please select valid tables from the Dataset Tables sidebar.",
            "next_action": "select_valid_tables",
        }

    # 2. Identify required tables
    required_tables, is_available, err_msg = identify_required_tables(
        question=question,
        selected_tables=clean_selected,
        current_plan=current_plan,
    )

    if not is_available:
        return {
            "status": "blocked",
            "reason": "required_table_unavailable",
            "question": question,
            "required_tables": sorted(list(required_tables)),
            "selected_tables": sorted(list(clean_selected)),
            "missing_tables": sorted(list(required_tables)),
            "message": err_msg or "The required clinical data source is unavailable in the active dataset.",
            "next_action": "unsupported_data_source",
        }

    # 3. Compute missing tables: required_tables - selected_tables
    missing = required_tables - set(clean_selected)
    if missing:
        missing_list = sorted(list(missing))
        missing_display = ", ".join(t.upper() for t in missing_list)
        return {
            "status": "blocked",
            "reason": "required_tables_not_selected",
            "question": question,
            "required_tables": sorted(list(required_tables)),
            "selected_tables": sorted(list(clean_selected)),
            "missing_tables": missing_list,
            "message": f"This analysis requires the {missing_display} table{'s' if len(missing_list) > 1 else ''}, but {'they have' if len(missing_list) > 1 else 'it has'} not been selected.",
            "next_action": "select_missing_tables",
        }

    # 4. All required tables are selected!
    return {
        "status": "passed",
        "reason": None,
        "question": question,
        "required_tables": sorted(list(required_tables)),
        "selected_tables": sorted(list(clean_selected)),
        "missing_tables": [],
        "message": "All required tables are selected and authorized.",
        "next_action": None,
    }


def extract_sql_tables_ast(sql: str) -> Set[str]:
    """
    Extracts all physical table references from a SQL query using sqlglot AST parsing.
    Properly excludes CTE names defined in WITH clauses while inspecting their inner queries.
    """
    if not sql or not sql.strip():
        return set()

    try:
        parsed = sqlglot.parse_one(sql, read="mysql")
        if parsed is None:
            return set()

        # Gather CTE alias names defined in WITH expressions
        cte_names = {
            cte.alias_or_name.lower()
            for cte in parsed.find_all(exp.CTE)
            if cte.alias_or_name
        }

        # Gather all physical table references not matching a CTE name
        tables: Set[str] = set()
        for t in parsed.find_all(exp.Table):
            tbl_name = t.name.lower() if t.name else ""
            if tbl_name and tbl_name not in cte_names and not tbl_name.startswith("@"):
                tables.add(tbl_name)

        return tables
    except Exception:
        # Robust fallback using regex if syntax dialect variance occurs
        tables = set()
        cte_pattern = re.findall(r"\bWITH\s+([A-Za-z0-9_]+)\s+AS", sql, re.IGNORECASE)
        ctes = {c.lower() for c in cte_pattern}
        matches = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.IGNORECASE)
        for m in matches:
            m_lower = m.lower()
            if m_lower not in ctes and m_lower not in ("select", "where", "group", "order", "having"):
                tables.add(m_lower)
        return tables


def enforce_sql_table_boundaries(sql: str, selected_tables: List[str]) -> Tuple[bool, Set[str]]:
    """
    Verifies that every table referenced in the SQL query (via AST) belongs
    to the authorized selected_tables allowlist.
    Returns: (is_authorized, set_of_unauthorized_tables)
    """
    allowed_set = {t.strip().lower() for t in (selected_tables or []) if t and t.strip()}
    referenced = extract_sql_tables_ast(sql)

    unauthorized = referenced - allowed_set
    return len(unauthorized) == 0, unauthorized
