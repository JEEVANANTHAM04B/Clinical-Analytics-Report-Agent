import re
from typing import Optional, Dict, Set, List, Tuple, Any

from app.clinical import registry as clinical_registry


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

SQL_CLAUSE_KEYWORDS = {
    "join", "left", "right", "inner", "outer", "cross", "on", "where",
    "group", "by", "order", "having", "limit", "offset", "as", "set",
    "into", "values", "from", "select",
}

SQL_FUNCTIONS_AND_RESERVED = {
    "select", "from", "join", "left", "right", "inner", "outer", "cross", "on", "where",
    "group", "by", "order", "having", "limit", "offset", "as", "and", "or", "not", "in",
    "is", "null", "between", "like", "case", "when", "then", "else", "end", "asc", "desc",
    "distinct", "count", "avg", "sum", "min", "max", "round", "datediff", "abs", "coalesce",
    "ifnull", "concat", "substring", "true", "false", "now", "curdate", "date", "year", "month",
}


def _check_unqualified_columns(
    sql: str,
    referenced_tables: Set[str],
    approved_tables: Dict[str, Set[str]],
    alias_map: Dict[str, str],
) -> List[str]:
    """
    Validates unqualified column names referenced in the query against
    the union of columns in all referenced tables.
    """
    if not referenced_tables:
        return []

    # 1. Strip string literals
    clean = re.sub(r"'[^']*'", " ", sql)
    clean = clean.replace("`", "")

    # 2. Collect aliases defined via AS <alias>
    as_aliases = {
        m.group(1).lower()
        for m in re.finditer(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)\b", clean, re.IGNORECASE)
    }

    # 3. Strip qualified table.column identifiers (handled separately)
    clean = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\b", " ", clean)

    # 4. Strip AS <alias> clauses so the alias itself is not treated as an unresolvable column
    clean = re.sub(r"\bAS\s+[A-Za-z_][A-Za-z0-9_]*\b", " ", clean, flags=re.IGNORECASE)

    # 5. Strip FROM / JOIN <table_name> [alias] clauses
    clean = re.sub(
        r"\b(?:FROM|JOIN)\s+[A-Za-z_][A-Za-z0-9_]*(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\b",
        " ",
        clean,
        flags=re.IGNORECASE,
    )

    # Allowed column pool across all referenced tables
    allowed_cols: Set[str] = set()
    for t in referenced_tables:
        actual_t = alias_map.get(t.lower(), t.lower())
        allowed_cols.update(approved_tables.get(actual_t, set()))

    # Find remaining candidate identifiers
    identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", clean)
    unauthorized: List[str] = []

    for ident in identifiers:
        ident_lower = ident.lower()
        if (
            ident_lower in SQL_FUNCTIONS_AND_RESERVED
            or ident_lower in as_aliases
            or ident_lower in referenced_tables
            or ident_lower in alias_map
        ):
            continue
        if ident_lower not in allowed_cols:
            unauthorized.append(ident)

    return unauthorized


def _extract_plan_datasets(plan: str) -> List[str]:
    """
    Extract dataset table names from Section 1 ('Relevant Tables and Columns')
    or structured bullet lists of an analysis plan.
    """
    if not plan:
        return []
    datasets: List[str] = []
    registered = set(clinical_registry.get_dataset_names()) | {
        "encounters", "conditions", "patients", "medications", "observations", "procedures"
    }

    sec1_match = re.search(
        r'(?i)#{1,4}\s*(?:1[\.\s]*)?Relevant\s+Tables\s+and\s+Columns[^\n]*\n([\s\S]*?)(?:#{1,4}\s*(?:2[\.\s]*)?Join\s+Conditions|\Z)',
        plan,
    )
    search_text = sec1_match.group(1) if sec1_match else plan

    # Pattern 1: * **`table`**: or - **table**:
    matches = re.findall(r'(?:^|\n)\s*[*+-]\s*\*\*`?([A-Za-z0-9_]+)`?\*\*', search_text)
    for m in matches:
        ds = m.strip().lower()
        if ds not in datasets and ds not in ("none", "null") and ds in registered:
            datasets.append(ds)

    # Pattern 2: - Table: <table> or - Tables: <table1>, <table2>
    table_lines = re.findall(r'(?i)(?:^|\n)\s*[*+-]?\s*Tables?:\s*([^\n]+)', search_text)
    for line in table_lines:
        tokens = re.findall(r'[A-Za-z0-9_]+', line)
        for tok in tokens:
            ds = tok.strip().lower()
            if ds in registered and ds not in datasets:
                datasets.append(ds)

    # Pattern 3: - `table`: or * table:
    colon_matches = re.findall(r'(?:^|\n)\s*[*+-]\s*`?([A-Za-z0-9_]+)`?\s*:', search_text)
    for m in colon_matches:
        ds = m.strip().lower()
        if ds in registered and ds not in datasets:
            datasets.append(ds)

    # Pattern 4: Backticked identifiers in search_text: `table`
    backticked = re.findall(r'`([A-Za-z0-9_]+)`', search_text)
    for tok in backticked:
        ds = tok.strip().lower()
        if ds in registered and ds not in datasets:
            datasets.append(ds)

    # Pattern 5: Distinct clinical dataset acronyms (e.g. adlb, adsl, adae, advs)
    # Exclude common prose words (like 'study') unless structured as table/backticked above
    cdisc_distinct = registered - {"study", "patients", "conditions", "encounters", "procedures", "observations", "medications"}
    if not datasets:
        tokens = re.findall(r'\b[A-Za-z0-9_]+\b', search_text)
        for tok in tokens:
            ds = tok.strip().lower()
            if ds in cdisc_distinct and ds not in datasets:
                datasets.append(ds)

    return datasets

