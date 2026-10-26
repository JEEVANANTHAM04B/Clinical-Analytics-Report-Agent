"""Evidence-bound PDF rendering in the supplied clinical-safety template style."""
import html
import io
import re
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#1b3b64")
BLUE = colors.HexColor("#3f89c7")
MUTED = colors.HexColor("#526b86")
PALE = colors.HexColor("#e9f3fb")
ROW = colors.HexColor("#f3f7fb")
LINE = colors.HexColor("#c5d7e8")
INK = colors.HexColor("#24313c")


def _esc(value):
    return html.escape(str(value if value is not None else "Not supplied"))


def _label(key):
    label = str(key).replace("_", " ").strip().title()
    return label.replace(" Ae", " AE").replace(" Sae", " SAE").replace(" Pct", " (%)")


def _value(value, key=""):
    if value is None:
        return "Not supplied"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return f"{value:,}" + ("%" if "pct" in key.lower() or "percent" in key.lower() else "")
    if isinstance(value, float):
        is_percent = "pct" in key.lower() or "percent" in key.lower()
        number = f"{value:,.1f}" if is_percent or value != int(value) else f"{value:,.0f}"
        return number + ("%" if is_percent else "")
    return str(value)


def _styles():
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle("SafetyEyebrow", parent=base["Normal"], fontSize=11,
                                  leading=15, textColor=MUTED, alignment=1),
        "cover_title": ParagraphStyle("SafetyCoverTitle", parent=base["Title"], fontName="Helvetica-Bold",
                                      fontSize=22, leading=27, textColor=NAVY, alignment=1),
        "cover_sub": ParagraphStyle("SafetyCoverSub", parent=base["Normal"], fontSize=11,
                                    leading=16, textColor=MUTED, alignment=1),
        "heading": ParagraphStyle("SafetyHeading", parent=base["Heading2"], fontName="Helvetica-Bold",
                                  fontSize=13, leading=17, spaceBefore=12, spaceAfter=6,
                                  keepWithNext=True, textColor=NAVY),
        "subheading": ParagraphStyle("SafetySubheading", parent=base["Heading3"], fontName="Helvetica-Bold",
                                     fontSize=9.5, leading=13, spaceBefore=8, spaceAfter=4,
                                     keepWithNext=True, textColor=NAVY),
        "body": ParagraphStyle("SafetyBody", parent=base["BodyText"], fontSize=8.6,
                               leading=12.5, spaceAfter=3, textColor=INK),
        "small": ParagraphStyle("SafetySmall", parent=base["BodyText"], fontSize=7.5,
                                leading=10.5, spaceAfter=3, textColor=MUTED),
        "cell": ParagraphStyle("SafetyCell", parent=base["BodyText"], fontSize=8,
                               leading=10.5, textColor=INK),
        "cell_head": ParagraphStyle("SafetyCellHead", parent=base["BodyText"],
                                    fontName="Helvetica-Bold", fontSize=8,
                                    leading=10.5, textColor=colors.white),
    }


def _box(text, style):
    box = Table([[Paragraph(text, style)]], colWidths=[503])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#a6c9e7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return box


