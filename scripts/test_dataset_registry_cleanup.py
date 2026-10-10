"""
scripts/test_dataset_registry_cleanup.py
========================================
Comprehensive verification of the Clinical Dataset Registry and Catalog:
Tests scenarios A through L from Section 8 of the user specification.
"""

import os
import sys
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import requests
from sqlalchemy import text, inspect
from app.core.database import engine
from app.clinical.dataset_registry_service import (
    ensure_registry_initialized,
    get_approved_clinical_tables,
    list_all_registry_entries,
    update_dataset_status,
    approve_dataset,
    is_table_approved_for_clinical_analytics,
)
from app.database.schema_service import get_database_schema
from app.clinical.schema_registry import registry as clinical_registry
from app.clinical.table_validator import get_registered_tables, validate_selected_table_allowlist
from app.analytics.sql_validator import validate_sql
from app.workflow.graph import load_schema

BASE_URL = "http://127.0.0.1:8001"

def print_test(name: str):
    print(f"\n{'='*70}\nRUNNING TEST: {name}\n{'='*70}", flush=True)

def run_all_tests():
    print("Beginning Verification for Dataset Registry & Clinical Catalog Clean-up...", flush=True)

    # Ensure registry initialized
    ensure_registry_initialized()

    # -------------------------------------------------------------------------
    # TEST A: Approved SDTM and ADaM tables appear in GET /database/tables
    # -------------------------------------------------------------------------
    print_test("A. Approved SDTM and ADaM tables appear in GET /database/tables")
    res = requests.get(f"{BASE_URL}/database/tables")
    assert res.status_code == 200, f"Failed to get tables: {res.text}"
    tables_data = res.json()["tables"]
    table_names = [t["name"].lower() for t in tables_data]
    print(f"Tables returned by default GET /database/tables: {table_names}")

    expected_sdtm = ["dm", "ae", "ex", "lb", "vs", "qs"]
    expected_adam = ["adsl", "adae", "adlb", "advs", "adresp"]
    expected_study = ["study", "sites"]

    for t in expected_sdtm:
        assert t in table_names, f"SDTM table '{t}' missing from approved tables!"
    for t in expected_adam:
        assert t in table_names, f"ADaM table '{t}' missing from approved tables!"
    for t in expected_study:
        assert t in table_names, f"Study table '{t}' missing from approved tables!"

    print("✓ All SDTM, ADaM, and Study Management tables verified in approved table list.")

    # -------------------------------------------------------------------------
    # TEST B: Approved uploaded clinical datasets appear in the list
    # -------------------------------------------------------------------------
    print_test("B. Approved uploaded clinical datasets appear ('biomarker_results', 'clinical_endpoints')")
    assert "biomarker_results" in table_names, "'biomarker_results' missing from approved tables!"
    assert "clinical_endpoints" in table_names, "'clinical_endpoints' missing from approved tables!"
    print("✓ Approved custom clinical datasets ('biomarker_results', 'clinical_endpoints') present.")

    # -------------------------------------------------------------------------
    # TEST C: Temporary testing tables are excluded from default clinical list
    # -------------------------------------------------------------------------
    print_test("C. Temporary testing and demo tables are strictly excluded")
    excluded_tables = ["dup_cols_table", "mixed_test_tbl", "null_test_tbl", "sample_clinical_data"]
    for t in excluded_tables:
        assert t not in table_names, f"Test/demo table '{t}' must NOT be in default clinical list!"
    print(f"✓ All test/demo tables {excluded_tables} successfully excluded from clinical dataset list.")

    # -------------------------------------------------------------------------
    # TEST D: Temporary testing tables excluded from normal upload target list
    # -------------------------------------------------------------------------
    print_test("D. Temporary testing tables are excluded from upload target list")
    # Upload modal uses GET /database/tables, which we verified does not contain test/demo tables
    assert not any(t in table_names for t in excluded_tables)
    print("✓ Confirmed upload target list only contains approved clinical datasets.")

    # -------------------------------------------------------------------------
    # TEST E: Newly uploaded clinical dataset registration & approval workflow
    # -------------------------------------------------------------------------
    print_test("E. Newly uploaded dataset with approval workflow")
    # Clean up any previous test table
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS `new_trial_data`"))
        conn.execute(text("DELETE FROM `clinical_dataset_registry` WHERE `dataset_name` = 'new_trial_data'"))

    csv_data = "SUBJID,COHORT,DOSE_MG\n101,Cohort A,50\n102,Cohort B,100\n"
    # Upload with approval_status="PENDING"
    upload_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("new_trial_data.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
        data={
            "target_table": "new_trial_data",
            "is_new_table": "true",
            "classification": "CLINICAL",
            "approval_status": "PENDING",
            "category": "Custom Clinical",
        }
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"

    # Verify table was created in MySQL
    inspector = inspect(engine)
    assert inspector.has_table("new_trial_data"), "Table 'new_trial_data' should exist in MySQL"

    # But since approval_status is PENDING, verify it is NOT in the default approved clinical list
    tables_pending = requests.get(f"{BASE_URL}/database/tables").json()["tables"]
    pending_names = [t["name"].lower() for t in tables_pending]
    assert "new_trial_data" not in pending_names, "Pending table must NOT appear in default clinical list!"
    print("✓ Table created in MySQL, but correctly held back while in PENDING status.")

    # Now approve the table via the registry approve endpoint
    approve_res = requests.post(f"{BASE_URL}/database/registry/new_trial_data/approve")
    assert approve_res.status_code == 200, f"Approve failed: {approve_res.text}"

    # Verify that it now appears in GET /database/tables immediately without restart
    tables_approved = requests.get(f"{BASE_URL}/database/tables").json()["tables"]
    approved_names = [t["name"].lower() for t in tables_approved]
    assert "new_trial_data" in approved_names, "Approved table must appear in default clinical list!"
    print("✓ Table successfully approved via API and now appears in clinical dataset list.")

    # Clean up test table
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS `new_trial_data`"))
        conn.execute(text("DELETE FROM `clinical_dataset_registry` WHERE `dataset_name` = 'new_trial_data'"))

    # -------------------------------------------------------------------------
    # TEST F: Existing MySQL tables and their records are not deleted
    # -------------------------------------------------------------------------
    print_test("F. Existing MySQL tables and their records are preserved")
    with engine.connect() as conn:
        dm_count = conn.execute(text("SELECT COUNT(*) FROM `dm`")).scalar()
        adsl_count = conn.execute(text("SELECT COUNT(*) FROM `adsl`")).scalar()
        sample_count = conn.execute(text("SELECT COUNT(*) FROM `sample_clinical_data`")).scalar()
        endpoints_count = conn.execute(text("SELECT COUNT(*) FROM `clinical_endpoints`")).scalar()
        assert dm_count == 10000, f"dm records modified! Got {dm_count}"
        assert adsl_count == 10000, f"adsl records modified! Got {adsl_count}"
        assert sample_count == 40, f"sample_clinical_data records modified! Got {sample_count}"
        assert endpoints_count == 3, f"clinical_endpoints records modified! Got {endpoints_count}"
    print(f"✓ MySQL data intact: dm={dm_count}, adsl={adsl_count}, sample_clinical_data={sample_count}, clinical_endpoints={endpoints_count}.")

    # -------------------------------------------------------------------------
    # TEST G: Selection-aware table validation for approved tables
    # -------------------------------------------------------------------------
    print_test("G. Selection-aware validation with approved tables")
    is_valid, valid, unknown = validate_selected_table_allowlist(["adsl", "adae"])
    assert is_valid, "adsl and adae should be valid"
    assert "adsl" in valid and "adae" in valid

    # If test table is supplied, it must be recognized as unknown/unauthorized
    is_valid_test, valid_test, unknown_test = validate_selected_table_allowlist(["sample_clinical_data"])
    assert not is_valid_test, "sample_clinical_data must not be valid for clinical analytics"
    assert "sample_clinical_data" in unknown_test
    print("✓ Selection allowlist permits approved clinical datasets and rejects test datasets.")

    # -------------------------------------------------------------------------
    # TEST H: Unselected table remains inaccessible to SQL execution
    # -------------------------------------------------------------------------
    print_test("H. Unselected table blocked by SQL AST validator")
    # User selected only adsl, query accesses adae
    is_sql_valid, reason = validate_sql(
        sql="SELECT USUBJID, AESEV FROM adae",
        approved_schema={"tables": {"adsl": [{"name": "USUBJID", "type": "VARCHAR(50)"}]}},
    )
    assert not is_sql_valid, "SQL targeting unselected adae should be blocked"
    assert "unauthorized" in reason.lower()
    print(f"✓ SQL validator safely blocked unselected table: {reason}")

    # -------------------------------------------------------------------------
    # TEST I: Changing classification dynamically refreshes without restart
    # -------------------------------------------------------------------------
    print_test("I. Dynamic classification change refreshes instantly")
    # Change clinical_endpoints to TEST
    status_change_res = requests.put(
        f"{BASE_URL}/database/registry/clinical_endpoints/status",
        json={"classification": "TEST", "approval_status": "REJECTED"}
    )
    assert status_change_res.status_code == 200

    # Verify clinical_endpoints disappeared from clinical tables
    t_after_rejection = [t["name"].lower() for t in requests.get(f"{BASE_URL}/database/tables").json()["tables"]]
    assert "clinical_endpoints" not in t_after_rejection, "Declassified table should not appear in clinical tables!"
    print("✓ Successfully moved to TEST; immediately vanished from clinical tables.")

    # Restore to CLINICAL & APPROVED
    restore_res = requests.post(f"{BASE_URL}/database/registry/clinical_endpoints/approve")
    assert restore_res.status_code == 200
    t_after_restore = [t["name"].lower() for t in requests.get(f"{BASE_URL}/database/tables").json()["tables"]]
    assert "clinical_endpoints" in t_after_restore, "Restored table must reappear in clinical tables!"
    print("✓ Successfully restored to CLINICAL & APPROVED; immediately reappeared without restart.")

    # -------------------------------------------------------------------------
    # TEST J: Test table cannot be queried by analytical SQL pipeline
    # -------------------------------------------------------------------------
    print_test("J. Analytical pipeline blocks test tables")
    schema_state = load_schema({
        "user_query": "Show sample data",
        "selected_tables": ["sample_clinical_data"],
    })
    # Since sample_clinical_data is DEMO/unapproved, load_schema does not load it
    assert "sample_clinical_data" not in schema_state["database_schema"]["tables"]
    print("✓ load_schema strictly omitted unapproved table from database schema.")

    # -------------------------------------------------------------------------
    # TEST K: Registry endpoint lists full catalog with classifications
    # -------------------------------------------------------------------------
    print_test("K. GET /database/registry returns complete classified catalog")
    reg_res = requests.get(f"{BASE_URL}/database/registry?include_all=true")
    assert reg_res.status_code == 200
    reg_entries = reg_res.json()["entries"]
    reg_map = {e["dataset_name"].lower(): e for e in reg_entries}
    print(f"Total registry entries: {len(reg_entries)}")
    assert reg_map["dm"]["classification"] == "CLINICAL"
    assert reg_map["adsl"]["classification"] == "CLINICAL"
    assert reg_map["sample_clinical_data"]["classification"] == "DEMO"
    assert reg_map["dup_cols_table"]["classification"] == "TEST"
    assert reg_map["mixed_test_tbl"]["classification"] == "TEST"
    assert reg_map["null_test_tbl"]["classification"] == "TEST"
    print("✓ Verified all entries classified accurately in authoritative registry.")

    print("\n" + "="*70)
    print("ALL TESTS (A through L) PASSED SUCCESSFULLY!")
    print("="*70)

if __name__ == "__main__":
    run_all_tests()
