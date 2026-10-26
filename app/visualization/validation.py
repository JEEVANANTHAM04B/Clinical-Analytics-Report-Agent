"""Chart contracts: referenced data must be present, finite and numeric."""
import math
from numbers import Number


def validate_chart(spec, rows):
    if not rows or not isinstance(spec, dict): raise ValueError("Chart data is empty")
    if "data" in spec:
        if not spec["data"]: raise ValueError("Chart has no series")
        for trace in spec["data"]:
            if len(trace.get("x", [])) != len(rows) or len(trace.get("y", [])) != len(rows):
                raise ValueError("Chart labels and values have inconsistent lengths")
            x_column = spec.get("x_column")
            labels = [str(r.get(x_column, i)) if x_column else str(i) for i, r in enumerate(rows)]
            if trace["x"] != labels: raise ValueError("Chart labels differ from verified results")
            name = trace.get("name")
            if name not in rows[0] or trace["y"] != [r[name] for r in rows]:
                raise ValueError("Chart values differ from verified results")
            if not any(v is not None for v in trace["y"]): raise ValueError("Chart series has no measurements")
            if any(v is not None and (isinstance(v, bool) or not isinstance(v, Number) or not math.isfinite(v)) for v in trace["y"]):
                raise ValueError("Chart values are not finite numeric measurements")
    else:
        if spec.get("chart_type") not in {"bar", "line", "scatter", "pie"}: raise ValueError("Unsupported chart type")
        for name in ("x_column", "y_column"):
            if spec.get(name) not in rows[0]: raise ValueError("Chart column not present")
        values = [r[spec["y_column"]] for r in rows]
        if not any(v is not None for v in values): raise ValueError("No numeric chart values")
        if any(v is not None and (isinstance(v, bool) or not isinstance(v, Number) or not math.isfinite(v)) for v in values):
            raise ValueError("Chart values must be finite numbers")
    return spec
