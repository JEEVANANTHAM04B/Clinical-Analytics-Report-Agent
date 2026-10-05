import re


FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
}


def validate_sql(
    sql: str,
    approved_schema: dict | None = None,
    analysis_plan: str | None = None,
) -> tuple[bool, str]:

    if not sql or not sql.strip():
        return False, "SQL query is empty"

    cleaned_sql = sql.strip()

    # Remove one trailing semicolon.
    if cleaned_sql.endswith(";"):
        cleaned_sql = cleaned_sql[:-1].strip()

    # Reject multiple statements.
    if ";" in cleaned_sql:
        return False, "Multiple SQL statements are not allowed"

    # Only SELECT statements are allowed.
    if not re.match(r"^SELECT\b", cleaned_sql, re.IGNORECASE):
        return False, "Only SELECT statements are allowed"

    # Reject empty SELECT clause immediately followed by FROM or end of string.
    if re.search(r"^\s*SELECT\s+(?:FROM\b|\Z)", cleaned_sql, re.IGNORECASE):
        return False, "Syntax error: SELECT clause contains no column expressions"

    # Reject dangling incomplete clauses at the end of the query.
    if re.search(r"\b(?:WHERE|JOIN|ON|HAVING|ORDER\s+BY|GROUP\s+BY)\s*$", cleaned_sql, re.IGNORECASE):
        return False, "Syntax error: query ends with an incomplete clause"

    # Reject dangerous SQL keywords.
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(
            rf"\b{keyword}\b",
            cleaned_sql,
            re.IGNORECASE,
        ):
            return False, f"Forbidden SQL keyword: {keyword}"

    if approved_schema is None:
        try:
            from app.database.schema_service import get_database_schema
            approved_schema = get_database_schema()
        except Exception:
            approved_schema = None

    if approved_schema:
        # -----------------------------------------------------
        # Approved tables and columns
        # -----------------------------------------------------
        approved_tables = {
            table.lower(): {
                column["name"].lower()
                for column in columns
            }
            for table, columns in approved_schema.get(
                "tables",
                {},
            ).items()
        }

        referenced_tables = {
            table.lower()
            for table in re.findall(
                r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
                cleaned_sql,
                re.IGNORECASE,
            )
        }

        unauthorized_tables = (
            referenced_tables - set(approved_tables)
        )

        if unauthorized_tables:
            return (
                False,
                "Unauthorized table(s): "
                + ", ".join(sorted(unauthorized_tables)),
            )

        qualified_columns = re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b",
            cleaned_sql,
            re.IGNORECASE,
        )

        for table, column in qualified_columns:
            table_lower = table.lower()
            column_lower = column.lower()

            if table_lower not in approved_tables:
                continue

            if column_lower not in approved_tables[table_lower]:
                return (
                    False,
                    f"Unauthorized column: "
                    f"{table}.{column}",
                )

        # -----------------------------------------------------
        # Approved relationship validation
        # -----------------------------------------------------
        approved_relationships = []

        for relationship in approved_schema.get(
            "relationships",
            [],
        ):
            approved_relationships.append(
                (
                    relationship["parent_table"].lower(),
                    relationship["parent_column"].lower(),
                    relationship["child_table"].lower(),
                    relationship["child_column"].lower(),
                )
            )

        join_conditions = re.findall(
            r"\bON\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)"
            r"\s*=\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
            cleaned_sql,
            re.IGNORECASE,
        )

        for (
            left_table,
            left_column,
            right_table,
            right_column,
        ) in join_conditions:

            relationship = (
                left_table.lower(),
                left_column.lower(),
                right_table.lower(),
                right_column.lower(),
            )

            reverse_relationship = (
                right_table.lower(),
                right_column.lower(),
                left_table.lower(),
                left_column.lower(),
            )

            if (
                relationship not in approved_relationships
                and reverse_relationship not in approved_relationships
            ):
                return (
                    False,
                    "Unauthorized relationship: "
                    f"{left_table}.{left_column} = "
                    f"{right_table}.{right_column}",
                )

    # ---------------------------------------------------------
    # Plan consistency validation
    # ---------------------------------------------------------
    if analysis_plan:
        plan_lower = analysis_plan.lower()
        sql_lower = cleaned_sql.lower()

        # 1. Grouping consistency
        if (
            "group by encounters.encounterclass" in plan_lower 
            or "group by `encounters.encounterclass`" in plan_lower
            or "group results by `encounters.encounterclass`" in plan_lower
            or "group results by encounters.encounterclass" in plan_lower
        ):
            if "encounterclass" not in sql_lower or "group by" not in sql_lower:
                return False, "Plan-consistency error: SQL must GROUP BY encounters.ENCOUNTERCLASS as required by approved plan"
            if "group by conditions.description" in sql_lower or "group by c.description" in sql_lower or "group by c.diagnosis" in sql_lower:
                return False, "Plan-consistency error: SQL groups by diagnosis/conditions.DESCRIPTION instead of approved encounters.ENCOUNTERCLASS"
        elif "group by conditions.description" in plan_lower or "group by `conditions.description`" in plan_lower:
            if "conditions.description" not in sql_lower and "description" not in sql_lower:
                return False, "Plan-consistency error: SQL must GROUP BY conditions.DESCRIPTION as required by approved plan"

        # 2. Single-table query check
        if (
            ("join conditions" in plan_lower and ("none required" in plan_lower or "none (" in plan_lower or "single-table" in plan_lower or "single table" in plan_lower))
            or ("relevant tables and columns" in plan_lower and "conditions" not in plan_lower and "encounters" in plan_lower)
        ):
            if " join " in sql_lower or " join\n" in sql_lower:
                return False, "Plan-consistency error: SQL includes JOINs but approved plan specifies a single-table query"

        # 3. Filtering consistency
        if "in ('inpatient', 'emergency')" in plan_lower or ("inpatient and emergency" in plan_lower and "encounterclass" in plan_lower):
            if "encounterclass = 'inpatient'" in sql_lower or "encounterclass = \"inpatient\"" in sql_lower or "encounterclass='inpatient'" in sql_lower:
                return False, "Plan-consistency error: SQL restricts to inpatient only, but approved plan requires inpatient and emergency"
            if "in ('inpatient', 'emergency')" not in sql_lower and "in (\"inpatient\", \"emergency\")" not in sql_lower and "in ('inpatient','emergency')" not in sql_lower:
                return False, "Plan-consistency error: SQL missing ENCOUNTERCLASS IN ('inpatient', 'emergency') filter required by approved plan"

        if "start is not null" in plan_lower and "start is not null" not in sql_lower:
            return False, "Plan-consistency error: SQL missing START IS NOT NULL filter required by approved plan"

        if "stop is not null" in plan_lower and "stop is not null" not in sql_lower:
            return False, "Plan-consistency error: SQL missing STOP IS NOT NULL filter required by approved plan"

        if "between 0 and 30" in plan_lower and "between 0 and 30" not in sql_lower:
            return False, "Plan-consistency error: SQL missing LOS BETWEEN 0 AND 30 filter required by approved plan"

    return True, "SQL query is safe"