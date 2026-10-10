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
    target_metric: str | None = None,
    question: str | None = None,
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

    # Resolve X column (primary categorical / dimension)
    if not x_column or x_column not in cols:
        if cat_cols:
            x_column = cat_cols[0]
        else:
            x_column = cols[0]

    # Resolve Y column (numeric / metric)
    if not y_column or y_column not in cols:
        # 1. Match against target_metric if specified
        if target_metric and num_cols:
            tm_clean = target_metric.lower().replace("_", "")
            for c in num_cols:
                if c.lower().replace("_", "") == tm_clean or tm_clean in c.lower().replace("_", ""):
                    y_column = c
                    break

        # 2. Prioritize rate / percentage metrics if question or columns suggest rate
        if not y_column and num_cols:
            rate_indicators = ["rate", "pct", "percentage", "proportion", "%"]
            has_rate_q = question and any(term in question.lower() for term in rate_indicators)
            rate_cols = [c for c in num_cols if any(term in c.lower() for term in ["rate", "pct", "percentage"])]
            if has_rate_q and rate_cols:
                y_column = rate_cols[0]
            elif rate_cols:
                y_column = rate_cols[0]

        # 3. Prioritize analytical change/mean metrics over raw population counts
        if not y_column and num_cols:
            analytical_cols = [c for c in num_cols if any(k in c.lower() for k in ["chg", "pchg", "resp", "mean", "avg"])]
            if analytical_cols:
                y_column = analytical_cols[0]

        # 4. If total/enrolled subjects is present alongside an event/incidence count, pick event count
        if not y_column and num_cols:
            event_cols = [c for c in num_cols if any(k in c.lower() for k in ["ae_subjects", "event_count", "ae_count", "events"])]
            if event_cols:
                y_column = event_cols[0]
            else:
                y_column = num_cols[0]
        elif not y_column and len(cols) > 1:
            remaining = [c for c in cols if c != x_column]
            y_column = remaining[0] if remaining else cols[0]
        elif not y_column:
            y_column = cols[0]

    # Resolve Group / Stratification column (secondary categorical dimension)
    group_column = None
    remaining_cats = [c for c in cat_cols if c != x_column]
    if remaining_cats:
        group_column = remaining_cats[0]

    if not title:
        x_clean = "Treatment Arm" if x_column.lower() in ("trt01a", "arm") else x_column.replace("_", " ").title()
        if y_column.lower() in ("ae_rate_pct", "rate_pct", "ae_rate", "overall_ae_rate_pct"):
            y_clean = "Adverse Event Rate (%)"
        elif y_column.lower() in ("response_rate_pct", "resp_rate_pct"):
            y_clean = "Efficacy Response Rate (%)"
        elif y_column.lower() in ("event_count", "ae_count", "total_adverse_events"):
            y_clean = "Adverse Event Count"
        elif y_column.lower() in ("ae_subjects",):
            y_clean = "Subjects with Adverse Events"
        elif y_column.lower() in ("total_subjects", "subject_count", "enrolled_subjects"):
            y_clean = "Total Subjects"
        else:
            y_clean = y_column.replace("_", " ").title()

        if group_column:
            grp_clean = group_column.replace("_", " ").title()
            title = f"{y_clean} by {x_clean} and {grp_clean}"
        else:
            title = f"{y_clean} by {x_clean}"

    spec = {
        "chart_type": "bar",
        "title": title,
        "x_column": x_column,
        "y_column": y_column,
    }
    if group_column:
        spec["group_column"] = group_column
        spec["is_grouped"] = True

    return spec


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
    group_col = spec.get("group_column")

    df = pd.DataFrame(results)

    if group_col and group_col in df.columns:
        figure = px.bar(
            df,
            x=x_col,
            y=y_col,
            color=group_col,
            barmode="group",
            title=chart_title,
        )
    else:
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