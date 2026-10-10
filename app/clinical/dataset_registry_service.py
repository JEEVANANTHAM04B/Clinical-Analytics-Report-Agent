"""
app/clinical/dataset_registry_service.py
=========================================
Authoritative Dataset Registry Service for Clinical Analytics.

Provides centralized classification, approval tracking, and schema validation
to distinguish approved CDISC/clinical datasets from temporary test and demo tables.
"""

from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.core.database import engine, Base, get_db_context
from app.core.logging_config import get_logger
from app.database.models import ClinicalDatasetRegistry

logger = get_logger(__name__)

# System metadata tables that must NEVER be treated as clinical datasets
METADATA_TABLES: Set[str] = {
    "dataset_versions",
    "dataset_columns",
    "approved_relationships",
    "audit_logs",
    "clinical_dataset_registry",
}

# Core approved clinical dataset catalog definitions
CORE_APPROVED_CLINICAL_CATALOG: Dict[str, Dict[str, str]] = {
    # SDTM
    "dm": {
        "display_name": "Demographics (DM)",
        "category": "SDTM",
        "description": "Subject demographics and baseline characteristics.",
    },
    "ae": {
        "display_name": "Adverse Events (AE)",
        "category": "SDTM",
        "description": "Reported adverse events and safety occurrences.",
    },
    "ex": {
        "display_name": "Exposure (EX)",
        "category": "SDTM",
        "description": "Study drug dosing and exposure records.",
    },
    "lb": {
        "display_name": "Laboratory Tests (LB)",
        "category": "SDTM",
        "description": "Clinical laboratory findings and pathology tests.",
    },
    "vs": {
        "display_name": "Vital Signs (VS)",
        "category": "SDTM",
        "description": "Vital signs measurements, blood pressure, and pulse.",
    },
    "qs": {
        "display_name": "Questionnaires (QS)",
        "category": "SDTM",
        "description": "Patient reported outcomes and questionnaires.",
    },
    # ADaM
    "adsl": {
        "display_name": "Subject-Level Analysis (ADSL)",
        "category": "ADaM",
        "description": "Primary subject-level analysis dataset with treatment arms.",
    },
    "adae": {
        "display_name": "Adverse Events Analysis (ADAE)",
        "category": "ADaM",
        "description": "Analysis-ready adverse events dataset with treatment emergent flags.",
    },
    "adlb": {
        "display_name": "Laboratory Analysis (ADLB)",
        "category": "ADaM",
        "description": "Analysis laboratory results with baseline and change values.",
    },
    "advs": {
        "display_name": "Vital Signs Analysis (ADVS)",
        "category": "ADaM",
        "description": "Analysis vital signs dataset with baseline change parameters.",
    },
    "adresp": {
        "display_name": "Response / Efficacy Analysis (ADRESP)",
        "category": "ADaM",
        "description": "Primary and secondary efficacy endpoints and responder indicators.",
    },
    # Clinical study metadata
    "study": {
        "display_name": "Study Protocol (STUDY)",
        "category": "Study Management",
        "description": "Overall study protocol metadata, phase, and therapeutic area.",
    },
    "sites": {
        "display_name": "Clinical Sites (SITES)",
        "category": "Study Management",
        "description": "Participating research centers and target enrollments.",
    },
}

# Known test and demonstration tables
KNOWN_TEST_DEMO_TABLES: Dict[str, Dict[str, str]] = {
    "sample_clinical_data": {
        "display_name": "Sample Clinical Data (Mock)",
        "classification": "DEMO",
        "approval_status": "PENDING",
        "category": "Demo",
        "description": "Synthetic mock dataset for local ingestion and format demonstration.",
    },
    "dup_cols_table": {
        "display_name": "Duplicate Columns Test",
        "classification": "TEST",
        "approval_status": "REJECTED",
        "category": "Testing",
        "description": "Temporary table for testing duplicate column rejection.",
    },
    "mixed_test_tbl": {
        "display_name": "Mixed Values Test",
        "classification": "TEST",
        "approval_status": "REJECTED",
        "category": "Testing",
        "description": "Temporary table for testing mixed type inference.",
    },
    "null_test_tbl": {
        "display_name": "Null Values Test",
        "classification": "TEST",
        "approval_status": "REJECTED",
        "category": "Testing",
        "description": "Temporary table for testing NULL preservation.",
    },
}

# Custom or unapproved datasets (preserved in database, but excluded from default clinical catalog)
CUSTOM_UNAPPROVED_DATASETS: Dict[str, Dict[str, str]] = {
    "biomarker_results": {
        "display_name": "Biomarker Results",
        "classification": "CUSTOM",
        "approval_status": "PENDING",
        "category": "Biomarkers",
        "description": "Biomarker concentrations, expression levels, and genetic variants (custom unapproved).",
    },
    "clinical_endpoints": {
        "display_name": "Clinical Endpoints",
        "classification": "CUSTOM",
        "approval_status": "PENDING",
        "category": "Clinical Endpoints",
        "description": "Primary and secondary efficacy endpoints and visit results (custom unapproved).",
    },
}