def _table(headers, data, widths, styles):
    rows = [[Paragraph(_esc(h), styles["cell_head"]) for h in headers]]
    rows += [[Paragraph(_esc(v), styles["cell"]) for v in row] for row in data]
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW, colors.white]),
        ("GRID", (0, 0), (-1, -1), .45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _arm_key(rows):
    if not rows:
        return None
    return next((key for key in rows[0] if key.lower() in {"treatment_arm", "arm", "trt01a"}), None)


def _summary_table(rows, styles):
    if not rows:
        return _table(["Metric", "Value"], [["Result rows", "None supplied"]], [252, 251], styles)
    arm = _arm_key(rows)
    if arm and len(rows) == 2:
        headers = ["Metric", str(rows[0].get(arm, "Group 1")), str(rows[1].get(arm, "Group 2"))]
        metrics = [key for key in rows[0] if key != arm]
        data = [[_label(key), _value(rows[0].get(key), key), _value(rows[1].get(key), key)] for key in metrics]
        return _table(headers, data or [["Result", "Not supplied", "Not supplied"]], [245, 129, 129], styles)
    if len(rows) == 1:
        return _table(["Metric", "Value"],
                      [[_label(key), _value(value, key)] for key, value in rows[0].items()],
                      [252, 251], styles)
    keys = list(rows[0])[:3]
    return _table([_label(key) for key in keys],
                  [[_value(row.get(key), key) for key in keys] for row in rows[:8]],
                  [503 / len(keys)] * len(keys), styles)


def _chart(rows, question, chart_builder):
    arm = _arm_key(rows)
    if arm and len(rows) == 2:
        import matplotlib.pyplot as plt

        numeric = [key for key in rows[0] if key != arm and all(
            isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool) for row in rows)]
        priority = [key for key in numeric if "pct" in key.lower() or "rate" in key.lower()]
        metric = (priority or numeric)[-1] if numeric else None
        if metric:
            labels = [str(row.get(arm, "Not supplied")) for row in rows]
            values = [float(row[metric]) for row in rows]
            fig, ax = plt.subplots(figsize=(6.8, 2.45), dpi=220)
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")
            bars = ax.bar(labels, values, width=.48, color="#3f89c7", edgecolor="#1b3b64", linewidth=.5)
            ax.set_ylim(min(0, min(values) * 1.2), max(values) * 1.28 if max(values) > 0 else 1)
            ax.set_ylabel("Percent" if "pct" in metric.lower() or "percent" in metric.lower()
                          else _label(metric), fontsize=8, color="#24313c")
            ax.tick_params(labelsize=8, colors="#24313c")
            ax.spines[["top", "right"]].set_visible(False)
            ax.spines[["left", "bottom"]].set_color("#c5d7e8")
            for bar, value in zip(bars, values):
                ax.annotate(_value(value, metric),
                            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                            xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
            fig.tight_layout(pad=1.0)
            image = io.BytesIO()
            fig.savefig(image, format="png", dpi=220, facecolor="white")
            plt.close(fig)
            image.seek(0)
            return image, metric
    return chart_builder(rows, question or ""), None


def _count_chart(rows):
    """Show two supplied participant counts without estimating missing values."""
    arm = _arm_key(rows)
    if not arm or len(rows) != 2:
        return None
    keys = {key.lower(): key for key in rows[0]}
    total = next((keys[name] for name in (
        "total_safety_subjects", "total_subjects", "safety_population"
    ) if name in keys), None)
    affected = next((keys[name] for name in (
        "subjects_with_sae", "sae_subjects", "subjects_with_ae", "ae_subjects"
    ) if name in keys), None)
    if not total or not affected or not all(
        isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)
        for row in rows for key in (total, affected)
    ):
        return None

    import matplotlib.pyplot as plt

    labels = [str(row[arm]) for row in rows]
    totals = [float(row[total]) for row in rows]
    affected_values = [float(row[affected]) for row in rows]
    fig, ax = plt.subplots(figsize=(6.8, 2.45), dpi=220)
    fig.patch.set_facecolor("white")
    positions = range(len(rows))
    first = ax.bar([x - .18 for x in positions], totals, width=.34, label=_label(total), color="#1b3b64")
    second = ax.bar([x + .18 for x in positions], affected_values, width=.34,
                    label=_label(affected), color="#3f89c7")
    ax.set_xticks(list(positions), labels)
    ax.set_ylabel("Participants", fontsize=8, color="#24313c")
    ax.set_ylim(0, max(totals + affected_values) * 1.25 or 1)
    ax.tick_params(labelsize=8, colors="#24313c")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c5d7e8")
    ax.legend(frameon=False, fontsize=7, loc="upper center", ncol=2,
              bbox_to_anchor=(.5, 1.16))
    for bar in [*first, *second]:
        ax.annotate(f"{bar.get_height():,.0f}",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=7)
    fig.tight_layout(pad=1.0)
    image = io.BytesIO()
    fig.savefig(image, format="png", dpi=220, facecolor="white")
    plt.close(fig)
    image.seek(0)
    return image


