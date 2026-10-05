import pandas as pd
import plotly.express as px
from decimal import Decimal


def _is_numeric(val) -> bool:
    if isinstance(val, (int, float, Decimal)):
        return True
    if isinstance(val, str):
        try:
            float(val.replace(',', ''))
            return True
        except ValueError:
            return False
    return False


def create_chart_spec(
    results: list[dict],
    x_column: str | None = None,
    y_column: str | None = None,
    title: str | None = None,
) -> dict:
    """
    Create a chart specification from validated SQL results.

    The specification contains only chart instructions.
    Actual values always come from validated SQL results.
    """

    if not results:
        raise ValueError("No data available for chart generation")

    first_row = results[0]
    cols = list(first_row.keys())

    if not cols:
        raise ValueError("No columns found in result rows")

    # Dynamic column classification
    cat_cols = []
    num_cols = []

    for c in cols:
        val = first_row.get(c)
        if _is_numeric(val):
            num_cols.append(c)
        else:
            cat_cols.append(c)

    # Resolve X column (categorical / dimension)
    if not x_column or x_column not in cols:
        if cat_cols:
            x_column = cat_cols[0]
        else:
            x_column = cols[0]

    # Resolve Y column (numeric / metric)
    if not y_column or y_column not in cols:
        if num_cols:
            y_column = num_cols[0]
        elif len(cols) > 1:
            remaining = [c for c in cols if c != x_column]
            y_column = remaining[0] if remaining else cols[0]
        else:
            y_column = cols[0]

    if not title:
        x_clean = x_column.replace("_", " ").title()
        y_clean = y_column.replace("_", " ").title()
        title = f"{y_clean} by {x_clean}"

    return {
        "chart_type": "bar",
        "title": title,
        "x_column": x_column,
        "y_column": y_column,
    }


def create_bar_chart(
    results: list[dict],
    x_column: str | None = None,
    y_column: str | None = None,
    title: str | None = None,
):
    """
    Create a Plotly bar chart from validated SQL results.
    """

    if not results:
        raise ValueError("No data available for chart generation")

    spec = create_chart_spec(results, x_column, y_column, title)
    x_col = spec["x_column"]
    y_col = spec["y_column"]
    chart_title = spec["title"]

    df = pd.DataFrame(results)

    figure = px.bar(
        df,
        x=x_col,
        y=y_col,
        title=chart_title,
    )

    figure.update_layout(
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=y_col.replace("_", " ").title(),
        template="plotly_white",
    )

    return figure