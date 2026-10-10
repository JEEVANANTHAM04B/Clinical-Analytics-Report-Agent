"""
scripts/test_custom_datasets_removal.py
======================================
Automated verification for removing custom datasets (biomarker_results, clinical_endpoints)
from the default approved clinical dataset catalog.

Tests:
A. biomarker_results is absent from the default clinical list
B. clinical_endpoints is absent from the default clinical list
C. Neither table appears in normal upload target dropdown
D. Both MySQL tables and their records remain intact
E. The core SDTM, ADaM, study, and sites datasets remain available (13 tables)
F. Unapproved tables cannot be queried by clinical agents (selection & SQL validation block them)
G. Existing clinical analytics workflow and chart generation still work
"""

import sys
import os
import requests
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import engine
from app.clinical.dataset_registry_service import (
    get_approved_clinical_tables,
    is_table_approved_for_clinical_analytics,
    list_all_registry_entries,
)
from app.clinical.table_validator import (
    get_registered_tables,
    validate_selected_table_allowlist,
    check_table_selection,
    enforce_sql_table_boundaries,
)
from app.database.schema_service import get_database_schema

BASE_URL = "http://127.0.0.1:8001"

EXPECTED_13_TABLES = sorted([
    # SDTM
    "dm", "ae", "ex", "lb", "vs", "qs",
    # ADaM
    "adsl", "adae", "adlb", "advs", "adresp",
    # Study metadata
    "study", "sites"
])

CUSTOM_DATASETS_REMOVED = ["biomarker_results", "clinical_endpoints"]


def run_tests():
    print("======================================================================")
    print("RUNNING CUSTOM DATASETS REMOVAL VERIFICATION")
    print("======================================================================")

    # 1. API GET /database/tables
    res = requests.get(f"{BASE_URL}/database/tables")
    assert res.status_code == 200, f"GET /database/tables failed: {res.text}"
    tables_data = res.json()["tables"]
    api_table_names = sorted([t["name"].lower() for t in tables_data])

    print(f"API Tables returned ({len(api_table_names)}): {api_table_names}")

    # TEST A: biomarker_results absent from default clinical list
    assert "biomarker_results" not in api_table_names, "'biomarker_results' must NOT be in default clinical tables!"
    print("[PASS] TEST A: 'biomarker_results' is absent from the default clinical list.")

    # TEST B: clinical_endpoints absent from default clinical list
    assert "clinical_endpoints" not in api_table_names, "'clinical_endpoints' must NOT be in default clinical tables!"
    print("[PASS] TEST B: 'clinical_endpoints' is absent from the default clinical list.")

    # TEST C: Neither table appears in normal upload target dropdown
    for c_tbl in CUSTOM_DATASETS_REMOVED:
        assert c_tbl not in api_table_names, f"Target table dropdown would receive unapproved table '{c_tbl}'!"
    print("[PASS] TEST C: Neither table appears in normal upload target dropdown.")

    # TEST D: Both MySQL tables and their records remain intact
    with engine.connect() as conn:
        b_cnt = conn.execute(text("SELECT COUNT(*) FROM `biomarker_results`")).scalar()
        c_cnt = conn.execute(text("SELECT COUNT(*) FROM `clinical_endpoints`")).scalar()
        dm_cnt = conn.execute(text("SELECT COUNT(*) FROM `dm`")).scalar()
        adsl_cnt = conn.execute(text("SELECT COUNT(*) FROM `adsl`")).scalar()

    assert b_cnt == 4, f"biomarker_results record count changed! Expected 4, got {b_cnt}"
    assert c_cnt == 3, f"clinical_endpoints record count changed! Expected 3, got {c_cnt}"
    assert dm_cnt == 10000, f"dm record count changed! Expected 10000, got {dm_cnt}"
    assert adsl_cnt == 10000, f"adsl record count changed! Expected 10000, got {adsl_cnt}"
    print(f"[PASS] TEST D: Both MySQL tables and records intact (biomarker_results={b_cnt}, clinical_endpoints={c_cnt}, dm={dm_cnt}, adsl={adsl_cnt}).")

    # TEST E: The core SDTM, ADaM, study, and sites datasets remain available (13 tables)
    assert api_table_names == EXPECTED_13_TABLES, f"Mismatch in expected 13 clinical tables! Got: {api_table_names}"
    approved_backend = sorted(get_approved_clinical_tables())
    assert approved_backend == EXPECTED_13_TABLES, f"Backend approved list mismatch! Got: {approved_backend}"
    registered_tbls = sorted(list(get_registered_tables()))
    assert registered_tbls == EXPECTED_13_TABLES, f"Table validator registered tables mismatch! Got: {registered_tbls}"
    print(f"[PASS] TEST E: Exactly 13 core SDTM, ADaM, study, and sites datasets available: {api_table_names}")

    # TEST F: Unapproved tables cannot be queried by clinical agents
    for c_tbl in CUSTOM_DATASETS_REMOVED:
        assert not is_table_approved_for_clinical_analytics(c_tbl), f"{c_tbl} must not be approved for clinical analytics!"
        is_valid, _, unknown = validate_selected_table_allowlist([c_tbl])
        assert not is_valid, f"{c_tbl} must be rejected by selection allowlist!"
        assert c_tbl in unknown, f"{c_tbl} must be classified as unknown/unapproved!"

        # Check check_table_selection blocks execution
        sel_check = check_table_selection("Analysis query", [c_tbl])
        assert sel_check["status"] == "blocked", f"check_table_selection did not block {c_tbl}!"

    # SQL AST boundary validation
    is_auth, unauth = enforce_sql_table_boundaries("SELECT * FROM `biomarker_results`", ["dm", "adsl"])
    assert not is_auth, "enforce_sql_table_boundaries must block unselected/unapproved biomarker_results!"
    assert "biomarker_results" in unauth, "Unauth tables must report biomarker_results!"
    print("[PASS] TEST F: Unapproved custom tables are strictly blocked from selection and SQL query execution.")

    # TEST G: Existing clinical analytics workflow and chart generation still work
    query_payload = {
        "question": "What is the subject distribution by treatment arm?",
        "selected_tables": ["adsl", "dm"]
    }
    analyze_res = requests.post(f"{BASE_URL}/analytics/run", json=query_payload, timeout=60)
    assert analyze_res.status_code == 200, f"/analytics/run failed: {analyze_res.text}"
    analyze_json = analyze_res.json()
    assert (
        analyze_json.get("status") in ["success", "completed", "plan_ready", "awaiting_approval"]
        or "analysis_plan" in analyze_json
        or "chart_spec" in analyze_json
    ), f"Analytics query failed: {analyze_json}"
    print("[PASS] TEST G: Clinical analytics execution and workflow working seamlessly with approved catalog.")

    # Check registry entries: classification=CUSTOM, approval_status=PENDING
    all_reg = {r["dataset_name"].lower(): r for r in list_all_registry_entries(include_all=True, include_row_counts=False)}
    assert all_reg["biomarker_results"]["classification"] == "CUSTOM"
    assert all_reg["biomarker_results"]["approval_status"] == "PENDING"
    assert all_reg["clinical_endpoints"]["classification"] == "CUSTOM"
    assert all_reg["clinical_endpoints"]["approval_status"] == "PENDING"
    print("[PASS] Verified registry metadata: both datasets classified as CUSTOM (PENDING) in clinical_dataset_registry.")

    print("\n======================================================================")
    print("ALL TESTS (A through G) PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    run_tests()