_is_initialized = False

def ensure_registry_initialized(force: bool = False) -> None:
    """
    Initializes the clinical_dataset_registry table in MySQL and seeds
    the authoritative catalog, verifying against actual MySQL tables.
    Runs once unless force=True.
    """
    global _is_initialized
    if _is_initialized and not force:
        return

    inspector = inspect(engine)

    # 1. Create table if not exists
    if not inspector.has_table("clinical_dataset_registry"):
        try:
            Base.metadata.create_all(bind=engine, tables=[ClinicalDatasetRegistry.__table__])
        except Exception as e:
            logger.warning(f"Error creating clinical_dataset_registry table: {e}")

    # 2. Inspect existing tables in MySQL
    inspector = inspect(engine)
    existing_db_tables = {t.lower(): t for t in inspector.get_table_names()}

    with get_db_context() as db:
        # Load currently registered entries
        try:
            current_entries = {
                r.dataset_name.lower(): r
                for r in db.query(ClinicalDatasetRegistry).all()
            }
        except Exception as e:
            logger.error(f"Failed to query clinical_dataset_registry: {e}")
            return

        # Seed core clinical catalog tables only if not already present
        for tbl_name, info in CORE_APPROVED_CLINICAL_CATALOG.items():
            tbl_lower = tbl_name.lower()
            if tbl_lower not in current_entries:
                new_entry = ClinicalDatasetRegistry(
                    dataset_name=tbl_lower,
                    display_name=info["display_name"],
                    classification="CLINICAL",
                    approval_status="APPROVED",
                    category=info["category"],
                    description=info["description"],
                )
                db.add(new_entry)

        # Classify known test and demonstration tables
        for test_tbl, t_info in KNOWN_TEST_DEMO_TABLES.items():
            test_lower = test_tbl.lower()
            if test_lower in current_entries:
                entry = current_entries[test_lower]
                entry.classification = t_info["classification"]
                entry.approval_status = t_info["approval_status"]
                entry.category = t_info["category"]
            else:
                new_test = ClinicalDatasetRegistry(
                    dataset_name=test_lower,
                    display_name=t_info["display_name"],
                    classification=t_info["classification"],
                    approval_status=t_info["approval_status"],
                    category=t_info["category"],
                    description=t_info["description"],
                )
                db.add(new_test)

        # Update custom unapproved datasets to ensure they are excluded from the default approved catalog
        for custom_tbl, c_info in CUSTOM_UNAPPROVED_DATASETS.items():
            c_lower = custom_tbl.lower()
            if c_lower in current_entries:
                entry = current_entries[c_lower]
                entry.classification = c_info["classification"]
                entry.approval_status = c_info["approval_status"]
                entry.category = c_info["category"]
                entry.description = c_info["description"]
            else:
                new_custom = ClinicalDatasetRegistry(
                    dataset_name=c_lower,
                    display_name=c_info["display_name"],
                    classification=c_info["classification"],
                    approval_status=c_info["approval_status"],
                    category=c_info["category"],
                    description=c_info["description"],
                )
                db.add(new_custom)

        # Check for any other existing MySQL tables not yet registered
        for db_tbl_lower, actual_name in existing_db_tables.items():
            if db_tbl_lower in METADATA_TABLES or db_tbl_lower.startswith("alembic_"):
                continue
            if (
                db_tbl_lower not in current_entries
                and db_tbl_lower not in CORE_APPROVED_CLINICAL_CATALOG
                and db_tbl_lower not in KNOWN_TEST_DEMO_TABLES
                and db_tbl_lower not in CUSTOM_UNAPPROVED_DATASETS
            ):
                # Register as quarantined/pending so it is neither silently approved nor deleted
                new_unknown = ClinicalDatasetRegistry(
                    dataset_name=db_tbl_lower,
                    display_name=actual_name.capitalize(),
                    classification="QUARANTINED",
                    approval_status="PENDING",
                    category="Unverified",
                    description=f"Auto-discovered table '{actual_name}' pending clinical verification.",
                )
                db.add(new_unknown)

        db.commit()
        _is_initialized = True


def get_approved_clinical_tables() -> List[str]:
    """
    Returns the list of lowercase table names that are:
      1. Registered with classification = 'CLINICAL'
      2. Marked with approval_status = 'APPROVED'
      3. Physically present in MySQL
    """
    ensure_registry_initialized()

    inspector = inspect(engine)
    existing_tables = set(t.lower() for t in inspector.get_table_names())

    with get_db_context() as db:
        results = (
            db.query(ClinicalDatasetRegistry.dataset_name)
            .filter(
                ClinicalDatasetRegistry.classification == "CLINICAL",
                ClinicalDatasetRegistry.approval_status == "APPROVED",
            )
            .all()
        )
        approved_registered = set(r[0].lower() for r in results)

    # Exclude system metadata tables
    approved_registered -= METADATA_TABLES

    # Only include tables that physically exist in MySQL
    valid_tables = [t for t in approved_registered if t in existing_tables]
    return sorted(valid_tables)


