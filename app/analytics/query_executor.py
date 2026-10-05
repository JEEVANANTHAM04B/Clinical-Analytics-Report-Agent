from sqlalchemy import text

from app.core.database import engine
from app.analytics.sql_validator import validate_sql


def execute_query(sql: str) -> list[dict]:
    is_valid, message = validate_sql(sql)

    if not is_valid:
        raise ValueError(f"SQL validation failed: {message}")

    with engine.connect() as connection:
        result = connection.execute(text(sql))

        columns = result.keys()

        return [
            dict(zip(columns, row))
            for row in result.fetchall()
        ]