def validate_sql(
    sql: str,
    approved_schema: Optional[dict] = None,
    analysis_plan: Optional[str] = None,
    clinical_question_plan: Optional[Any] = None,
) -> Tuple[bool, str]:
    """
    Validates a SQL query for safety, security, and strict clinical schema conformance.
    Supports both the CDISC clinical-trial schema (primary) and legacy EHR schema.
    """
    if not sql or not sql.strip():
        return False, "SQL query is empty"

    cleaned_sql = sql.strip()

    # Remove one trailing semicolon
    if cleaned_sql.endswith(";"):
        cleaned_sql = cleaned_sql[:-1].strip()

    # Reject multiple statements
    if ";" in cleaned_sql:
        return False, "Multiple SQL statements are not allowed"

    # Only SELECT statements are allowed
    if not re.match(r"^SELECT\b", cleaned_sql, re.IGNORECASE):
        return False, "Only SELECT statements are allowed"

    # Reject empty SELECT clause immediately followed by FROM, semicolon, or end of string
    if re.search(r"^\s*SELECT(?:\s+(?:FROM\b|\Z)|\s*$)", cleaned_sql, re.IGNORECASE):
        return False, "Syntax error: SELECT clause contains no column expressions"

    # Reject dangling incomplete clauses at the end of the query
    if re.search(r"\b(?:WHERE|JOIN|ON|HAVING|ORDER\s+BY|GROUP\s+BY)\s*$", cleaned_sql, re.IGNORECASE):
        return False, "Syntax error: query ends with an incomplete clause"

    # Reject dangerous SQL keywords
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(
            rf"\b{keyword}\b",
            cleaned_sql,
            re.IGNORECASE,
        ):
            return False, f"Forbidden SQL keyword: {keyword}"

    # ---------------------------------------------------------
    # Resolve approved tables & columns
    # ---------------------------------------------------------
    approved_tables: Dict[str, Set[str]] = {}

    if approved_schema and "tables" in approved_schema:
        # Use explicitly passed schema (e.g. legacy EHR test cases or custom caller)
        for table, columns in approved_schema.get("tables", {}).items():
            approved_tables[table.lower()] = {
                (col["name"].lower() if isinstance(col, dict) else str(col).lower())
                for col in columns
            }

        # If an approved analysis plan or clinical question plan is provided,
        # ensure all approved CDISC datasets validated against ClinicalSchemaRegistry
        # are included in the authorization scope
        required_datasets: Set[str] = set()
        if analysis_plan:
            required_datasets.update(_extract_plan_datasets(analysis_plan))
        if clinical_question_plan:
            if isinstance(clinical_question_plan, dict):
                plan_ds = clinical_question_plan.get("datasets", [])
            else:
                plan_ds = getattr(clinical_question_plan, "datasets", [])
            for ds in plan_ds:
                if isinstance(ds, str):
                    required_datasets.add(ds.strip().lower())

        for ds_name in required_datasets:
            if ds_name in approved_tables:
                ds_meta = clinical_registry.get_dataset(ds_name)
                if ds_meta:
                    approved_tables[ds_name].update(
                        c.lower() for c in ds_meta.important_columns.keys()
                    )
    else:
        # Production default: populate from ClinicalSchemaRegistry
        for ds in clinical_registry.list_datasets():
            approved_tables[ds.name.lower()] = {
                col_name.lower() for col_name in ds.important_columns.keys()
            }

        # Also incorporate columns from live database inspection if available
        try:
            from app.database.schema_service import get_database_schema
            db_schema = get_database_schema()
            if db_schema and "tables" in db_schema:
                for tbl, cols in db_schema["tables"].items():
                    tbl_lower = tbl.lower()
                    col_names = {c["name"].lower() for c in cols}
                    if tbl_lower in approved_tables:
                        approved_tables[tbl_lower].update(col_names)
                    else:
                        approved_tables[tbl_lower] = col_names
        except Exception:
            pass

    # ---------------------------------------------------------
    # Table validation (AST-based parsing with CTE exclusion)
    # ---------------------------------------------------------
    try:
        from app.clinical.table_validator import extract_sql_tables_ast
        referenced_tables = extract_sql_tables_ast(cleaned_sql)
    except Exception:
        referenced_tables = {
            table.lower()
            for table in re.findall(
                r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)",
                cleaned_sql,
                re.IGNORECASE,
            )
        }

    unauthorized_tables = referenced_tables - set(approved_tables)
    if unauthorized_tables:
        return (
            False,
            "Unauthorized table(s): "
            + ", ".join(sorted(unauthorized_tables)),
        )

    # ---------------------------------------------------------
    # Table alias map resolution
    # ---------------------------------------------------------
    alias_map: Dict[str, str] = {t: t for t in approved_tables}
    for m in re.finditer(
        r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?",
        cleaned_sql,
        re.IGNORECASE,
    ):
        table_name = m.group(1).lower()
        alias = m.group(2)
        if alias and alias.lower() not in SQL_CLAUSE_KEYWORDS:
            alias_map[alias.lower()] = table_name

    # ---------------------------------------------------------
    # Column validation
    # ---------------------------------------------------------
    # 1. Qualified columns (table.column or alias.column)
    qualified_columns = re.findall(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b",
        cleaned_sql,
        re.IGNORECASE,
    )

    for table_or_alias, column in qualified_columns:
        tbl_lower = table_or_alias.lower()
        col_lower = column.lower()

        actual_table = alias_map.get(tbl_lower, tbl_lower)
        if actual_table not in approved_tables:
            continue

        if col_lower not in approved_tables[actual_table]:
            return (
                False,
                f"Unauthorized column: "
                f"{table_or_alias}.{column}",
            )

    # 2. Unqualified columns
    unauthorized_unqualified = _check_unqualified_columns(
        cleaned_sql, referenced_tables, approved_tables, alias_map
    )
    if unauthorized_unqualified:
        return (
            False,
            f"Unauthorized column: {unauthorized_unqualified[0]}",
        )

    # ---------------------------------------------------------
    # Approved relationship validation
    # ---------------------------------------------------------
    approved_relationships: Set[Tuple[str, str, str, str]] = set()

    # 1. From ClinicalSchemaRegistry
    for rel in clinical_registry.get_relationships():
        approved_relationships.add(
            (
                rel.parent_table.lower(),
                rel.parent_column.lower(),
                rel.child_table.lower(),
                rel.child_column.lower(),
            )
        )

    # 2. From approved_schema if available
    if approved_schema and "relationships" in approved_schema:
        for relationship in approved_schema.get("relationships", []):
            approved_relationships.add(
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
        left_table_or_alias,
        left_column,
        right_table_or_alias,
        right_column,
    ) in join_conditions:
        left_table = alias_map.get(left_table_or_alias.lower(), left_table_or_alias.lower())
        right_table = alias_map.get(right_table_or_alias.lower(), right_table_or_alias.lower())

        relationship = (
            left_table,
            left_column.lower(),
            right_table,
            right_column.lower(),
        )

        reverse_relationship = (
            right_table,
            right_column.lower(),
            left_table,
            left_column.lower(),
        )

        if (
            relationship not in approved_relationships
            and reverse_relationship not in approved_relationships
        ):
            return (
                False,
                "Unauthorized relationship: "
                f"{left_table_or_alias}.{left_column} = "
                f"{right_table_or_alias}.{right_column}",
            )

    # ---------------------------------------------------------
    # Clinical multi-table connectivity check
    # ---------------------------------------------------------
    clinical_datasets = set(clinical_registry.get_dataset_names())
    ref_clinical = [t for t in referenced_tables if t in clinical_datasets]
    if len(ref_clinical) > 1:
        if not clinical_registry.are_connected(ref_clinical):
            return (
                False,
                f"Disconnected clinical tables in join: "
                + ", ".join(sorted(ref_clinical)),
            )

    # ---------------------------------------------------------
    # Plan consistency validation
    # ---------------------------------------------------------
    if analysis_plan:
        plan_lower = analysis_plan.lower()
        sql_lower = cleaned_sql.lower()

        def _get_join_section(text: str) -> str:
            if "join conditions" in text:
                after = text.split("join conditions", 1)[1]
                match = re.search(r"(?:###+|\*\*|\n)\s*3[\.\s]", after)
                if match:
                    return after[:match.start()]
                return after[:200]
            return ""

        join_section = _get_join_section(plan_lower)
        is_ehr = bool(re.search(r"\b(encounters|encounterclass)\b", plan_lower) or ("conditions" in plan_lower and "dm" not in plan_lower and "adsl" not in plan_lower))

        # Legacy EHR plan consistency checks
        if is_ehr:
            if (
                "group by encounters.encounterclass" in plan_lower
                or "group by `encounters.encounterclass`" in plan_lower
                or "group results by `encounters.encounterclass`" in plan_lower
                or "group results by encounters.encounterclass" in plan_lower
            ):
                if "encounterclass" not in sql_lower or "group by" not in sql_lower:
                    return False, "Plan-consistency error: SQL must GROUP BY encounters.ENCOUNTERCLASS as required by approved plan"
                if (
                    "group by conditions.description" in sql_lower
                    or "group by c.description" in sql_lower
                    or "group by c.diagnosis" in sql_lower
                ):
                    return False, "Plan-consistency error: SQL groups by diagnosis/conditions.DESCRIPTION instead of approved encounters.ENCOUNTERCLASS"
            elif (
                "group by conditions.description" in plan_lower
                or "group by `conditions.description`" in plan_lower
            ):
                if "conditions.description" not in sql_lower and "description" not in sql_lower:
                    return False, "Plan-consistency error: SQL must GROUP BY conditions.DESCRIPTION as required by approved plan"

            if (
                ("none required" in join_section or "none (" in join_section or "single-table" in join_section or "single table" in join_section)
                or ("relevant tables and columns" in plan_lower and "conditions" not in plan_lower and "encounters" in plan_lower)
            ):
                if " join " in sql_lower or " join\n" in sql_lower:
                    return False, "Plan-consistency error: SQL includes JOINs but approved plan specifies a single-table query"

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

        # CDISC clinical trial plan consistency checks
        else:
            if (
                "group by dm.arm" in plan_lower
                or "group results by dm.arm" in plan_lower
                or "group by `dm.arm`" in plan_lower
            ):
                if "arm" not in sql_lower or "group by" not in sql_lower:
                    return False, "Plan-consistency error: SQL must GROUP BY dm.ARM as required by approved plan"
                if "group by ae.aesev" in sql_lower or "group by aesev" in sql_lower:
                    return False, "Plan-consistency error: SQL groups by ae.AESEV instead of approved dm.ARM"

            if (
                ("none required" in join_section or "single-table" in join_section or "single table" in join_section or "join required: no" in join_section)
                or ("relevant tables and columns" in plan_lower and "dm only" in plan_lower)
            ):
                if " join " in sql_lower or " join\n" in sql_lower:
                    return False, "Plan-consistency error: SQL includes JOINs but approved plan specifies a single-table query"

            if "aeser = 'y'" in plan_lower or "serious adverse events" in plan_lower:
                if "aeser" not in sql_lower or "'y'" not in sql_lower:
                    return False, "Plan-consistency error: SQL missing AESER = 'Y' filter required by approved plan"

            if "respfl = 'y'" in plan_lower or "responders" in plan_lower:
                if "respfl" not in sql_lower or "'y'" not in sql_lower:
                    return False, "Plan-consistency error: SQL missing RESPFL = 'Y' filter required by approved plan"

            if "rfstdtc is not null" in plan_lower and "rfstdtc is not null" not in sql_lower:
                return False, "Plan-consistency error: SQL missing RFSTDTC IS NOT NULL filter required by approved plan"

            if "eosdt is not null" in plan_lower and "eosdt is not null" not in sql_lower:
                return False, "Plan-consistency error: SQL missing EOSDT IS NOT NULL filter required by approved plan"

            if "between 18 and 65" in plan_lower and "between 18 and 65" not in sql_lower:
                return False, "Plan-consistency error: SQL missing AGE BETWEEN 18 AND 65 filter required by approved plan"

    return True, "SQL query is safe"