def is_table_approved_for_clinical_analytics(table_name: str) -> bool:
    """Verifies whether a specific table name is approved for clinical analytics."""
    if not table_name:
        return False
    approved = get_approved_clinical_tables()
    return table_name.strip().lower() in approved


def register_dataset(
    dataset_name: str,
    display_name: Optional[str] = None,
    classification: str = "CLINICAL",
    approval_status: str = "APPROVED",
    category: Optional[str] = "Custom Clinical",
    description: Optional[str] = "",
) -> Dict[str, Any]:
    """
    Registers or updates a dataset in the clinical dataset registry.
    """
    ensure_registry_initialized()
    clean_name = dataset_name.strip().lower()

    if clean_name in METADATA_TABLES:
        raise ValueError(f"Cannot register protected system table '{clean_name}'.")

    display = display_name or clean_name.capitalize()

    with get_db_context() as db:
        entry = (
            db.query(ClinicalDatasetRegistry)
            .filter(ClinicalDatasetRegistry.dataset_name == clean_name)
            .first()
        )
        if entry:
            entry.display_name = display
            entry.classification = classification
            entry.approval_status = approval_status
            if category:
                entry.category = category
            if description:
                entry.description = description
            entry.updated_at = datetime.utcnow()
        else:
            entry = ClinicalDatasetRegistry(
                dataset_name=clean_name,
                display_name=display,
                classification=classification,
                approval_status=approval_status,
                category=category or "Custom Clinical",
                description=description or f"Dataset '{clean_name}'",
            )
            db.add(entry)
        db.commit()

        return {
            "id": entry.id,
            "dataset_name": entry.dataset_name,
            "display_name": entry.display_name,
            "classification": entry.classification,
            "approval_status": entry.approval_status,
            "category": entry.category,
            "description": entry.description,
        }


def update_dataset_status(
    dataset_name: str,
    classification: Optional[str] = None,
    approval_status: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates the classification or approval status of an existing dataset.
    """
    ensure_registry_initialized()
    clean_name = dataset_name.strip().lower()

    with get_db_context() as db:
        entry = (
            db.query(ClinicalDatasetRegistry)
            .filter(ClinicalDatasetRegistry.dataset_name == clean_name)
            .first()
        )
        if not entry:
            raise ValueError(f"Dataset '{clean_name}' is not registered in the catalog.")

        if classification:
            entry.classification = classification.upper()
        if approval_status:
            entry.approval_status = approval_status.upper()
        if category:
            entry.category = category
        if description:
            entry.description = description
        entry.updated_at = datetime.utcnow()
        db.commit()

        return {
            "id": entry.id,
            "dataset_name": entry.dataset_name,
            "display_name": entry.display_name,
            "classification": entry.classification,
            "approval_status": entry.approval_status,
            "category": entry.category,
            "description": entry.description,
        }


def approve_dataset(dataset_name: str) -> Dict[str, Any]:
    """Approves a dataset for clinical analytics."""
    return update_dataset_status(
        dataset_name=dataset_name,
        classification="CLINICAL",
        approval_status="APPROVED",
    )


def list_all_registry_entries(include_all: bool = True, include_row_counts: bool = True) -> List[Dict[str, Any]]:
    """
    Lists all dataset entries in the registry with their row count and status.
    Separates ORM session from raw connection pool to prevent deadlock.
    """
    ensure_registry_initialized()
    inspector = inspect(engine)
    existing_tables = set(t.lower() for t in inspector.get_table_names())

    with get_db_context() as db:
        query = db.query(ClinicalDatasetRegistry)
        if not include_all:
            query = query.filter(
                ClinicalDatasetRegistry.classification == "CLINICAL",
                ClinicalDatasetRegistry.approval_status == "APPROVED",
            )
        raw_records = [
            {
                "id": r.id,
                "dataset_name": r.dataset_name,
                "display_name": r.display_name,
                "classification": r.classification,
                "approval_status": r.approval_status,
                "category": r.category,
                "description": r.description,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in query.order_by(ClinicalDatasetRegistry.dataset_name).all()
        ]

    entries_out = []
    if include_row_counts:
        with engine.connect() as conn:
            for r in raw_records:
                t_lower = r["dataset_name"].lower()
                row_cnt = 0
                if t_lower in existing_tables:
                    try:
                        row_cnt = conn.execute(text(f"SELECT COUNT(*) FROM `{t_lower}`")).scalar() or 0
                    except Exception:
                        row_cnt = 0
                r["row_count"] = int(row_cnt)
                r["is_present_in_db"] = t_lower in existing_tables
                entries_out.append(r)
    else:
        for r in raw_records:
            t_lower = r["dataset_name"].lower()
            r["row_count"] = 0
            r["is_present_in_db"] = t_lower in existing_tables
            entries_out.append(r)

    return entries_out
