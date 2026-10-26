from sqlalchemy import inspect

from app.core.database import engine, get_db_context
from app.database.repository import get_approved_relationships_from_db


METADATA_TABLES = {
    "clinical_reports", "workflow_executions", "workflow_artifacts", "workflow_events", "workflow_notifications",
    "dataset_versions",
    "dataset_columns",
    "approved_relationships",
    "audit_logs",
    "clinical_dataset_registry",
}

def get_database_schema(approved_only: bool = True) -> dict:
    """
    Build the analytical database schema using only approved clinical datasets
    from the authoritative dataset registry.
    """

    inspector = inspect(engine)

    # ---------------------------------------------------------
    # 1. Read approved relationships while DB session is open
    # ---------------------------------------------------------
    with get_db_context() as db:
        approved_relationships = get_approved_relationships_from_db(
            db,
            status="APPROVED",
        )

        relationships = [
            {
                "parent_table": relationship.parent_table,
                "parent_column": relationship.parent_column,
                "child_table": relationship.child_table,
                "child_column": relationship.child_column,
            }
            for relationship in approved_relationships
        ]

    # ---------------------------------------------------------
    # 2. Determine approved clinical tables from authoritative registry
    # ---------------------------------------------------------
    from app.clinical.dataset_registry_service import get_approved_clinical_tables

    all_db_tables = inspector.get_table_names()

    if approved_only:
        approved_tables = set(get_approved_clinical_tables())
    else:
        approved_tables = {
            tbl.lower() for tbl in all_db_tables
            if tbl.lower() not in METADATA_TABLES and not tbl.lower().startswith("alembic_")
        }

    # Never expose metadata tables to analytical queries
    approved_tables -= {t.lower() for t in METADATA_TABLES}

    # ---------------------------------------------------------
    # 3. Build schema from actual MySQL columns
    # ---------------------------------------------------------
    schema = {
        "tables": {},
        "relationships": relationships,
    }

    for table_name in sorted(approved_tables):
        actual_name = next((t for t in all_db_tables if t.lower() == table_name.lower()), None)
        if not actual_name:
            continue

        columns = inspector.get_columns(actual_name)

        schema["tables"][actual_name] = [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column.get("nullable", True),
            }
            for column in columns
        ]

    return schema