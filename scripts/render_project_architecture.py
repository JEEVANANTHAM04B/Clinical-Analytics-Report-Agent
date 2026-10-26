"""Render the current Clinical Analytics Platform architecture as an editable SVG."""

from html import escape
from pathlib import Path

WIDTH, HEIGHT = 2400, 1490
OUT = Path("output/clinical-analytics-architecture.svg")

INK = "#163148"
MUTED = "#5e7283"
LINE = "#a8b6c2"
PURPLE = "#6257cf"
LAVENDER = "#f0efff"
GREEN = "#087d67"
MINT = "#e4f6f0"
AMBER = "#ae690f"
CREAM = "#fff2dd"
NEUTRAL = "#f3f6f8"

svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
    '<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M1 1 L10 6 L1 11" fill="none" stroke="#546b7b" stroke-width="2"/></marker>',
    '<marker id="arrowGreen" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M1 1 L10 6 L1 11" fill="none" stroke="#087d67" stroke-width="2"/></marker>',
    '<marker id="arrowAmber" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M1 1 L10 6 L1 11" fill="none" stroke="#bd7718" stroke-width="2"/></marker>',
    '<filter id="shadow" x="-10%" y="-20%" width="120%" height="150%"><feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#d6dee6" flood-opacity=".55"/></filter></defs>',
    f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#fbfcfe"/>',
]


def txt(x, y, value, size=21, weight=400, color=INK, anchor="start"):
    svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>')


def rect(x, y, w, h, fill="white", stroke=LINE, radius=18, width=2, dash=None, shadow=False):
    attrs = f' x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"'
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    if shadow:
        attrs += ' filter="url(#shadow)"'
    svg.append(f'<rect{attrs}/>')


def line(x1, y1, x2, y2, color="#546b7b", width=3, marker=True, dash=None):
    attrs = f' x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" fill="none"'
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    if marker:
        attrs += f' marker-end="url(#{"arrowAmber" if color == "#bd7718" else "arrowGreen" if color == GREEN else "arrow"})"'
    svg.append(f'<line{attrs}/>')


def path(d, color="#546b7b", width=3, marker=True, dash=None):
    attrs = f' d="{d}" stroke="{color}" stroke-width="{width}" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    if marker:
        attrs += f' marker-end="url(#{"arrowAmber" if color == "#bd7718" else "arrowGreen" if color == GREEN else "arrow"})"'
    svg.append(f'<path{attrs}/>')


def section(x, y, w, h, title, accent, dashed=False):
    rect(x, y, w, h, "white", accent, 25, 3, "12 9" if dashed else None)
    rect(x + 18, y - 20, 57, 44, accent, accent, 11, 0)
    rect(x + 80, y - 20, min(w - 100, len(title) * 18), 46, "white", "white", 0, 0)
    txt(x + 46, y + 9, title[:1], 24, 700, "white", "middle")
    txt(x + 91, y + 14, title, 30, 700)


def card(x, y, w, h, title, subtitle, kind="neutral", badge=None):
    palette = {
        "neutral": (NEUTRAL, "#8b969e", INK),
        "purple": (LAVENDER, PURPLE, "#3d3b9c"),
        "green": (MINT, GREEN, "#075f50"),
        "amber": (CREAM, AMBER, "#845007"),
    }
    fill, stroke, title_color = palette[kind]
    rect(x, y, w, h, fill, stroke, 16, 2.2, shadow=True)
    if badge:
        svg.append(f'<circle cx="{x + 38}" cy="{y + 33}" r="21" fill="{stroke}"/>')
        txt(x + 38, y + 40, badge, 17, 700, "white", "middle")
        title_y = y + 72
    else:
        title_y = y + 44
    txt(x + w / 2, title_y, title, 22, 700, title_color, "middle")
    for index, part in enumerate(subtitle):
        txt(x + w / 2, title_y + 31 + 23 * index, part, 17, 400, MUTED, "middle")


txt(75, 38, "CLINICAL ANALYTICS PLATFORM", 34, 700)
txt(2320, 38, "CURRENT APPLICATION ARCHITECTURE", 19, 700, MUTED, "end")

# Client and API layer.
section(60, 84, 2280, 220, "Client and API layer", "#7c8a96", dashed=True)
card(160, 148, 390, 110, "Clinical user", ["Analyst or technical operator"], "green", "U")
card(740, 148, 430, 110, "React + TypeScript", ["Clinical and Technical views"], "green", "UI")
card(1360, 148, 430, 110, "FastAPI backend", ["REST APIs and request handling"], "neutral", "API")
card(1950, 148, 300, 110, "Audit", ["Operational event trail"], "neutral", "A")
line(550, 203, 740, 203)
line(1170, 203, 1360, 203)
line(1790, 203, 1950, 203)

# Main workflow layer.
section(60, 345, 2280, 715, "Dataset and LangGraph analytics pipeline", PURPLE)
txt(105, 408, "DATA ONBOARDING", 19, 700, PURPLE)
card(105, 430, 350, 150, "CSV / XLSX upload", ["Validate file and columns", "check duplicates"], "neutral", "IN")
card(560, 430, 400, 150, "Ingestion-time EDA", ["Profile data quality", "infer schema and relationships"], "neutral", "DQ")
card(1065, 430, 400, 150, "MySQL clinical store", ["SDTM / ADaM tables", "registry and versions"], "neutral", "DB")
card(1570, 430, 340, 150, "Redis (optional)", ["Validated row cache", "TTL; bypass on failure"], "green", "C")
card(1990, 430, 290, 150, "Gemini", ["Assists plan, SQL, insight", "fallbacks in workflow"], "purple", "AI")
line(455, 489, 560, 489)
line(960, 489, 1065, 489)
path("M1575 260 L1575 320 L35 320 L35 715", marker=False)
line(35, 489, 105, 489)
line(35, 715, 100, 715)

