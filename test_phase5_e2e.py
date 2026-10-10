"""
test_phase5_e2e.py
===================
End-to-End Test Suite for Phase 5 — MySQL Clinical Data Layer
"""
import sys
import json
import urllib.request
import urllib.error
from sqlalchemy import inspect, text

from app.core.database import engine, get_db_context
from app.database.session import init_db
from app.ingestion.mysql_loader import sanitize_table_name, resolve_safe_file_path

BASE_URL = "http://127.0.0.1:8001"

passed = 0
failed = 0

def report(test_name: str, success: bool, details: str = ""):
    global passed, failed
    if success:
        passed += 1
        print(f"[PASS] {test_name} {details}")
    else:
        failed += 1
        print(f"[FAIL] {test_name} - {details}")

def http_req(path: str, method: str = "GET", data: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            resp_body = json.loads(resp.read().decode("utf-8"))
            return status_code, resp_body
    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            resp_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            resp_body = {"error": str(e)}
        return status_code, resp_body
    except Exception as e:
        return 500, {"error": str(e)}


print("=" * 70)
print("RUNNING PHASE 5 COMPREHENSIVE VERIFICATION")
print("=" * 70)

# -----------------------------------------------------------------------------
# Test 1 & 2: Unit tests on table name sanitization & safety
# -----------------------------------------------------------------------------
try:
    assert sanitize_table_name("sample_clinical_data.csv") == "sample_clinical_data"
    assert sanitize_table_name("analytics_patients.csv") == "analytics_patients"
    assert sanitize_table_name("123-Patient Records (2024)! .csv") == "tbl_123_patient_records_2024"
    assert sanitize_table_name("SELECT.csv") == "tbl_select"
    assert sanitize_table_name("ORDER.csv") == "tbl_order"
    
    # Protected table rejection
    threw_protected = False
    try:
        sanitize_table_name("dataset_versions")
    except ValueError:
        threw_protected = True
    assert threw_protected, "Should reject protected metadata table names"
    
    report("1. Safe Table Name Sanitization", True, "(lowercase, underscores, prefixes, keyword protection)")
except Exception as e:
    report("1. Safe Table Name Sanitization", False, str(e))

# -----------------------------------------------------------------------------
# Test 3: Path Traversal Security
# -----------------------------------------------------------------------------
try:
    threw_security = False
    try:
        resolve_safe_file_path(file_path="../../Windows/System32/drivers/etc/hosts")
    except (ValueError, FileNotFoundError):
        threw_security = True
    assert threw_security, "Should reject arbitrary filesystem traversal"
    report("2. Path Traversal Security Check", True, "(Rejects paths outside allowed directories)")
except Exception as e:
    report("2. Path Traversal Security Check", False, str(e))

# -----------------------------------------------------------------------------
# Test 4: Metadata table initialization
# -----------------------------------------------------------------------------
try:
    init_res = init_db()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected_meta = ["dataset_versions", "dataset_columns", "approved_relationships", "audit_logs"]
    all_present = all(t in tables for t in expected_meta)
    assert all_present, f"Missing tables in {tables}"
    report("3. Metadata Tables Initialized", True, f"Found: {expected_meta}")
except Exception as e:
    report("3. Metadata Tables Initialized", False, str(e))

# -----------------------------------------------------------------------------
# Test 5 & 6: GET /health and GET /health/db
# -----------------------------------------------------------------------------
s, b = http_req("/health")
report("4. GET /health", s == 200 and b.get("status") == "healthy", f"Status: {s}")

s, b = http_req("/health/db")
report("5. GET /health/db", s == 200 and b.get("database", {}).get("status") == "healthy", f"Status: {s}")

# -----------------------------------------------------------------------------
# Test 7: POST /ingestion/analyze (Real dataset directory to populate candidates)
# -----------------------------------------------------------------------------
s, b = http_req("/ingestion/analyze", method="POST", data={
    "directory_path": r"C:\Users\sathy\OneDrive\Documents\Desktop\Office Bootcamp\Dataset\CSV Dataset"
})
report("6. POST /ingestion/analyze", s == 200 and b.get("status") == "success", f"Datasets analyzed: {len(b.get('datasets', []))}, Candidates: {len(b.get('relationships', []))}")

# -----------------------------------------------------------------------------
# Test 8: Clean and load fresh table via POST /database/load
# -----------------------------------------------------------------------------
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS sample_clinical_data"))
    conn.execute(text("DELETE FROM dataset_columns WHERE dataset_name='sample_clinical_data'"))
    conn.execute(text("DELETE FROM dataset_versions WHERE dataset_name='sample_clinical_data'"))

s, b = http_req("/database/load", method="POST", data={
    "filename": "sample_clinical_data.csv",
    "if_exists": "fail"
})
table_name = b.get("table_name")
rows_loaded = b.get("rows_loaded")
cols_loaded = b.get("columns_loaded")
v_id = b.get("dataset_version_id")
v_num = b.get("version_number")

report("7. POST /database/load (Initial Load)", s == 200 and b.get("status") == "success",
       f"table='{table_name}', rows={rows_loaded}, cols={cols_loaded}, version_id={v_id}")

# -----------------------------------------------------------------------------
# Test 9: Verify clinical table exists in MySQL
# -----------------------------------------------------------------------------
inspector = inspect(engine)
clinical_table_exists = inspector.has_table("sample_clinical_data")
report("8. Clinical Table in MySQL", clinical_table_exists, "Table 'sample_clinical_data' exists")

# -----------------------------------------------------------------------------
# Test 10 & 11: Verify row and column count in MySQL
# -----------------------------------------------------------------------------
with engine.connect() as conn:
    row_count = conn.execute(text("SELECT COUNT(*) FROM sample_clinical_data")).scalar()
    col_names = [col["name"] for col in inspector.get_columns("sample_clinical_data")]

report("9. Verify Row Count in MySQL", row_count == 40, f"Actual rows in MySQL: {row_count} (Expected: 40)")
report("10. Verify Column Count in MySQL", len(col_names) == 13, f"Actual cols in MySQL: {len(col_names)} (Expected: 13)")

# -----------------------------------------------------------------------------
# Test 12: Verify dataset_versions contains load record
# -----------------------------------------------------------------------------
with engine.connect() as conn:
    v_row = conn.execute(text("SELECT id, dataset_name, row_count, column_count, status FROM dataset_versions WHERE dataset_name='sample_clinical_data' ORDER BY id DESC LIMIT 1")).fetchone()

report("11. Verify dataset_versions Record", v_row is not None and v_row[4] == "LOADED", f"Version Record: id={v_row[0] if v_row else None}, status={v_row[4] if v_row else None}")

# -----------------------------------------------------------------------------
# Test 13: Verify dataset_columns contains column metadata
# -----------------------------------------------------------------------------
with engine.connect() as conn:
    col_count_db = conn.execute(text(f"SELECT COUNT(*) FROM dataset_columns WHERE dataset_version_id={v_id}")).scalar()

report("12. Verify dataset_columns Records", col_count_db == 13, f"Column metadata records stored: {col_count_db} (Expected: 13)")

# -----------------------------------------------------------------------------
# Test 14: Duplicate loading behavior with if_exists='fail' -> 409
# -----------------------------------------------------------------------------
s, b = http_req("/database/load", method="POST", data={
    "filename": "sample_clinical_data.csv",
    "if_exists": "fail"
})
report("13. Duplicate Load with if_exists='fail'", s == 409, f"Received status {s} (Expected 409 Conflict)")

# -----------------------------------------------------------------------------
# Test 15: Overwrite load with if_exists='replace' -> 200
# -----------------------------------------------------------------------------
s, b = http_req("/database/load", method="POST", data={
    "filename": "sample_clinical_data.csv",
    "if_exists": "replace"
})
report("14. Replace Load with if_exists='replace'", s == 200 and b.get("version_number") == (v_num + 1), f"Loaded as Version {b.get('version_number')}")

# -----------------------------------------------------------------------------
# Test 16: Invalid / Nonexistent file -> 404
# -----------------------------------------------------------------------------
s, b = http_req("/database/load", method="POST", data={
    "filename": "non_existent_file_9999.csv",
    "if_exists": "fail"
})
report("15. Nonexistent File Load Rejection", s == 404, f"Received status {s} (Expected 404 Not Found)")

# -----------------------------------------------------------------------------
# Test 17: Relationship review persistence in MySQL
# -----------------------------------------------------------------------------
# Review 1: APPROVE detected candidate patients.ID -> encounters.PATIENT
s, b = http_req("/relationships/review", method="POST", data={
    "parent_table": "patients",
    "parent_column": "ID",
    "child_table": "encounters",
    "child_column": "PATIENT",
    "action": "APPROVE",
    "analyst_note": "Verified clinical link between patients and encounters."
})
report("16. POST /relationships/review (APPROVE)", s == 200, f"Status: {s}")

# Verify in MySQL approved_relationships
with engine.connect() as conn:
    rel_row = conn.execute(text("SELECT parent_table, child_table, status FROM approved_relationships WHERE parent_table='patients' AND child_table='encounters'")).fetchone()

report("17. Verify Approved Relationship in MySQL", rel_row is not None and rel_row[2] == "APPROVED", f"Persisted: {rel_row}")

# Review 2: REJECT detected candidate encounters.ID -> observations.ENCOUNTER
s, b = http_req("/relationships/review", method="POST", data={
    "parent_table": "encounters",
    "parent_column": "ID",
    "child_table": "observations",
    "child_column": "ENCOUNTER",
    "action": "REJECT",
    "analyst_note": "Rejection test for Phase 5"
})
report("18. POST /relationships/review (REJECT)", s == 200, f"Status: {s}")

with engine.connect() as conn:
    rej_row = conn.execute(text("SELECT parent_table, child_table, status FROM approved_relationships WHERE parent_table='encounters' AND child_table='observations'")).fetchone()

report("19. Verify Rejected Relationship in MySQL", rej_row is not None and rej_row[2] == "REJECTED", f"Persisted: {rej_row}")

# -----------------------------------------------------------------------------
# Test 18: Audit Log Persistence
# -----------------------------------------------------------------------------
with engine.connect() as conn:
    audit_count = conn.execute(text("SELECT COUNT(*) FROM audit_logs")).scalar()

report("20. Verify Audit Log Persistence in MySQL", audit_count > 0, f"Total audit log records: {audit_count}")

# -----------------------------------------------------------------------------
# Test 19: GET Metadata APIs
# -----------------------------------------------------------------------------
s, b = http_req("/database/versions")
report("21. GET /database/versions", s == 200 and b.get("count") >= 1, f"Versions count: {b.get('count')}")

s, b = http_req(f"/database/versions/{v_id}/columns")
report("22. GET /database/versions/{id}/columns", s == 200 and b.get("count") == 13, f"Columns returned: {b.get('count')}")

s, b = http_req("/database/relationships")
report("23. GET /database/relationships", s == 200 and len(b) >= 2, f"Persisted relationships returned: {len(b)}")

s, b = http_req("/database/audit-logs")
report("24. GET /database/audit-logs", s == 200 and b.get("count") >= 1, f"Audit logs returned: {b.get('count')}")

# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
print("=" * 70)
print(f"RESULTS: {passed} PASSED, {failed} FAILED (Total: {passed + failed})")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    print("ALL PHASE 5 TESTS PASSED SUCCESSFULLY!")
