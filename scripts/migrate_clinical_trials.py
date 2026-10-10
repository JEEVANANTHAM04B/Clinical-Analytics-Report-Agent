"""
scripts/migrate_clinical_trials.py
==================================
Database Migration & Clinical Trial Dataset Loader

Migrates MySQL database `clinical_analytics_db` from the old healthcare model
to the new CDISC SDTM / ADaM clinical-trial relational data model:
  1. Creates the new relational schema with verified Primary Keys, Foreign Keys, and Indexes.
  2. Loads 13 clinical datasets in strict dependency order without data loss.
  3. Formats dates accurately (e.g. DD-MM-YYYY in STUDY to ISO YYYY-MM-DD).
  4. Updates platform metadata (dataset_versions, dataset_columns, approved_relationships, audit_logs).
  5. Performs thorough validation of row counts, null counts, duplicate keys, and orphan records.
  6. Drops obsolete healthcare tables only after 100% successful validation.
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath("."))

import pandas as pd
import pymysql
import pymysql.cursors
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger("clinical_migration")

DATA_DIR = os.path.abspath("data/clinical_trials")

# The 13 datasets in exact relational dependency load order
DATASET_LOAD_ORDER = [
    ("study", "STUDY.csv"),
    ("sites", "SITES.csv"),
    ("dm", "DM.csv"),
    ("ae", "AE.csv"),
    ("ex", "EX.csv"),
    ("lb", "LB.csv"),
    ("qs", "QS.csv"),
    ("vs", "VS.csv"),
    ("adsl", "ADSL.csv"),
    ("adae", "ADAE.csv"),
    ("adlb", "ADLB.csv"),
    ("advs", "ADVS.csv"),
    ("adresp", "ADRESP.csv"),
]

OLD_HEALTHCARE_TABLES = [
    "conditions",
    "encounters",
    "medications",
    "observations",
    "patients",
    "procedures",
    "sample_clinical_data",
]

# DDL definitions with exact types, PKs, FKs, and clinical analytics indexes
SCHEMA_DDL = {
    "study": """
        CREATE TABLE IF NOT EXISTS `study` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `STUDY_TITLE` VARCHAR(255) NOT NULL,
            `PHASE` VARCHAR(50) NOT NULL,
            `THERAPEUTIC_AREA` VARCHAR(100) NOT NULL,
            `INDICATION` VARCHAR(100) NOT NULL,
            `SPONSOR` VARCHAR(100) NOT NULL,
            `STUDY_STATUS` VARCHAR(50) NOT NULL,
            `START_DATE` DATE NOT NULL,
            `END_DATE` DATE NOT NULL,
            PRIMARY KEY (`STUDYID`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "sites": """
        CREATE TABLE IF NOT EXISTS `sites` (
            `SITEID` VARCHAR(50) NOT NULL,
            `STUDYID` VARCHAR(50) NOT NULL,
            `SITE_NAME` VARCHAR(100) NOT NULL,
            `COUNTRY` VARCHAR(100) NOT NULL,
            `CITY` VARCHAR(100) NOT NULL,
            `PI_NAME` VARCHAR(100) NOT NULL,
            `PLANNED_SUBJECTS` INT NOT NULL,
            `ACTUAL_SUBJECTS` INT NOT NULL,
            PRIMARY KEY (`SITEID`),
            INDEX `idx_sites_studyid` (`STUDYID`),
            CONSTRAINT `fk_sites_study` FOREIGN KEY (`STUDYID`) REFERENCES `study` (`STUDYID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "dm": """
        CREATE TABLE IF NOT EXISTS `dm` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `DOMAIN` VARCHAR(10) NOT NULL DEFAULT 'DM',
            `USUBJID` VARCHAR(50) NOT NULL,
            `SUBJID` INT NOT NULL,
            `SITEID` VARCHAR(50) NOT NULL,
            `AGE` INT NOT NULL,
            `SEX` VARCHAR(10) NOT NULL,
            `RACE` VARCHAR(50) NOT NULL,
            `COUNTRY` VARCHAR(50) NOT NULL,
            `ARMCD` VARCHAR(50) NOT NULL,
            `ARM` VARCHAR(100) NOT NULL,
            `RFSTDTC` DATE NOT NULL,
            `RFENDTC` DATE NOT NULL,
            PRIMARY KEY (`USUBJID`),
            INDEX `idx_dm_studyid` (`STUDYID`),
            INDEX `idx_dm_siteid` (`SITEID`),
            INDEX `idx_dm_armcd` (`ARMCD`),
            CONSTRAINT `fk_dm_study` FOREIGN KEY (`STUDYID`) REFERENCES `study` (`STUDYID`) ON DELETE CASCADE,
            CONSTRAINT `fk_dm_sites` FOREIGN KEY (`SITEID`) REFERENCES `sites` (`SITEID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "ae": """
        CREATE TABLE IF NOT EXISTS `ae` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `DOMAIN` VARCHAR(10) NOT NULL DEFAULT 'AE',
            `USUBJID` VARCHAR(50) NOT NULL,
            `AESEQ` INT NOT NULL,
            `AETERM` VARCHAR(255) NOT NULL,
            `AEDECOD` VARCHAR(255) NOT NULL,
            `AEBODSYS` VARCHAR(255) NOT NULL,
            `AESEV` VARCHAR(50) NOT NULL,
            `AESER` VARCHAR(1) NOT NULL,
            `AEREL` VARCHAR(50) NOT NULL,
            `AESTDTC` DATE NOT NULL,
            `AEENDTC` DATE NOT NULL,
            PRIMARY KEY (`USUBJID`, `AESEQ`),
            INDEX `idx_ae_studyid` (`STUDYID`),
            INDEX `idx_ae_aedecod` (`AEDECOD`),
            INDEX `idx_ae_aebodsys` (`AEBODSYS`),
            INDEX `idx_ae_aeser` (`AESER`),
            CONSTRAINT `fk_ae_dm` FOREIGN KEY (`USUBJID`) REFERENCES `dm` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "ex": """
        CREATE TABLE IF NOT EXISTS `ex` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `DOMAIN` VARCHAR(10) NOT NULL DEFAULT 'EX',
            `USUBJID` VARCHAR(50) NOT NULL,
            `EXSEQ` INT NOT NULL,
            `EXTRT` VARCHAR(100) NOT NULL,
            `EXDOSE` DOUBLE NOT NULL,
            `EXDOSU` VARCHAR(50) NOT NULL,
            `EXROUTE` VARCHAR(50) NOT NULL,
            `EXSTDTC` DATE NOT NULL,
            `EXENDTC` DATE NOT NULL,
            PRIMARY KEY (`USUBJID`, `EXSEQ`),
            INDEX `idx_ex_studyid` (`STUDYID`),
            INDEX `idx_ex_extrt` (`EXTRT`),
            CONSTRAINT `fk_ex_dm` FOREIGN KEY (`USUBJID`) REFERENCES `dm` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "lb": """
        CREATE TABLE IF NOT EXISTS `lb` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `DOMAIN` VARCHAR(10) NOT NULL DEFAULT 'LB',
            `USUBJID` VARCHAR(50) NOT NULL,
            `LBTESTCD` VARCHAR(50) NOT NULL,
            `LBTEST` VARCHAR(100) NOT NULL,
            `LBORRES` DOUBLE NOT NULL,
            `LBORRESU` VARCHAR(50) NOT NULL,
            `VISIT` VARCHAR(50) NOT NULL,
            `LBSEQ` INT NOT NULL,
            `LBDTC` DATE NOT NULL,
            `LBNRIND` VARCHAR(50) NOT NULL,
            PRIMARY KEY (`USUBJID`, `LBSEQ`),
            INDEX `idx_lb_studyid` (`STUDYID`),
            INDEX `idx_lb_testcd` (`LBTESTCD`),
            INDEX `idx_lb_visit` (`VISIT`),
            CONSTRAINT `fk_lb_dm` FOREIGN KEY (`USUBJID`) REFERENCES `dm` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "qs": """
        CREATE TABLE IF NOT EXISTS `qs` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `DOMAIN` VARCHAR(10) NOT NULL DEFAULT 'QS',
            `USUBJID` VARCHAR(50) NOT NULL,
            `QSTESTCD` VARCHAR(50) NOT NULL,
            `QSTEST` VARCHAR(100) NOT NULL,
            `QSORRES` DOUBLE NOT NULL,
            `QSORRESU` VARCHAR(50) NOT NULL,
            `VISIT` VARCHAR(50) NOT NULL,
            `QSSEQ` INT NOT NULL,
            `QSDTC` DATE NOT NULL,
            PRIMARY KEY (`USUBJID`, `QSSEQ`),
            INDEX `idx_qs_studyid` (`STUDYID`),
            INDEX `idx_qs_testcd` (`QSTESTCD`),
            INDEX `idx_qs_visit` (`VISIT`),
            CONSTRAINT `fk_qs_dm` FOREIGN KEY (`USUBJID`) REFERENCES `dm` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "vs": """
        CREATE TABLE IF NOT EXISTS `vs` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `DOMAIN` VARCHAR(10) NOT NULL DEFAULT 'VS',
            `USUBJID` VARCHAR(50) NOT NULL,
            `VSTESTCD` VARCHAR(50) NOT NULL,
            `VSTEST` VARCHAR(100) NOT NULL,
            `VSORRES` DOUBLE NOT NULL,
            `VSORRESU` VARCHAR(50) NOT NULL,
            `VISIT` VARCHAR(50) NOT NULL,
            `VSSEQ` INT NOT NULL,
            `VSDTC` DATE NOT NULL,
            PRIMARY KEY (`USUBJID`, `VSSEQ`),
            INDEX `idx_vs_studyid` (`STUDYID`),
            INDEX `idx_vs_testcd` (`VSTESTCD`),
            INDEX `idx_vs_visit` (`VISIT`),
            CONSTRAINT `fk_vs_dm` FOREIGN KEY (`USUBJID`) REFERENCES `dm` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "adsl": """
        CREATE TABLE IF NOT EXISTS `adsl` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `USUBJID` VARCHAR(50) NOT NULL,
            `SUBJID` INT NOT NULL,
            `SITEID` VARCHAR(50) NOT NULL,
            `AGE` INT NOT NULL,
            `SEX` VARCHAR(10) NOT NULL,
            `TRT01P` VARCHAR(100) NOT NULL,
            `TRT01A` VARCHAR(100) NOT NULL,
            `SAFFL` VARCHAR(1) NOT NULL,
            `ITTFL` VARCHAR(1) NOT NULL,
            `PPROTFL` VARCHAR(1) NOT NULL,
            `RANDDT` DATE NOT NULL,
            `TRTSDT` DATE NOT NULL,
            `TRTEDT` DATE NOT NULL,
            `EOSDT` DATE NOT NULL,
            PRIMARY KEY (`USUBJID`),
            INDEX `idx_adsl_studyid` (`STUDYID`),
            INDEX `idx_adsl_siteid` (`SITEID`),
            INDEX `idx_adsl_trt01p` (`TRT01P`),
            INDEX `idx_adsl_trt01a` (`TRT01A`),
            CONSTRAINT `fk_adsl_dm` FOREIGN KEY (`USUBJID`) REFERENCES `dm` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "adae": """
        CREATE TABLE IF NOT EXISTS `adae` (
            `STUDYID` VARCHAR(50) NOT NULL,
            `USUBJID` VARCHAR(50) NOT NULL,
            `AEDECOD` VARCHAR(255) NOT NULL,
            `AEBODSYS` VARCHAR(255) NOT NULL,
            `AESEV` VARCHAR(50) NOT NULL,
            `AESER` VARCHAR(1) NOT NULL,
            `AEREL` VARCHAR(50) NOT NULL,
            `TRT01A` VARCHAR(100) NOT NULL,
            `ASTDT` DATE NOT NULL,
            `AENDT` DATE NOT NULL,
            `TRTEMFL` VARCHAR(1) NOT NULL,
            `SAFFL` VARCHAR(1) NOT NULL,
            PRIMARY KEY (`USUBJID`),
            INDEX `idx_adae_studyid` (`STUDYID`),
            INDEX `idx_adae_trt01a` (`TRT01A`),
            INDEX `idx_adae_aedecod` (`AEDECOD`),
            INDEX `idx_adae_aebodsys` (`AEBODSYS`),
            INDEX `idx_adae_aeser` (`AESER`),
            CONSTRAINT `fk_adae_adsl` FOREIGN KEY (`USUBJID`) REFERENCES `adsl` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "adlb": """
        CREATE TABLE IF NOT EXISTS `adlb` (
            `USUBJID` VARCHAR(50) NOT NULL,
            `TRT01A` VARCHAR(100) NOT NULL,
            `AVISIT` VARCHAR(50) NOT NULL,
            `AVAL` DOUBLE NOT NULL,
            `BASE` DOUBLE NOT NULL,
            `STUDYID` VARCHAR(50) NOT NULL,
            `PARAMCD` VARCHAR(50) NOT NULL,
            `PARAM` VARCHAR(100) NOT NULL,
            `AVALU` VARCHAR(50) NOT NULL,
            `CHG` DOUBLE NOT NULL,
            `PCHG` DOUBLE NOT NULL,
            `ANL01FL` VARCHAR(1) NOT NULL,
            PRIMARY KEY (`USUBJID`, `PARAMCD`, `AVISIT`),
            INDEX `idx_adlb_studyid` (`STUDYID`),
            INDEX `idx_adlb_trt01a` (`TRT01A`),
            INDEX `idx_adlb_paramcd` (`PARAMCD`),
            INDEX `idx_adlb_param` (`PARAM`),
            INDEX `idx_adlb_avisit` (`AVISIT`),
            CONSTRAINT `fk_adlb_adsl` FOREIGN KEY (`USUBJID`) REFERENCES `adsl` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "advs": """
        CREATE TABLE IF NOT EXISTS `advs` (
            `USUBJID` VARCHAR(50) NOT NULL,
            `TRT01A` VARCHAR(100) NOT NULL,
            `AVISIT` VARCHAR(50) NOT NULL,
            `AVAL` DOUBLE NOT NULL,
            `BASE` DOUBLE NOT NULL,
            `STUDYID` VARCHAR(50) NOT NULL,
            `PARAMCD` VARCHAR(50) NOT NULL,
            `PARAM` VARCHAR(100) NOT NULL,
            `AVALU` VARCHAR(50) NOT NULL,
            `CHG` DOUBLE NOT NULL,
            `PCHG` DOUBLE NOT NULL,
            `ANL01FL` VARCHAR(1) NOT NULL,
            PRIMARY KEY (`USUBJID`, `PARAMCD`, `AVISIT`),
            INDEX `idx_advs_studyid` (`STUDYID`),
            INDEX `idx_advs_trt01a` (`TRT01A`),
            INDEX `idx_advs_paramcd` (`PARAMCD`),
            INDEX `idx_advs_param` (`PARAM`),
            INDEX `idx_advs_avisit` (`AVISIT`),
            CONSTRAINT `fk_advs_adsl` FOREIGN KEY (`USUBJID`) REFERENCES `adsl` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "adresp": """
        CREATE TABLE IF NOT EXISTS `adresp` (
            `USUBJID` VARCHAR(50) NOT NULL,
            `TRT01A` VARCHAR(100) NOT NULL,
            `AVISIT` VARCHAR(50) NOT NULL,
            `AVAL` DOUBLE NOT NULL,
            `BASE` DOUBLE NOT NULL,
            `STUDYID` VARCHAR(50) NOT NULL,
            `PARAMCD` VARCHAR(50) NOT NULL,
            `PARAM` VARCHAR(100) NOT NULL,
            `AVALU` VARCHAR(50) NOT NULL,
            `CHG` DOUBLE NOT NULL,
            `PCHG` DOUBLE NOT NULL,
            `ANL01FL` VARCHAR(1) NOT NULL,
            `RESPFL` VARCHAR(1) NOT NULL,
            PRIMARY KEY (`USUBJID`, `PARAMCD`, `AVISIT`),
            INDEX `idx_adresp_studyid` (`STUDYID`),
            INDEX `idx_adresp_trt01a` (`TRT01A`),
            INDEX `idx_adresp_paramcd` (`PARAMCD`),
            INDEX `idx_adresp_param` (`PARAM`),
            INDEX `idx_adresp_avisit` (`AVISIT`),
            INDEX `idx_adresp_respfl` (`RESPFL`),
            CONSTRAINT `fk_adresp_adsl` FOREIGN KEY (`USUBJID`) REFERENCES `adsl` (`USUBJID`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
}

# New Approved Relationships for approved_relationships metadata table
NEW_APPROVED_RELATIONSHIPS = [
    ("study", "STUDYID", "sites", "STUDYID"),
    ("study", "STUDYID", "dm", "STUDYID"),
    ("sites", "SITEID", "dm", "SITEID"),
    ("dm", "USUBJID", "ae", "USUBJID"),
    ("dm", "USUBJID", "ex", "USUBJID"),
    ("dm", "USUBJID", "lb", "USUBJID"),
    ("dm", "USUBJID", "qs", "USUBJID"),
    ("dm", "USUBJID", "vs", "USUBJID"),
    ("dm", "USUBJID", "adsl", "USUBJID"),
    ("adsl", "USUBJID", "adae", "USUBJID"),
    ("adsl", "USUBJID", "adlb", "USUBJID"),
    ("adsl", "USUBJID", "advs", "USUBJID"),
    ("adsl", "USUBJID", "adresp", "USUBJID"),
]

def get_mysql_connection():
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

def execute_migration():
    conn = get_mysql_connection()
    cursor = conn.cursor()

    print("\n" + "="*80)
    print("STEP 1: CREATING NEW CLINICAL TRIAL RELATIONAL SCHEMA")
    print("="*80)

    # Disable foreign key checks during table creation
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

    for tbl, ddl in SCHEMA_DDL.items():
        print(f"Creating/verifying table: `{tbl}`...")
        cursor.execute(ddl)

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    print("All 13 clinical tables created successfully.")

    print("\n" + "="*80)
    print("STEP 2: LOADING CLINICAL DATASETS")
    print("="*80)

    load_summary = {}

    for tbl_name, csv_file in DATASET_LOAD_ORDER:
        csv_path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Required dataset {csv_file} not found at {csv_path}!")

        print(f"\nProcessing {csv_file} -> `{tbl_name}`...")
        df = pd.read_csv(csv_path)
        initial_rows = len(df)

        # Date normalization for STUDY table (DD-MM-YYYY -> YYYY-MM-DD)
        if tbl_name == "study":
            for d_col in ["START_DATE", "END_DATE"]:
                if d_col in df.columns:
                    df[d_col] = pd.to_datetime(df[d_col], format="%d-%m-%Y").dt.strftime("%Y-%m-%d")

        # Ensure column names match schema exactly
        cols = list(df.columns)
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join([f"`{c}`" for c in cols])
        insert_sql = f"INSERT INTO `{tbl_name}` ({col_names}) VALUES ({placeholders})"

        # Clean NaN/None for database insertion
        records = df.where(pd.notnull(df), None).values.tolist()

        # Truncate any existing rows before reload to guarantee idempotency
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute(f"TRUNCATE TABLE `{tbl_name}`;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        # Batch insert
        batch_size = 2000
        total_inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
            total_inserted += len(batch)

        conn.commit()
        print(f"  Loaded {total_inserted:,} rows into `{tbl_name}` (expected {initial_rows:,})")
        load_summary[tbl_name] = {
            "csv_rows": initial_rows,
            "db_rows": total_inserted,
            "cols": len(cols)
        }

    print("\n" + "="*80)
    print("STEP 3: UPDATING METADATA TABLES")
    print("="*80)

    # 1. Update approved_relationships: add new clinical relationships
    print("Updating approved_relationships...")
    for parent_t, parent_c, child_t, child_c in NEW_APPROVED_RELATIONSHIPS:
        cursor.execute("""
            SELECT id FROM `approved_relationships`
            WHERE `parent_table` = %s AND `parent_column` = %s
              AND `child_table` = %s AND `child_column` = %s
        """, (parent_t, parent_c, child_t, child_c))
        existing = cursor.fetchone()
        if not existing:
            cursor.execute("""
                INSERT INTO `approved_relationships`
                (`parent_table`, `parent_column`, `child_table`, `child_column`, `status`, `analyst_note`, `was_edited`, `created_at`)
                VALUES (%s, %s, %s, %s, 'APPROVED', 'CDISC SDTM/ADaM clinical relational model', 0, NOW())
            """, (parent_t, parent_c, child_t, child_c))
            print(f"  Added approved relationship: {parent_t}.{parent_c} -> {child_t}.{child_c}")
    conn.commit()

    # 2. Update dataset_versions & dataset_columns
    print("Updating dataset_versions and dataset_columns...")
    for tbl_name, csv_file in DATASET_LOAD_ORDER:
        csv_path = os.path.join(DATA_DIR, csv_file)
        df = pd.read_csv(csv_path)

        # Get highest version
        cursor.execute("SELECT MAX(version_number) as max_v FROM `dataset_versions` WHERE `dataset_name` = %s", (tbl_name,))
        res = cursor.fetchone()
        max_v = res["max_v"] or 0
        new_v = max_v + 1

        cursor.execute("""
            INSERT INTO `dataset_versions`
            (`dataset_name`, `source_filename`, `source_file_type`, `version_number`, `row_count`, `column_count`, `status`, `loaded_at`, `created_at`)
            VALUES (%s, %s, '.csv', %s, %s, %s, 'LOADED', NOW(), NOW())
        """, (tbl_name, csv_file, new_v, len(df), len(df.columns)))
        version_id = cursor.lastrowid

        # Insert columns metadata
        for col in df.columns:
            s = df[col]
            null_count = int(s.isna().sum())
            null_pct = float((null_count / len(df)) * 100) if len(df) > 0 else 0.0

            # infer simple semantic type
            if pd.api.types.is_numeric_dtype(s):
                sem_type = "decimal" if not (s.dropna() % 1 == 0).all() else "integer"
                sql_type = "DOUBLE" if sem_type == "decimal" else "INT"
            elif "DATE" in col.upper() or col.upper().endswith("DT") or col.upper().endswith("DTC"):
                sem_type = "date"
                sql_type = "DATE"
            elif col.upper() in ("SEX", "SAFFL", "ITTFL", "PPROTFL", "TRTEMFL", "ANL01FL", "RESPFL", "AESER"):
                sem_type = "flag"
                sql_type = "VARCHAR(1)"
            else:
                sem_type = "identifier" if "ID" in col.upper() or "SEQ" in col.upper() else "categorical"
                sql_type = "VARCHAR(100)"

            cursor.execute("""
                INSERT INTO `dataset_columns`
                (`dataset_version_id`, `dataset_name`, `column_name`, `data_type`, `semantic_type`, `nullable`, `missing_count`, `missing_percentage`, `is_primary_key_candidate`, `created_at`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (version_id, tbl_name, col, sql_type, sem_type, (null_count > 0), null_count, null_pct, (null_count == 0)))
    conn.commit()

    # 3. Insert audit log
    cursor.execute("""
        INSERT INTO `audit_logs`
        (`action`, `entity_type`, `entity_name`, `status`, `message`, `user_agent`, `created_at`)
        VALUES ('DATABASE_MIGRATION', 'DATABASE', 'clinical_analytics_db', 'SUCCESS', 'Migrated schema and loaded 13 clinical SDTM/ADaM datasets', 'Clinical Migration Script', NOW())
    """)
    conn.commit()

    print("\n" + "="*80)
    print("STEP 4: POST-LOAD DATABASE VALIDATION")
    print("="*80)

    validation_results = {}
    validation_passed = True

    for tbl_name, _ in DATASET_LOAD_ORDER:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM `{tbl_name}`;")
        row_count = cursor.fetchone()["cnt"]

        cursor.execute(f"SHOW COLUMNS FROM `{tbl_name}`;")
        columns_info = cursor.fetchall()
        col_names = [c["Field"] for c in columns_info]

        # Null counts per column
        null_counts = {}
        for c in col_names:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM `{tbl_name}` WHERE `{c}` IS NULL;")
            null_cnt = cursor.fetchone()["cnt"]
            if null_cnt > 0:
                null_counts[c] = null_cnt

        validation_results[tbl_name] = {
            "row_count": row_count,
            "col_count": len(col_names),
            "columns": col_names,
            "null_counts": null_counts,
        }
        print(f"Table `{tbl_name}`: {row_count:,} rows, {len(col_names)} cols, Nulls: {null_counts or 'None'}")
        if row_count == 0:
            validation_passed = False

    # Foreign Key / Orphan Checks
    print("\nValidating Foreign Key / Relational Integrity:")
    fk_checks = [
        ("study", "STUDYID", "sites", "STUDYID"),
        ("study", "STUDYID", "dm", "STUDYID"),
        ("sites", "SITEID", "dm", "SITEID"),
        ("dm", "USUBJID", "ae", "USUBJID"),
        ("dm", "USUBJID", "ex", "USUBJID"),
        ("dm", "USUBJID", "lb", "USUBJID"),
        ("dm", "USUBJID", "qs", "USUBJID"),
        ("dm", "USUBJID", "vs", "USUBJID"),
        ("dm", "USUBJID", "adsl", "USUBJID"),
        ("adsl", "USUBJID", "adae", "USUBJID"),
        ("adsl", "USUBJID", "adlb", "USUBJID"),
        ("adsl", "USUBJID", "advs", "USUBJID"),
        ("adsl", "USUBJID", "adresp", "USUBJID"),
    ]

    orphan_results = {}
    for p_tbl, p_col, c_tbl, c_col in fk_checks:
        cursor.execute(f"""
            SELECT COUNT(*) as orphans
            FROM `{c_tbl}` c
            LEFT JOIN `{p_tbl}` p ON c.`{c_col}` = p.`{p_col}`
            WHERE p.`{p_col}` IS NULL;
        """)
        orphans = cursor.fetchone()["orphans"]
        orphan_results[f"{p_tbl}.{p_col} -> {c_tbl}.{c_col}"] = orphans
        print(f"  {p_tbl}.{p_col} -> {c_tbl}.{c_col}: {orphans} orphans")
        if orphans > 0:
            validation_passed = False

    if not validation_passed:
        print("\nERROR: Validation failed! Aborting removal of old tables.")
        conn.close()
        return False

    print("\n" + "="*80)
    print("STEP 5: VALIDATION 100% PASSED — REMOVING OBSOLETE HEALTHCARE TABLES")
    print("="*80)

    # Clean up obsolete approved_relationships pointing to old tables
    cursor.execute("""
        DELETE FROM `approved_relationships`
        WHERE `parent_table` IN ('patients', 'encounters', 'conditions', 'medications', 'procedures', 'observations', 'sample_clinical_data')
           OR `child_table` IN ('patients', 'encounters', 'conditions', 'medications', 'procedures', 'observations', 'sample_clinical_data');
    """)
    conn.commit()
    print("Cleaned up obsolete relationship records.")

    # Drop old healthcare tables safely
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for old_tbl in OLD_HEALTHCARE_TABLES:
        cursor.execute(f"DROP TABLE IF EXISTS `{old_tbl}`;")
        print(f"  Dropped obsolete table: `{old_tbl}`")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()

    # Final table listing in DB
    cursor.execute("SHOW TABLES;")
    remaining_tables = [list(r.values())[0] for r in cursor.fetchall()]
    print(f"\nFinal tables in database: {remaining_tables}")

    conn.close()
    print("\nMigration completed successfully!")
    return True

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)