def _top_adverse_events_chart(entries):
    """Plot the separately queried ADAE participant counts, when available."""
    import matplotlib.pyplot as plt

    items = []
    for entry in entries[:5]:
        if not isinstance(entry, dict):
            continue
        term, count = entry.get("term"), entry.get("subject_count")
        if not isinstance(term, str) or not term.strip() or not isinstance(count, int) or isinstance(count, bool) or count < 0:
            continue
        items.append((term.strip(), count))
    if not items:
        return None, []

    fig, ax = plt.subplots(figsize=(6.8, 3.1), dpi=220)
    fig.patch.set_facecolor("white")
    bars = ax.barh(range(len(items)), [count for _, count in items], color="#3f89c7")
    ax.set_yticks(range(len(items)), [term[:38] + ("..." if len(term) > 38 else "") for term, _ in items])
    ax.invert_yaxis()
    ax.set_xlabel("Distinct participants", fontsize=8, color="#24313c")
    ax.set_xlim(0, max(count for _, count in items) * 1.2 or 1)
    ax.tick_params(labelsize=8, colors="#24313c")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#c5d7e8")
    for bar, (_, count) in zip(bars, items):
        ax.annotate(f"{count:,}", (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=8)
    fig.tight_layout(pad=1.0)
    image = io.BytesIO()
    fig.savefig(image, format="png", dpi=220, facecolor="white")
    plt.close(fig)
    image.seek(0)
    return image, items


def _analysis_rules(request, rows, group_names):
    """Summarize the supplied plan without restating SQL as clinical policy."""
    plan = request.analysis_plan or ""
    lower = plan.lower()
    if not plan.strip():
        return [("Analysis plan", "No approved plan was supplied with this report.")]

    rules = []
    if "saffl" in lower and ("unless" in lower or "if applicable" in lower):
        population = ("The plan mentions the safety-population flag as an optional restriction; "
                      "the submitted results do not establish that it was applied.")
    elif "saffl" in lower and "'y'" in lower:
        population = "The plan restricts participants to those marked with the safety-population flag."
    else:
        population = "The population is the participants represented in the submitted result rows; a safety-population restriction was not established."
    rules.append(("Analysis population", population))

    if group_names:
        comparison = f"Compare {group_names[0]} with {group_names[1]}"
        comparison += (" using the recorded treatment arm." if "trt01a" in lower
                       else " using the treatment groups in the submitted results.")
        rules.append(("Comparison", comparison))

    if "adsl" in lower and "adae" in lower:
        join = "Participant-level ADSL records are linked to ADAE adverse-event records"
        join += (" by participant ID." if "usubjid" in lower else ".")
        if re.search(r"without\W{0,5}studyid", lower):
            join += " The plan does not require a study-ID match; confirm participant IDs are unique across studies."
        rules.append(("How records are linked", join))

    columns = {key.lower() for row in rows for key in row}
    is_sae = "sae" in lower or "serious adverse" in lower or "sae" in " ".join(columns)
    is_ae = "adverse" in lower or "ae_" in " ".join(columns) or "ae" in (request.question or "").lower()
    event = "serious adverse event" if is_sae else "adverse event" if is_ae else "qualifying event"
    if "count(distinct" in lower and ("rate" in lower or "pct" in " ".join(columns)):
        rules.append(("Participant percentage",
                      f"Participants with at least one {event} divided by participants in the comparison group, multiplied by 100. Each participant is counted once per group."))
        rules.append(("Counting distinction",
                      f"One participant may have multiple {event} records. Event-record counts and participant counts are different measures."))

    if "trtemfl" in lower and ("unless" in lower or "if applicable" in lower):
        rules.append(("Event window", "The plan mentions treatment-emergent events as an optional restriction; the submitted results do not establish that it was applied."))

    sources = []
    selected = {table.lower() for table in request.selected_tables or []}
    if "adsl" in selected:
        sources.append("ADSL for participant-level treatment and population information")
    if "adae" in selected:
        sources.append("ADAE for adverse-event analysis records")
    if sources:
        rules.append(("Example data sources", "; ".join(sources) + ". Exact variables and derivations require confirmation against the study analysis specifications."))
    else:
        rules.append(("Data sources", ", ".join(request.selected_tables or []) or "Not specified"))
    if not re.search(r"\b(count\s*\(|select\b|join\b|group\s+by\b|usubjid\b)", lower):
        narrative = re.sub(r"[*#`]", "", plan)
        narrative = " ".join(narrative.split())
        if narrative:
            rules.append(("Additional plan detail", narrative))
    return rules


def _paragraphs(text, style):
    from app.reporting.pdf_generator import clean_markdown_for_reportlab

    output = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            output.append(Paragraph(clean_markdown_for_reportlab(line), style))
    return output or [Paragraph("Not supplied.", style)]


def build_report(request, *, clinical_context: bool, chart_builder) -> bytes:
    from app.reporting.pdf_generator import NumberedCanvas

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=46, rightMargin=46,
                            topMargin=46, bottomMargin=48)
    styles = _styles()
    rows = request.results or []
    metadata = request.analysis_metadata or {}
    study = metadata.get("study") or {}
    result_check = metadata.get("result_validation") or {}
    quality = metadata.get("eda") or {}
    source = metadata.get("provenance") or "Submitted report values; source execution not established."
    validation_record = (
        "Saved analysis validated" if result_check.get("valid") and request.analysis_run_id
        else "Result checks passed; source execution not established" if result_check.get("valid")
        else "Not established"
    )
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    question = request.question or "Clinical Analytics Inquiry"
    arm = _arm_key(rows)
    group_names = [str(row.get(arm, "")) for row in rows] if arm and len(rows) == 2 else []
    is_safety = "serious" in question.lower() and (
        "adverse" in question.lower() or "sae" in question.lower()
    )
    cover_title = "Serious Adverse Event Comparison" if is_safety else "Clinical Analytics Report"
    subtitle = " vs ".join(group_names) if group_names else question
    report_scope = ", ".join(request.selected_tables or []) or "Not specified"

    story = [
        Spacer(1, 36),
        Paragraph("CLINICAL SAFETY ANALYTICS" if is_safety else "CLINICAL ANALYTICS",
                  styles["eyebrow"]),
        Spacer(1, 12), Paragraph(_esc(cover_title), styles["cover_title"]),
        Spacer(1, 11), Paragraph(_esc(subtitle), styles["cover_sub"]), Spacer(1, 20),
    ]
    rule = Table([[""]], colWidths=[370], rowHeights=[1.5], hAlign="CENTER")
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE)]))
    story += [rule, Spacer(1, 14),
              _box(f"<b>Purpose</b><br/>{_esc(question)}", styles["body"]), Spacer(1, 9),
              Paragraph(f"<b>Study / dataset:</b> {_esc(request.dataset_name or 'Not specified')}", styles["body"]),
              Paragraph(f"<b>Study ID:</b> {_esc(study.get('studyid') or 'Not supplied')}", styles["body"]),
              Paragraph(f"<b>Phase:</b> {_esc(study.get('phase') or 'Not supplied')}", styles["body"]),
              Paragraph(f"<b>Study title:</b> {_esc(study.get('study_title') or 'Not supplied')}", styles["body"]),
              Paragraph(f"<b>Indication:</b> {_esc(study.get('indication') or 'Not supplied')}", styles["body"]),
              Paragraph(f"<b>Study dates:</b> {_esc(study.get('start_date') or 'Not supplied')} to {_esc(study.get('end_date') or 'Not supplied')}", styles["body"]),
              Paragraph(f"<b>Datasets consulted:</b> {_esc(report_scope)}", styles["body"]),
              Paragraph(f"<b>Report generated:</b> {_esc(generated)}", styles["body"])]
    if request.analysis_run_id:
        story.append(Paragraph(f"<b>Saved analysis:</b> {_esc(request.analysis_run_id)}", styles["body"]))
    story += [Spacer(1, 9),
              _box("<b>IMPORTANT:</b> Results reproduce the supplied or saved analysis. Review source provenance, "
                   "validation, and clinical interpretation before decision-making.", styles["body"]),
              Spacer(1, 15),
              Paragraph("Prepared by: Clinical Analytics Report Agent", styles["cover_sub"]),
              PageBreak(), Paragraph("1. Executive Summary", styles["heading"])]

    story += _paragraphs(request.insight or "No interpretation was supplied with this report.", styles["body"])
    story += [_summary_table(rows, styles), Spacer(1, 5)]
    chart, metric = _chart(rows, question, chart_builder)
    story.append(Paragraph("2. Results Visualization", styles["heading"]))
    if chart:
        story.append(KeepTogether([
            Image(chart, width=470, height=169), Spacer(1, 3),
            Paragraph("Figure 1. " + (_esc(_label(metric)) + " by treatment group" if metric else
                      "Selected metric across result categories") +
                      ". Values reproduce supplied result rows.", styles["small"]),
        ]))
    else:
        story.append(Paragraph("A comparison chart is not applicable to the supplied result rows.", styles["body"]))
    count_chart = _count_chart(rows)
    if count_chart:
        story.append(KeepTogether([
            Spacer(1, 5), Image(count_chart, width=470, height=169), Spacer(1, 3),
            Paragraph("Figure 2. Participant counts by treatment group. Bars reproduce supplied result values; no missing counts are estimated.", styles["small"]),
        ]))
    top_ae_chart, top_ae_items = _top_adverse_events_chart(metadata.get("top_adverse_events") or [])
    if top_ae_chart:
        story += [KeepTogether([
                      Paragraph("Top Adverse Events by Frequency", styles["heading"]),
                      Paragraph("Supplemental ADAE dataset view. This chart provides context beyond the question's verified result rows.", styles["body"]),
                      Image(top_ae_chart, width=470, height=214), Spacer(1, 3),
                      Paragraph("Figure 3. Distinct participants with each adverse-event term in ADAE. "
                                "The dataset query includes records where TRTEMFL and SAFFL are Y or null. "
                                "A participant can appear under more than one term, so counts must not be added together.", styles["small"]),
                  ]),
                  Spacer(1, 5), _table(["Adverse event", "Distinct participants"],
                                      [[term, f"{count:,}"] for term, count in top_ae_items],
                                      [350, 153], styles)]
    story.append(Paragraph("3. Population and Analysis Rules", styles["heading"]))
    for label, explanation in _analysis_rules(request, rows, group_names):
        story.append(Paragraph(f"<b>{_esc(label)}:</b> {_esc(explanation)}", styles["body"]))
    story += [_box("<b>Important:</b> These plain-language rules summarize the submitted analysis plan. "
                   "Confirm population definitions, event windows, and derivations against the study specifications.", styles["body"]),
              Paragraph("4. Verified Results" if result_check.get("valid") else "4. Submitted Results", styles["heading"]),
              Paragraph("Values below reproduce the supplied result rows; no category counts are inferred. "
                        + ("Result structure and values passed validation." if result_check.get("valid")
                           else "Result validation was not supplied."), styles["body"])]

    if rows:
        keys = list(dict.fromkeys(key for row in rows for key in row))
        if len(keys) <= 5:
            story.append(_table([_label(key) for key in keys],
                                [[_value(row.get(key), key) for key in keys] for row in rows],
                                [503 / len(keys)] * len(keys), styles))
            story.append(Spacer(1, 4))
        else:
            for number, row in enumerate(rows, 1):
                data = [[_label(key), _value(row.get(key), key)] for key in keys]
                story += [Paragraph(f"Record {number}", styles["subheading"]),
                          _table(["Field", "Value"], data, [210, 293], styles), Spacer(1, 4)]
    else:
        story.append(Paragraph("No result rows were supplied.", styles["body"]))
    insight_paragraphs = _paragraphs(request.insight or "No interpretation was supplied.", styles["body"])
    insight_section = [Paragraph("5. Clinical Insights and Follow-up", styles["heading"]),
                       Paragraph("<b>Observed pattern:</b>", styles["body"]),
                       *insight_paragraphs]
    if request.follow_up_answers:
        insight_section.append(Paragraph("Follow-up answers", styles["subheading"]))
        for answer in request.follow_up_answers:
            insight_section.append(Paragraph(f"<b>{_esc(answer.get('question', ''))}</b> {_esc(answer.get('answer', ''))}",
                                             styles["body"]))
    else:
        insight_section.append(Paragraph("No follow-up answers were supplied.", styles["body"]))
    insight_section.append(_box("<b>What cannot be concluded:</b> Descriptive results alone do not establish causality, "
                                "statistical significance, or a final benefit-risk decision.", styles["body"]))
    if len(insight_paragraphs) <= 3 and len(request.follow_up_answers or []) <= 2:
        story.append(KeepTogether(insight_section))
    else:
        story.extend(insight_section)
    story += [Spacer(1, 5), Paragraph("6. Data Quality, Limitations, and Traceability", styles["heading"])]
    if result_check:
        check_label = "Passed" if result_check.get("valid") else "Failed or incomplete"
        story.append(Paragraph(f"<b>Result structure and value checks:</b> {check_label}.", styles["body"]))
    else:
        story.append(Paragraph("<b>Result validation:</b> Not supplied.", styles["body"]))
    if quality:
        story.append(Paragraph("<b>Ingestion-time quality findings:</b>", styles["body"]))
        for finding in quality.get("findings", []):
            story.append(Paragraph(_esc(finding.get("message", "Quality finding without details")), styles["body"]))
    else:
        story.append(Paragraph("No ingestion-time quality assessment was attached.", styles["body"]))
    story.append(Paragraph(f"<b>Provenance:</b> {_esc(source)}", styles["body"]))
    story.append(Paragraph("A report submission alone does not establish source integrity, SQL execution, "
                           "protocol compliance, clinical approval, or regulatory certification.", styles["body"]))
    story += [Paragraph("7. Agent Execution Record", styles["heading"]),
              _table(["Field", "Report value"], [
                  ["User question", question], ["Datasets consulted", report_scope],
                  ["Output", f"{len(rows)} result row(s), interpretation" + (", chart" if chart else "") + (", participant chart" if count_chart else "") + (", supplemental ADAE chart" if top_ae_chart else "")],
                  ["Validation status", validation_record],
                  ["Report generated", generated],
              ], [155, 348], styles)]

    doc.build(story, canvasmaker=lambda *a, **kw: _canvas(NumberedCanvas, clinical_context, *a, **kw))
    return output.getvalue()


def _canvas(factory, clinical_context, *args, **kwargs):
    result = factory(*args, **kwargs)
    result.is_clinical_trial = clinical_context
    return result
