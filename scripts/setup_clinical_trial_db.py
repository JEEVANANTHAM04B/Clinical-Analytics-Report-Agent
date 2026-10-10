"""
scripts/setup_clinical_trial_db.py
==================================
Dual-Database Safe Migration & Loader:
- Preserves original `clinical_analytics_db` with its healthcare tables and metadata.
- Creates separate new database `clinical_trial_analytics_db`.
- Creates all 13 clinical tables with PKs, FKs, and clinical indexes.
- Creates and populates infrastructure tables (dataset_versions, dataset_columns, approved_relationships, audit_logs).
- Loads all 13 CSVs from Dataset.zip in strict dependency order.
- Validates data integrity, uniqueness, and referential relationships.
"""

import os
import sys
import zipfile
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath("."))

import pandas as pd
import pymysql
import pymysql.cursors
from app.config import settings

NEW_DB_NAME = "clinical_trial_analytics_db"
OLD_DB_NAME = "clinical_analytics_db"

ZIP_PATH = os.path.abspath("Dataset.zip")
CLINICAL_DATA_DIR = os.path.abspath("data/clinical_trials")

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

SCHEMA_DDL = {
    # Infrastructure tables
    "dataset_versions": """
        CREATE TABLE IF NOT EXISTS `dataset_versions` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `dataset_name` VARCHAR(100) NOT NULL,
            `source_filename` VARCHAR(255) NOT NULL,
            `source_file_type` VARCHAR(20) NOT NULL,
            `version_number` INT NOT NULL DEFAULT 1,
            `row_count` INT NOT NULL,
            `column_count` INT NOT NULL,
            `status` VARCHAR(50) NOT NULL DEFAULT 'LOADED',
            `loaded_at` DATETIME NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            INDEX `ix_dataset_versions_dataset_name` (`dataset_name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "dataset_columns": """
        CREATE TABLE IF NOT EXISTS `dataset_columns` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `dataset_version_id` INT NOT NULL,
            `dataset_name` VARCHAR(100) NOT NULL,
            `column_name` VARCHAR(100) NOT NULL,
            `data_type` VARCHAR(100) NOT NULL,
            `semantic_type` VARCHAR(50) NOT NULL,
            `nullable` TINYINT(1) NOT NULL DEFAULT 1,
            `missing_count` INT NOT NULL DEFAULT 0,
            `missing_percentage` FLOAT NOT NULL DEFAULT 0.0,
            `is_primary_key_candidate` TINYINT(1) NOT NULL DEFAULT 0,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            INDEX `ix_dataset_columns_dataset_version_id` (`dataset_version_id`),
            INDEX `ix_dataset_columns_dataset_name` (`dataset_name`),
            CONSTRAINT `fk_dataset_columns_version` FOREIGN KEY (`dataset_version_id`) REFERENCES `dataset_versions` (`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "approved_relationships": """
        CREATE TABLE IF NOT EXISTS `approved_relationships` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `parent_table` VARCHAR(100) NOT NULL,
            `parent_column` VARCHAR(100) NOT NULL,
            `child_table` VARCHAR(100) NOT NULL,
            `child_column` VARCHAR(100) NOT NULL,
            `status` VARCHAR(50) NOT NULL DEFAULT 'APPROVED',
            `analyst_note` TEXT NULL,
            `was_edited` TINYINT(1) NOT NULL DEFAULT 0,
            `original_candidate` VARCHAR(255) NULL,
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "audit_logs": """
        CREATE TABLE IF NOT EXISTS `audit_logs` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `action` VARCHAR(100) NOT NULL,
            `entity_type` VARCHAR(100) NOT NULL,
            `entity_name` VARCHAR(255) NOT NULL,
            `status` VARCHAR(50) NOT NULL,
            `message` TEXT NULL,
            `user_agent` VARCHAR(100) NULL DEFAULT 'Clinical Analytics API',
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    # 13 Clinical Tables
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

CLINICAL_APPROVED_RELATIONSHIPS = [
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

def ensure_extracted_csvs():
    os.makedirs(CLINICAL_DATA_DIR, exist_ok=True)
    if os.path.exists(ZIP_PATH):
        print(f"Checking CSVs in {CLINICAL_DATA_DIR}...")
        with zipfile.ZipFile(ZIP_PATH, 'r') as z:
            for member in z.namelist():
                if member.lower().endswith(".csv") and "tlf" not in member.lower():
                    basename = os.path.basename(member)
                    target = os.path.join(CLINICAL_DATA_DIR, basename)
                    if not os.path.exists(target) or os.path.getsize(target) == 0:
                        with z.open(member) as source, open(target, "wb") as dest:
                            dest.write(source.read())
                        print(f"  Extracted: {basename} -> {target}")
                    else:
                        print(f"  Already exists: {basename}")

def main():
    print("="*80)
    print("PHASE 1: PRESERVE & CLEANUP EXISTING DATABASE")
    print("="*80)

    server_conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        autocommit=True
    )
    cursor = server_conn.cursor()

    # Verify and maintain old database
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{OLD_DB_NAME}` DEFAULT CHARACTER SET utf8mb4;")
    cursor.execute(f"USE `{OLD_DB_NAME}`;")

    # Drop only clinical trial tables from old database if any were created during prior tests
    # so old database remains pure EHR healthcare database
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for tbl, _ in DATASET_LOAD_ORDER:
        cursor.execute(f"DROP TABLE IF EXISTS `{tbl}`;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    cursor.execute("SHOW TABLES;")
    old_tables = [r[0] for r in cursor.fetchall()]
    print(f"Preserved tables in `{OLD_DB_NAME}`: {old_tables}")
    for t in old_tables:
        cursor.execute(f"SELECT COUNT(*) FROM `{t}`;")
        print(f"  {t}: {cursor.fetchone()[0]:,} rows")

    print("\n" + "="*80)
    print("PHASE 4: CREATE SEPARATE CLINICAL TRIAL DATABASE")
    print("="*80)
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{NEW_DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    print(f"Database `{NEW_DB_NAME}` created/verified successfully.")
    cursor.execute(f"USE `{NEW_DB_NAME}`;")

    print("\n" + "="*80)
    print("PHASE 5: CREATE TABLES (INFRASTRUCTURE + 13 CLINICAL DOMAINS)")
    print("="*80)
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for tbl, ddl in SCHEMA_DDL.items():
        cursor.execute(ddl)
        print(f"  Verified schema for `{tbl}`")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    print("\n" + "="*80)
    print("PHASE 7: LOAD CLINICAL TRIAL CSV DATA")
    print("="*80)
    ensure_extracted_csvs()

    for tbl_name, csv_file in DATASET_LOAD_ORDER:
        csv_path = os.path.join(CLINICAL_DATA_DIR, csv_file)
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Missing required CSV: {csv_path}")

        df = pd.read_csv(csv_path)
        initial_count = len(df)

        # Date formatting for study
        if tbl_name == "study":
            for d_col in ["START_DATE", "END_DATE"]:
                if d_col in df.columns:
                    df[d_col] = pd.to_datetime(df[d_col], format="%d-%m-%Y").dt.strftime("%Y-%m-%d")

        cols = list(df.columns)
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join([f"`{c}`" for c in cols])
        insert_sql = f"INSERT INTO `{tbl_name}` ({col_names}) VALUES ({placeholders})"

        records = df.where(pd.notnull(df), None).values.tolist()

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute(f"TRUNCATE TABLE `{tbl_name}`;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        batch_size = 2000
        total_inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
            total_inserted += len(batch)

        print(f"  Loaded `{tbl_name}`: {total_inserted:,} rows inserted (expected {initial_count:,})")

    print("\n" + "="*80)
    print("POPULATING INFRASTRUCTURE METADATA TABLES")
    print("="*80)
    # Populate approved_relationships
    for p_t, p_c, c_t, c_c in CLINICAL_APPROVED_RELATIONSHIPS:
        cursor.execute("""
            INSERT INTO `approved_relationships`
            (`parent_table`, `parent_column`, `child_table`, `child_column`, `status`, `analyst_note`, `was_edited`, `created_at`)
            VALUES (%s, %s, %s, %s, 'APPROVED', 'CDISC SDTM/ADaM clinical relational model', 0, NOW())
        """, (p_t, p_c, c_t, c_c))
    print(f"  Registered {len(CLINICAL_APPROVED_RELATIONSHIPS)} approved relationships.")

    # Populate dataset_versions and dataset_columns
    for tbl_name, csv_file in DATASET_LOAD_ORDER:
        csv_path = os.path.join(CLINICAL_DATA_DIR, csv_file)
        df = pd.read_csv(csv_path)

        cursor.execute("""
            INSERT INTO `dataset_versions`
            (`dataset_name`, `source_filename`, `source_file_type`, `version_number`, `row_count`, `column_count`, `status`, `loaded_at`, `created_at`)
            VALUES (%s, %s, '.csv', 1, %s, %s, 'LOADED', NOW(), NOW())
        """, (tbl_name, csv_file, len(df), len(df.columns)))
        v_id = cursor.lastrowid

        for col in df.columns:
            s = df[col]
            null_count = int(s.isna().sum())
            null_pct = float((null_count / len(df)) * 100) if len(df) > 0 else 0.0

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
            """, (v_id, tbl_name, col, sql_type, sem_type, (null_count > 0), null_count, null_pct, (null_count == 0)))
    print(f"  Populated dataset_versions and dataset_columns metadata.")

    # Audit log
    cursor.execute("""
        INSERT INTO `audit_logs`
        (`action`, `entity_type`, `entity_name`, `status`, `message`, `user_agent`, `created_at`)
        VALUES ('DATABASE_MIGRATION', 'DATABASE', %s, 'SUCCESS', 'Initialized clinical_trial_analytics_db with 13 tables', 'Setup Script', NOW())
    """, (NEW_DB_NAME,))
    print(f"  Inserted migration audit log.")

    print("\n" + "="*80)
    print("PHASE 8: VALIDATE NEW DATABASE INTEGRITY")
    print("="*80)
    for tbl_name, _ in DATASET_LOAD_ORDER:
        cursor.execute(f"SELECT COUNT(*) FROM `{tbl_name}`;")
        cnt = cursor.fetchone()[0]
        cursor.execute(f"SHOW COLUMNS FROM `{tbl_name}`;")
        cols = cursor.fetchall()
        print(f"  Table `{tbl_name}`: {cnt:,} rows, {len(cols)} columns")

    print("\nValidating Foreign Key / Relational Integrity:")
    for p_tbl, p_col, c_tbl, c_col in CLINICAL_APPROVED_RELATIONSHIPS:
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM `{c_tbl}` c
            LEFT JOIN `{p_tbl}` p ON c.`{p_col}` = p.`{p_col}`
            WHERE p.`{p_col}` IS NULL;
        """)
        orphans = cursor.fetchone()[0]
        print(f"  {p_tbl}.{p_col} -> {c_tbl}.{c_col}: {orphans} orphans")
        if orphans > 0:
            raise ValueError(f"Orphans detected in relationship {p_tbl} -> {c_tbl}!")

    server_conn.close()
    print("\nMigration to `clinical_trial_analytics_db` complete and verified 100%!")

if __name__ == "__main__":
    main()