txt(105, 615, "APPROVED ANALYSIS FLOW", 19, 700, PURPLE)
cards = [
    (100, "Question + scope", ["Select approved tables", "and ask clinical question"], "purple", "1"),
    (420, "Analysis Plan Agent", ["Clinical mapping + schema", "LLM or deterministic plan"], "purple", "2"),
    (740, "Plan approval", ["Human review", "approve or request revision"], "amber", "3"),
    (1060, "SQL Generation Agent", ["LLM or deterministic", "read-only query"], "purple", "4"),
    (1380, "Validate SQL", ["AST, schema, table scope", "and safety rules"], "neutral", "5"),
    (1700, "Execute query", ["Bounded read-only", "MySQL execution"], "neutral", "6"),
    (2020, "Validate results", ["Shape, types, values", "correction if needed"], "neutral", "7"),
]
for x, title, subtitle, kind, badge in cards:
    card(x, 640, 280, 150, title, subtitle, kind, badge)
for x in (380, 700, 1020, 1340, 1660, 1980):
    line(x, 715, x + 40, 715)
path("M880 790 L880 829 L560 829 L560 790", "#bd7718", 3, dash="9 7")
txt(718, 855, "Feedback regenerates plan", 16, 600, AMBER, "middle")
path("M2160 790 L2160 873 L1200 873 L1200 790", "#bd7718", 3, dash="9 7")
txt(1670, 897, "Correctable result mismatch retries SQL", 16, 600, AMBER, "middle")
path("M1265 580 L1265 602 L1720 602 L1720 640", marker=True)
txt(1510, 596, "Read-only data access", 16, 600, MUTED, "middle")
path("M1740 580 L1740 625 L1870 625 L1870 640", GREEN, 3, dash="7 5")
txt(1820, 619, "Cache lookup", 15, 600, GREEN, "middle")
path("M2160 640 L2160 615 L1935 615 L1935 505 L1910 505", GREEN, 3, dash="7 5")
txt(2050, 607, "Store validated rows", 15, 600, GREEN, "middle")
rect(105, 920, 870, 45, "#f7f8fb", "#d7dfe6", 12, 1)
txt(540, 949, "Saved workflow state • stage recovery • operational audit events", 18, 600, MUTED, "middle")

# Follow-up requests use validated context and need not repeat the full plan gate.
rect(1070, 920, 970, 90, LAVENDER, PURPLE, 16, 2, shadow=True)
svg.append(f'<circle cx="1110" cy="950" r="19" fill="{PURPLE}"/>')
txt(1110, 956, "F", 17, 700, "white", "middle")
txt(1555, 954, "Follow-up questions", 22, 700, "#3d3b9c", "middle")
txt(1555, 985, "Reuse verified results; safe read-only SQL when needed; answer returns to React", 17, 400, MUTED, "middle")
path("M1780 258 L1780 325 L2360 325 L2360 965 L2040 965", PURPLE, 3, dash="9 7")
txt(2280, 906, "Follow-up API", 15, 600, PURPLE, "end")

# Output layer; acknowledgement persists the reviewed PDF before history and download.
section(60, 1100, 2280, 300, "Results, visualization and reporting", GREEN)
out_cards = [
    (2020, "AI Insight Agent", ["Generated from validated", "result rows"], "purple", "AI"),
    (1700, "Insight check", ["Evidence validation", "and bounded retry"], "neutral", "✓"),
    (1380, "Plotly charts", ["Validated chart spec", "rendered in the browser"], "green", "CH"),
    (1060, "Clinical PDF", ["Verified run, own charts", "rules and provenance"], "green", "PDF"),
    (740, "Human report review", ["Review generated PDF", "acknowledge to save"], "amber", "HR"),
    (420, "PDF report history", ["Acknowledged PDFs", "stored in MySQL"], "green", "DB"),
    (100, "Download PDF", ["Open or download", "saved report"], "green", "↓"),
]
for x, title, subtitle, kind, badge in out_cards:
    card(x, 1180, 280, 152, title, subtitle, kind, badge)
for x in (2020, 1700, 1380, 1060, 740, 420):
    line(x, 1256, x - 40, 1256)
path("M2160 790 L2160 1082 L2160 1180")
path("M880 1332 L880 1353 L1200 1353 L1200 1332", AMBER, 3, dash="8 6")
txt(1040, 1380, "Human review requests PDF revision (manual)", 15, 600, AMBER, "middle")
txt(1770, 1362, "Acknowledged PDF and report history persist in MySQL", 16, 600, MUTED, "middle")
txt(1770, 1384, "Render-error fallback retries PDF generation", 15, 600, MUTED, "middle")

txt(70, 1455, "Current implementation: no active FAISS / RAG retrieval stage or Governed Workspace.", 18, 400, MUTED)
txt(2330, 1455, "Source: current React, FastAPI and LangGraph code", 17, 400, MUTED, "end")
svg.append("</svg>")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(svg), encoding="utf-8")
print(OUT.resolve())
