from sqlalchemy import text

from app.core.database import engine
from app.analytics.sql_validator import validate_sql


def execute_query(sql: str) -> list[dict]:
    is_valid, message = validate_sql(sql)

    if not is_valid:
        raise ValueError(f"SQL validation failed: {message}")

    with engine.connect() as connection:
        if engine.dialect.name == "mysql":
            connection.execute(text("SET SESSION MAX_EXECUTION_TIME = 30000"))
            connection.commit()
            connection.execute(text("SET TRANSACTION READ ONLY"))
        result = connection.execute(text(sql))

        columns = list(result.keys())
        if len(columns) != len(set(columns)):
            raise ValueError("Duplicate output column names; use distinct aliases")

        rows = result.fetchmany(10001)
        if len(rows) > 10000:
            raise ValueError("Result limit exceeded; narrow the approved analysis")
        return [
            dict(zip(columns, row))
            for row in rows
        ]