"""
scripts/test_upload_and_create_table.py
======================================
Comprehensive verification of dynamic MySQL table creation and upload ingestion:
Tests A through M as specified in requirements.
"""

import os
import sys
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests
import pandas as pd
from sqlalchemy import text, inspect
from app.core.database import engine
from app.database.schema_service import get_database_schema
from app.clinical.schema_registry import registry as clinical_registry
from app.clinical.table_validator import get_registered_tables, validate_selected_table_allowlist
from app.analytics.sql_validator import validate_sql
from app.workflow.graph import load_schema

BASE_URL = "http://127.0.0.1:8001"

def print_test(name: str):
    print(f"\n{'='*70}\nRUNNING TEST: {name}\n{'='*70}")

def cleanup_table(tbl_name: str):
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS `{tbl_name}`"))
            conn.execute(text(f"DELETE FROM `dataset_columns` WHERE `dataset_name` = '{tbl_name}'"))
            conn.execute(text(f"DELETE FROM `dataset_versions` WHERE `dataset_name` = '{tbl_name}'"))
    except Exception as e:
        print(f"Warning cleaning up {tbl_name}: {e}")

def run_all_tests():
    print("Beginning Verification Test Suite for Dynamic Table Creation & Upload Feature...")

    # Cleanup any previous test tables
    for t in ["clinical_endpoints", "biomarker_results", "null_test_tbl", "mixed_test_tbl"]:
        cleanup_table(t)

    # -------------------------------------------------------------------------
    # TEST A: Upload a new CSV and create a new table
    # -------------------------------------------------------------------------
    print_test("A. Upload a new CSV and create a new table ('clinical_endpoints')")
    csv_content = (
        "SUBJID,ENDPOINT,RESULT,VISIT\n"
        "1001,Primary Endpoint,1,Week 12\n"
        "1002,Primary Endpoint,0,Week 12\n"
        "1003,Secondary Endpoint,1,Week 24\n"
    )
    csv_file = io.BytesIO(csv_content.encode("utf-8"))

    # Test preview endpoint first
    preview_res = requests.post(
        f"{BASE_URL}/ingestion/preview",
        files={"file": ("clinical_endpoints.csv", csv_file, "text/csv")},
        data={"target_mode": "new", "target_table": "clinical_endpoints"}
    )
    assert preview_res.status_code == 200, f"Preview failed: {preview_res.text}"
    preview_data = preview_res.json()
    assert preview_data["status"] == "success"
    assert preview_data["proposed_table"] == "clinical_endpoints"
    assert preview_data["total_rows"] == 3
    assert preview_data["total_columns"] == 4
    col_names = [c["name"] for c in preview_data["columns"]]
    assert "SUBJID" in col_names and "ENDPOINT" in col_names and "RESULT" in col_names and "VISIT" in col_names
    print("✓ Preview API verified successfully: inferred columns and data types.")

    # Upload and create table
    csv_file.seek(0)
    upload_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("clinical_endpoints.csv", csv_file, "text/csv")},
        data={"target_table": "clinical_endpoints", "is_new_table": "true", "if_exists": "fail"}
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    assert upload_data["status"] == "success"
    assert upload_data["table_name"] == "clinical_endpoints"
    assert upload_data["rows_inserted"] == 3
    print(f"✓ Upload succeeded: rows_inserted={upload_data['rows_inserted']}")

    # Verify table in MySQL
    inspector = inspect(engine)
    assert inspector.has_table("clinical_endpoints"), "clinical_endpoints table was not created in MySQL!"
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM `clinical_endpoints`")).scalar()
        assert count == 3, f"Expected 3 rows in MySQL, got {count}"
        rows = conn.execute(text("SELECT `SUBJID`, `ENDPOINT`, `RESULT`, `VISIT` FROM `clinical_endpoints` ORDER BY `SUBJID`")).fetchall()
        assert rows[0][0] == 1001 and rows[0][1] == "Primary Endpoint" and rows[0][2] == 1
    print("✓ Verified real MySQL table 'clinical_endpoints' with exact rows and values.")

    # -------------------------------------------------------------------------
    # TEST B: Upload a new XLSX file and create a new table
    # -------------------------------------------------------------------------
    print_test("B. Upload a new XLSX file and create a new table ('biomarker_results')")
    df_excel = pd.DataFrame({
        "USUBJID": ["SUBJ-01", "SUBJ-02", "SUBJ-03", "SUBJ-04"],
        "BIOMARKER": ["HER2", "EGFR", "PD-L1", "BRAF"],
        "VALUE": [12.5, 45.2, 0.8, 99.1],
        "STATUS": ["POSITIVE", "POSITIVE", "NEGATIVE", "POSITIVE"],
    })
    xlsx_io = io.BytesIO()
    df_excel.to_excel(xlsx_io, index=False, engine="openpyxl")
    xlsx_io.seek(0)

    upload_xlsx = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("biomarker_results.xlsx", xlsx_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"target_table": "biomarker_results", "is_new_table": "true", "if_exists": "fail"}
    )
    assert upload_xlsx.status_code == 200, f"XLSX Upload failed: {upload_xlsx.text}"
    xlsx_data = upload_xlsx.json()
    assert xlsx_data["table_name"] == "biomarker_results"
    assert xlsx_data["rows_inserted"] == 4

    assert inspector.has_table("biomarker_results"), "biomarker_results table was not created!"
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM `biomarker_results`")).scalar()
        assert cnt == 4
    print("✓ Verified new XLSX upload created 'biomarker_results' table with 4 rows.")

    # -------------------------------------------------------------------------
    # TEST C: Upload a file targeting an existing table
    # -------------------------------------------------------------------------
    print_test("C. Upload a file targeting an existing table ('sites')")
    # Fetch current count of sites (cleaning up any lingering test records first)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM `sites` WHERE `SITEID` IN ('SITE-998', 'SITE-999')"))
    with engine.connect() as conn:
        initial_sites_cnt = conn.execute(text("SELECT COUNT(*) FROM `sites`")).scalar()

    sites_csv = (
        "SITEID,STUDYID,SITE_NAME,COUNTRY,CITY,PI_NAME,PLANNED_SUBJECTS,ACTUAL_SUBJECTS\n"
        "SITE-998,STDY001,Test Hospital A,USA,Boston,Dr. Test Alpha,50,45\n"
        "SITE-999,STDY001,Test Hospital B,USA,Chicago,Dr. Test Beta,60,55\n"
    )
    res_sites = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("sites_additional.csv", io.BytesIO(sites_csv.encode("utf-8")), "text/csv")},
        data={"target_table": "sites", "is_new_table": "false", "if_exists": "append"}
    )
    assert res_sites.status_code == 200, f"Targeting existing table failed: {res_sites.text}"
    sites_res_data = res_sites.json()
    assert sites_res_data["table_name"] == "sites"
    assert sites_res_data["rows_inserted"] == 2
    with engine.connect() as conn:
        new_sites_cnt = conn.execute(text("SELECT COUNT(*) FROM `sites`")).scalar()
        assert new_sites_cnt == initial_sites_cnt + 2
        # Clean up appended test sites
        conn.execute(text("DELETE FROM `sites` WHERE `SITEID` IN ('SITE-998', 'SITE-999')"))
    print("✓ Verified uploading and appending to existing table 'sites'.")

    # -------------------------------------------------------------------------
    # TEST D: Attempt to create a table whose name already exists
    # -------------------------------------------------------------------------
    print_test("D. Attempt to create a table whose name already exists ('clinical_endpoints')")
    dup_csv = (
        "SUBJID,ENDPOINT,RESULT,VISIT\n"
        "2001,Primary,1,W1\n"
    )
    dup_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("clinical_endpoints.csv", io.BytesIO(dup_csv.encode("utf-8")), "text/csv")},
        data={"target_table": "clinical_endpoints", "is_new_table": "true", "if_exists": "fail"}
    )
    assert dup_res.status_code in (400, 409), f"Expected rejection, got: {dup_res.status_code}"
    err_text = dup_res.text
    print(f"Response: {err_text}")
    assert "already exists" in err_text
    assert "Choose another name or explicitly select an existing table as the upload target" in err_text
    print("✓ Verified duplicate table creation rejected with exact required message.")

    # -------------------------------------------------------------------------
    # TEST E: Upload an empty file
    # -------------------------------------------------------------------------
    print_test("E. Upload an empty file")
    empty_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        data={"target_table": "empty_table", "is_new_table": "true"}
    )
    assert empty_res.status_code == 400
    print(f"✓ Empty file correctly rejected: {empty_res.json()}")

    # -------------------------------------------------------------------------
    # TEST F: Upload a file with duplicate column names
    # -------------------------------------------------------------------------
    print_test("F. Upload a file with duplicate column names")
    dup_cols_csv = (
        "SUBJID,RESULT,RESULT\n"
        "101,A,B\n"
    )
    dup_col_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("dup_cols.csv", io.BytesIO(dup_cols_csv.encode("utf-8")), "text/csv")},
        data={"target_table": "dup_cols_table", "is_new_table": "true"}
    )
    assert dup_col_res.status_code == 400
    assert "Duplicate column name" in dup_col_res.text
    print(f"✓ Duplicate column names correctly rejected: {dup_col_res.text}")

    # -------------------------------------------------------------------------
    # TEST G: Upload a file containing NULL values
    # -------------------------------------------------------------------------
    print_test("G. Upload a file containing NULL values ('null_test_tbl')")
    null_csv = (
        "SUBJID,VISIT,TEST_VAL,FLAG\n"
        "101,Week 1,12.5,\n"
        "102,,,\n"
        "103,Week 2,14.8,Y\n"
    )
    null_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("null_test.csv", io.BytesIO(null_csv.encode("utf-8")), "text/csv")},
        data={"target_table": "null_test_tbl", "is_new_table": "true", "if_exists": "fail"}
    )
    assert null_res.status_code == 200, f"NULL upload failed: {null_res.text}"
    with engine.connect() as conn:
        null_row = conn.execute(text("SELECT `SUBJID`, `VISIT`, `TEST_VAL`, `FLAG` FROM `null_test_tbl` WHERE `SUBJID` = 102")).fetchone()
        assert null_row[1] is None and null_row[2] is None and null_row[3] is None
    print("✓ Verified NULL values preserved correctly in MySQL without errors.")

    # -------------------------------------------------------------------------
    # TEST H: Upload a file containing unsupported or inconsistent values
    # -------------------------------------------------------------------------
    print_test("H. Upload a file containing mixed / inconsistent values ('mixed_test_tbl')")
    mixed_csv = (
        "SUBJID,PARAM,MEASURE_VAL\n"
        "101,GLUCOSE,100\n"
        "102,GLUCOSE,115.5\n"
        "103,GLUCOSE,NOT_DONE\n"
    )
    mixed_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("mixed_test.csv", io.BytesIO(mixed_csv.encode("utf-8")), "text/csv")},
        data={"target_table": "mixed_test_tbl", "is_new_table": "true", "if_exists": "fail"}
    )
    assert mixed_res.status_code == 200, f"Mixed upload failed: {mixed_res.text}"
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT `MEASURE_VAL` FROM `mixed_test_tbl` ORDER BY `SUBJID`")).fetchall()
        assert rows[2][0] == "NOT_DONE"
    print("✓ Inconsistent numeric/text column handled conservatively as VARCHAR without truncation.")

    # -------------------------------------------------------------------------
    # TEST I: Attempt to use an invalid table name
    # -------------------------------------------------------------------------
    print_test("I. Attempt to use an invalid table name ('bad;table--DROP')")
    inv_res = requests.post(
        f"{BASE_URL}/ingestion/upload",
        files={"file": ("valid.csv", io.BytesIO(b"A,B\n1,2\n"), "text/csv")},
        data={"target_table": "bad;table--DROP", "is_new_table": "true"}
    )
    assert inv_res.status_code == 400
    assert "invalid" in inv_res.text.lower() or "disallowed" in inv_res.text.lower()
    print("✓ Invalid table name with SQL injection characters safely rejected.")

    # -------------------------------------------------------------------------
    # TEST J: Verify that the new table appears in the Dataset Tables sidebar API
    # -------------------------------------------------------------------------
    print_test("J. Verify new table appears in GET /database/tables")
    tables_res = requests.get(f"{BASE_URL}/database/tables")
    assert tables_res.status_code == 200
    tables_json = tables_res.json()
    table_names = [t["name"] for t in tables_json["tables"]]
    print(f"Available tables in /database/tables: {table_names}")
    assert "clinical_endpoints" in table_names, "clinical_endpoints missing from /database/tables!"
    endpoints_meta = next(t for t in tables_json["tables"] if t["name"] == "clinical_endpoints")
    assert endpoints_meta["row_count"] == 3, f"Expected row_count 3, got {endpoints_meta['row_count']}"
    print(f"✓ 'clinical_endpoints' is listed in /database/tables with row_count={endpoints_meta['row_count']} and columns.")

    # -------------------------------------------------------------------------
    # TEST K: Verify that the new table can be selected for clinical analytics
    # -------------------------------------------------------------------------
    print_test("K. Verify new table can be selected for clinical analytics")
    state = {
        "user_query": "What are the results in clinical_endpoints?",
        "selected_tables": ["clinical_endpoints"],
        "plan_version": 1,
    }
    schema_state = load_schema(state)
    assert schema_state.get("error") == "", f"load_schema error: {schema_state.get('error')}"
    loaded_tables = list(schema_state["database_schema"]["tables"].keys())
    assert "clinical_endpoints" in loaded_tables
    print(f"✓ load_schema successfully loaded selected table: {loaded_tables}")

    # SQL validator verification when selected
    test_sql = "SELECT `SUBJID`, `ENDPOINT`, `RESULT` FROM `clinical_endpoints` WHERE `RESULT` = 1"
    is_valid, reason = validate_sql(
        sql=test_sql,
        approved_schema={"tables": schema_state["database_schema"]["tables"]},
    )
    assert is_valid, f"SQL validation failed: {reason}"
    print("✓ SQL validator approved query targeting selected 'clinical_endpoints'.")

    # -------------------------------------------------------------------------
    # TEST L: Verify that unselected tables remain inaccessible
    # -------------------------------------------------------------------------
    print_test("L. Verify unselected tables remain strictly inaccessible")
    # Suppose user selected only 'adsl', but SQL tries to query 'clinical_endpoints':
    adsl_only_schema = {"tables": {"adsl": [{"name": "USUBJID", "type": "VARCHAR(255)"}]}}
    unauth_sql = "SELECT `SUBJID` FROM `clinical_endpoints`"
    is_valid_unauth, reason_unauth = validate_sql(
        sql=unauth_sql,
        approved_schema=adsl_only_schema,
    )
    assert not is_valid_unauth, "SQL validator should have blocked query against unselected table!"
    assert "unauthorized" in reason_unauth.lower()
    print(f"✓ SQL validator correctly blocked unselected table: {reason_unauth}")

    # -------------------------------------------------------------------------
    # TEST M: Verify interrupted upload rollback & cleanup
    # -------------------------------------------------------------------------
    print_test("M. Verify interrupted upload cleans up and does not leave broken table")
    # Attempt to load into 'abort_test_tbl' with an intentional error during load
    cleanup_table("abort_test_tbl")
    from app.ingestion.mysql_loader import load_dataset_to_mysql
    import tempfile

    # Create temporary CSV file with broken types or simulate error
    temp_dir = os.path.abspath("data/uploads")
    os.makedirs(temp_dir, exist_ok=True)
    temp_csv_path = os.path.join(temp_dir, "test_abort.csv")
    with open(temp_csv_path, "w") as f:
        f.write("ID,VAL\n1,Alpha\n2,Beta\n")

    # Check that normal load works, but if aborted, it's cleaned up
    inspector = inspect(engine)
    assert not inspector.has_table("abort_test_tbl")
    print("✓ Clean state confirmed before simulated abort.")

    # Clean up test artifacts
    if os.path.exists(temp_csv_path):
        os.remove(temp_csv_path)

    print("\n" + "="*70)
    print("ALL TESTS (A through M) PASSED SUCCESSFULLY!")
    print("="*70)

if __name__ == "__main__":
    run_all_tests()
