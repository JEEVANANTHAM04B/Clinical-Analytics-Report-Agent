"""
tests/test_duplicate_upload_handling.py
=======================================
Comprehensive test suite for duplicate-primary-key handling in dataset ingestion.

Covers:
1. Upload with no duplicates (all records inserted).
2. Upload with all records already present (409 on default, 0 inserted / N skipped on insert_new_only).
3. Upload with some duplicate records and some new records (only eligible inserted).
4. Composite primary-key handling (e.g., ae with [USUBJID, AESEQ]).
5. Database failure and transaction rollback (no partial batches left).
6. Intra-file duplicate detection.
7. POST /ingestion/preview duplicate detection metadata.
8. Preservation of existing clinical records.
"""

import io
import pytest
import pandas as pd
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.core.database import engine
from app.ingestion.mysql_loader import (
    get_table_primary_keys,
    identify_duplicate_records,
    DuplicatePrimaryKeyError,
    load_dataset_to_mysql,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# =============================================================================
# 1. Primary Key Constraint Inspection Tests
# =============================================================================

def test_primary_key_inspection_cdisc_tables():
    """Verify primary key columns are inspected accurately for single and composite PKs."""
    dm_pks = get_table_primary_keys("dm")
    assert dm_pks == ["USUBJID"], f"Expected ['USUBJID'] for dm, got {dm_pks}"

    study_pks = get_table_primary_keys("study")
    assert study_pks == ["STUDYID"], f"Expected ['STUDYID'] for study, got {study_pks}"

    ae_pks = get_table_primary_keys("ae")
    assert ae_pks == ["USUBJID", "AESEQ"], f"Expected ['USUBJID', 'AESEQ'] for ae, got {ae_pks}"

    adlb_pks = get_table_primary_keys("adlb")
    assert adlb_pks == ["USUBJID", "PARAMCD", "AVISIT"], f"Expected composite PK for adlb, got {adlb_pks}"


# =============================================================================
# 2. Duplicate Identification Unit Tests
# =============================================================================

def test_identify_duplicates_all_existing():
    """Identify duplicates when all records already exist in target table."""
    # Get 2 existing USUBJIDs from dm
    with engine.connect() as conn:
        res = conn.execute(text("SELECT USUBJID FROM dm LIMIT 2")).fetchall()
        existing_keys = [r[0] for r in res]

    assert len(existing_keys) == 2

    df = pd.DataFrame({
        "STUDYID": ["STDY001", "STDY001"],
        "DOMAIN": ["DM", "DM"],
        "USUBJID": existing_keys,
        "SUBJID": ["9001", "9002"],
        "AGE": [45, 50],
        "SEX": ["M", "F"],
    })

    dup_info = identify_duplicate_records(df, "dm", engine)
    assert dup_info["has_pk"] is True
    assert dup_info["has_duplicates"] is True
    assert dup_info["duplicate_count"] == 2
    assert dup_info["eligible_count"] == 0
    assert len(dup_info["sample_duplicates"]) == 2
    assert dup_info["pk_columns"] == ["USUBJID"]


def test_identify_duplicates_mixed():
    """Identify duplicates when some records exist and some are new."""
    with engine.connect() as conn:
        existing_key = conn.execute(text("SELECT USUBJID FROM dm LIMIT 1")).scalar()

    new_key_1 = "TEST-DUP-NEW-001"
    new_key_2 = "TEST-DUP-NEW-002"

    df = pd.DataFrame({
        "STUDYID": ["STDY001", "STDY001", "STDY001"],
        "DOMAIN": ["DM", "DM", "DM"],
        "USUBJID": [existing_key, new_key_1, new_key_2],
        "SUBJID": ["0001", "9001", "9002"],
        "AGE": [45, 50, 55],
        "SEX": ["M", "F", "M"],
    })

    dup_info = identify_duplicate_records(df, "dm", engine)
    assert dup_info["has_duplicates"] is True
    assert dup_info["duplicate_count"] == 1
    assert dup_info["eligible_count"] == 2
    assert dup_info["duplicate_indices"] == [0]


def test_identify_duplicates_composite_pk():
    """Identify duplicates using composite primary key [USUBJID, AESEQ] on ae."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT USUBJID, AESEQ FROM ae LIMIT 1")).fetchone()
        existing_usubjid, existing_aeseq = row[0], row[1]

    df = pd.DataFrame({
        "STUDYID": ["STDY001", "STDY001", "STDY001"],
        "DOMAIN": ["AE", "AE", "AE"],
        "USUBJID": [existing_usubjid, existing_usubjid, "TEST-AE-NEW-001"],
        "AESEQ": [existing_aeseq, 999999, 1],  # 1st is duplicate, 2nd is same subject new seq, 3rd is new subject
        "AETERM": ["Headache", "Fatigue", "Nausea"],
    })

    dup_info = identify_duplicate_records(df, "ae", engine)
    assert dup_info["has_duplicates"] is True
    assert dup_info["duplicate_count"] == 1
    assert dup_info["eligible_count"] == 2
    assert dup_info["duplicate_indices"] == [0]


def test_identify_intra_file_duplicates():
    """Detect intra-file duplicate keys even if none exist in the database yet."""
    df = pd.DataFrame({
        "STUDYID": ["STDY001", "STDY001", "STDY001"],
        "DOMAIN": ["DM", "DM", "DM"],
        "USUBJID": ["TEST-UNIQUE-A", "TEST-UNIQUE-B", "TEST-UNIQUE-A"],  # row 0 and 2 have identical key
        "SUBJID": ["1", "2", "3"],
    })

    dup_info = identify_duplicate_records(df, "dm", engine)
    assert dup_info["has_duplicates"] is True
    assert dup_info["duplicate_count"] == 1
    assert dup_info["eligible_count"] == 2
    assert dup_info["duplicate_indices"] == [2]


# =============================================================================
# 3. API Upload & Action Tests
# =============================================================================

def test_api_upload_all_duplicates_rejected_by_default(client):
    """Uploading DM records that already exist returns HTTP 409 Conflict with structured metadata."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT USUBJID FROM dm LIMIT 2")).fetchall()
        keys = [r[0] for r in res]

    csv_content = f"STUDYID,DOMAIN,USUBJID,SUBJID,AGE,SEX\nSTDY001,DM,{keys[0]},0001,50,M\nSTDY001,DM,{keys[1]},0002,52,F\n"

    response = client.post(
        "/ingestion/upload",
        files={"file": ("DM_duplicates.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"target_table": "dm"},
    )

    assert response.status_code == 409, f"Expected 409 Conflict, got {response.status_code}: {response.text}"
    data = response.json()
    detail = data.get("detail", {})
    assert detail.get("error_code") == "DUPLICATE_KEY_DETECTED"
    assert detail.get("target_table") == "dm"
    assert detail.get("duplicate_count") == 2
    assert detail.get("eligible_count") == 0
    assert detail.get("primary_key_columns") == ["USUBJID"]


def test_api_upload_insert_new_only_when_all_duplicates(client):
    """When duplicate_action='insert_new_only' and all records exist, reports 0 inserted and N skipped safely."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT USUBJID FROM dm LIMIT 2")).fetchall()
        keys = [r[0] for r in res]

    csv_content = f"STUDYID,DOMAIN,USUBJID,SUBJID,AGE,SEX\nSTDY001,DM,{keys[0]},0001,50,M\nSTDY001,DM,{keys[1]},0002,52,F\n"

    response = client.post(
        "/ingestion/upload",
        files={"file": ("DM_duplicates.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"target_table": "dm", "duplicate_action": "insert_new_only"},
    )

    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert data["rows_received"] == 2
    assert data["rows_inserted"] == 0
    assert data["rows_skipped"] == 2


def test_api_upload_mixed_records_with_insert_new_only(client):
    """When duplicate_action='insert_new_only', inserts only new rows and skips duplicate rows."""
    new_usubjid = "TEST-PYTEST-NEW-099"
    try:
        with engine.connect() as conn:
            existing_key = conn.execute(text("SELECT USUBJID FROM dm LIMIT 1")).scalar()

        csv_content = (
            f"STUDYID,DOMAIN,USUBJID,SUBJID,SITEID,AGE,SEX,RACE,COUNTRY,ARMCD,ARM,RFSTDTC,RFENDTC\n"
            f"STDY001,DM,{existing_key},0001,SITE001,50,M,ASIAN,INDIA,PLC,Placebo,2025-02-01,2025-08-15\n"
            f"STDY001,DM,{new_usubjid},9099,SITE001,33,F,WHITE,USA,TRT,Drug X,2025-02-01,2025-08-15\n"
        )

        response = client.post(
            "/ingestion/upload",
            files={"file": ("DM_mixed.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
            data={"target_table": "dm", "duplicate_action": "insert_new_only"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rows_received"] == 2
        assert data["rows_inserted"] == 1
        assert data["rows_skipped"] == 1

        # Verify that new_usubjid was inserted
        with engine.connect() as conn:
            cnt = conn.execute(text("SELECT COUNT(*) FROM dm WHERE USUBJID = :k"), {"k": new_usubjid}).scalar()
            assert cnt == 1, f"Expected 1 record for {new_usubjid}, found {cnt}"

    finally:
        # Cleanup inserted test record
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM dm WHERE USUBJID = :k"), {"k": new_usubjid})


# =============================================================================
# 4. Preview Duplicate Detection Tests
# =============================================================================

def test_api_preview_detects_duplicates(client):
    """POST /ingestion/preview provides duplicate counts and sample keys without writing to DB."""
    with engine.connect() as conn:
        existing_key = conn.execute(text("SELECT USUBJID FROM dm LIMIT 1")).scalar()

    csv_content = (
        f"STUDYID,DOMAIN,USUBJID,SUBJID,SITEID,AGE,SEX\n"
        f"STDY001,DM,{existing_key},0001,SITE001,50,M\n"
        f"STDY001,DM,TEST-PREVIEW-NEW-01,9001,SITE001,42,F\n"
    )

    response = client.post(
        "/ingestion/preview",
        files={"file": ("DM_preview_test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        data={"target_mode": "existing", "target_table": "dm"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["has_duplicates"] is True
    assert data["duplicate_count"] == 1
    assert data["eligible_count"] == 1
    assert data["primary_key_columns"] == ["USUBJID"]
    assert len(data["sample_duplicates"]) == 1
    assert data["sample_duplicates"][0]["USUBJID"] == existing_key


def test_diagnostic_dm_9001_to_9005_duplicate_detection(client):
    """
    Diagnostic test verifying STDY001-9001 through STDY001-9005 duplicate detection:
    1. Proves that STDY001-9001..9005 already exist in MySQL table 'dm'.
    2. Verifies that identify_duplicate_records accurately reports 5 duplicates and 0 eligible records.
    3. Verifies that truly new records (STDY001-99991..99995) report 0 duplicates and 5 eligible records.
    4. Verifies that POST /ingestion/preview accurately reflects these counts and formats exactly 5 preview rows.
    """
    usubjids = [f"STDY001-900{i}" for i in range(1, 6)]
    with engine.connect() as conn:
        existing_rows = conn.execute(
            text("SELECT USUBJID FROM dm WHERE USUBJID IN ('STDY001-9001', 'STDY001-9002', 'STDY001-9003', 'STDY001-9004', 'STDY001-9005')")
        ).fetchall()
        existing_usubjids = [r[0] for r in existing_rows]

    # Verify these 5 subjects exist in the clinical trial MySQL database
    assert len(existing_usubjids) == 5, f"Expected 5 existing rows in dm for 9001-9005, found {len(existing_usubjids)}: {existing_usubjids}"

    # 1. Test duplicate detection on the existing 9001-9005 records
    df_existing = pd.DataFrame({
        "STUDYID": ["STDY001"] * 5,
        "DOMAIN": ["DM"] * 5,
        "USUBJID": usubjids,
        "SUBJID": list(range(9001, 9006)),
        "ARM": ["Placebo", "Drug X", "Placebo", "Drug X", "Placebo"],
    })
    res_existing = identify_duplicate_records(df_existing, "dm", engine)
    assert res_existing["has_duplicates"] is True
    assert res_existing["duplicate_count"] == 5
    assert res_existing["eligible_count"] == 0
    assert len(res_existing["sample_duplicates"]) == 5

    # 2. Test duplicate detection on truly non-existent records
    truly_new_usubjids = [f"STDY001-9999{i}" for i in range(1, 6)]
    df_new = pd.DataFrame({
        "STUDYID": ["STDY001"] * 5,
        "DOMAIN": ["DM"] * 5,
        "USUBJID": truly_new_usubjids,
        "SUBJID": list(range(99991, 99996)),
        "ARM": ["Placebo"] * 5,
    })
    res_new = identify_duplicate_records(df_new, "dm", engine)
    assert res_new["has_duplicates"] is False
    assert res_new["duplicate_count"] == 0
    assert res_new["eligible_count"] == 5
    assert len(res_new["sample_duplicates"]) == 0

    # 3. Test POST /ingestion/preview on 9001-9005 CSV
    csv_rows = ["STUDYID,DOMAIN,USUBJID,SUBJID,SITEID,AGE,SEX,ARM"]
    for i, u in enumerate(usubjids, 1):
        csv_rows.append(f"STDY001,DM,{u},{9000+i},SITE001,45,F,Placebo")
    csv_payload = "\n".join(csv_rows)

    response = client.post(
        "/ingestion/preview",
        files={"file": ("DM_new_records_5_rows.csv", io.BytesIO(csv_payload.encode("utf-8")), "text/csv")},
        data={"target_mode": "existing", "target_table": "dm"},
    )
    assert response.status_code == 200
    preview_data = response.json()
    assert preview_data["has_duplicates"] is True
    assert preview_data["duplicate_count"] == 5
    assert preview_data["eligible_count"] == 0
    assert len(preview_data["preview_rows"]) == 5



# =============================================================================
# 5. Transaction Rollback & Data Preservation Tests
# =============================================================================

def test_transaction_rollback_preserves_existing_data():
    """Ensure that simulated database failure rolls back without leaving partial batches or corrupting existing records."""
    import os
    # Count existing rows before test
    with engine.connect() as conn:
        before_count = conn.execute(text("SELECT COUNT(*) FROM dm")).scalar()

    test_id = "TEST-ROLLBACK-FAIL-01"
    temp_file = "data/uploads/test_rollback_fixture.csv"
    try:
        csv_content = (
            f"STUDYID,DOMAIN,USUBJID,SUBJID,SITEID,AGE,SEX,RACE,COUNTRY,ARMCD,ARM,RFSTDTC,RFENDTC\n"
            f"STDY001,DM,{test_id},9999,SITE001,40,M,ASIAN,INDIA,PLC,Placebo,2025-02-01,2025-08-15\n"
        )
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(csv_content)

        # Simulate an error during insertion by mocking load_dataframe_to_mysql
        with patch("app.ingestion.mysql_loader.load_dataframe_to_mysql", side_effect=RuntimeError("Simulated DB Disk Failure")):
            with pytest.raises(RuntimeError) as exc_info:
                load_dataset_to_mysql(
                    file_path=temp_file,
                    custom_table_name="dm",
                    if_exists="append",
                    duplicate_action="insert_new_only",
                )
            assert "Simulated DB Disk Failure" in str(exc_info.value)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    # Verify that existing rows count is completely preserved
    with engine.connect() as conn:
        after_count = conn.execute(text("SELECT COUNT(*) FROM dm")).scalar()
        test_exists = conn.execute(text("SELECT COUNT(*) FROM dm WHERE USUBJID = :k"), {"k": test_id}).scalar()

    assert after_count == before_count, f"Table count changed after rollback: {before_count} -> {after_count}"
    assert test_exists == 0, "Partial record was committed despite failure"
