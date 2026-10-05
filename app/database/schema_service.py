from sqlalchemy import inspect

from app.core.database import engine, get_db_context
from app.database.repository import get_approved_relationships_from_db


METADATA_TABLES = {
    "dataset_versions",
    "dataset_columns",
    "approved_relationships",
    "audit_logs",
}


def get_database_schema() -> dict:
    """
    Build the analytical database schema using only
    human-approved relationships.
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

        # Convert ORM objects to plain dictionaries immediately.
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
    # 2. Determine approved clinical tables
    # ---------------------------------------------------------
    approved_tables = set()

    for relationship in relationships:
        approved_tables.add(relationship["parent_table"])
        approved_tables.add(relationship["child_table"])

    # Never expose metadata tables to the LLM.
    approved_tables -= METADATA_TABLES

    # ---------------------------------------------------------
    # 3. Build schema from actual MySQL columns
    # ---------------------------------------------------------
    schema = {
        "tables": {},
        "relationships": relationships,
    }

    for table_name in sorted(approved_tables):

        if table_name not in inspector.get_table_names():
            continue

        columns = inspector.get_columns(table_name)

        schema["tables"][table_name] = [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column["nullable"],
            }
            for column in columns
        ]

    return schema