"""Render a compact SVG overview from node labels in docs/architecture.mmd.

The Mermaid source remains the authoritative diagram for conditional edges.
"""
from pathlib import Path
import html
import re

source = Path("docs/architecture.mmd").read_text(encoding="utf-8")
matches = re.findall(r'^\s*([A-Z_]+)(?:\["([^"]+)"\]|\{"([^"]+)"\})', source, re.M)
labels = {name: (box or decision).replace("<br/>", " ") for name, box, decision in matches}
lanes = [
    ("Ingestion: dataset EDA and registration", ["UPLOAD", "FILE_CHECK", "QUALITY", "DUP_CHECK", "LOAD"], 115),
    ("Default analysis: result validation, then insights", ["PREFLIGHT", "SCHEMA", "PLAN", "PLAN_GATE", "SQL", "SQL_VALID", "RUN_SQL", "RESULTS", "INSIGHT", "INSIGHT_VALID", "CHART", "PDF"], 320),
]
assert all(key in labels for _, keys, _ in lanes for key in keys)
width, height, box_w, box_h, gap = 1600, 720, 230, 95, 25
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<rect width="100%" height="100%" fill="#f8fafc"/>',
         '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#1e293b}.title{font-size:25px;font-weight:700}.lane{font-size:18px;font-weight:700}.box{font-size:12px}.arrow{stroke:#64748b;stroke-width:2;fill:none}</style>',
         '<text class="title" x="45" y="45">Clinical analytics workflow</text>',
         '<text x="45" y="72" font-size="14">Dataset profiling runs during ingestion. Analysis keeps SQL and result validation.</text>']
for lane_name, keys, top in lanes:
    parts.append(f'<text class="lane" x="45" y="{top}">{html.escape(lane_name)}</text>')
    previous = None
    for index, key in enumerate(keys):
        row, column = divmod(index, 6)
        if row % 2:
            column = 5 - column
        x, y = 45 + column * (box_w + gap), top + 18 + row * 125
        fill = "#fef3c7" if "GATE" in key or key in {"PLAN_GATE", "REVIEW_GATE"} else "#e0e7ff" if key in {"PLAN", "SQL", "INSIGHT", "INTERPRET"} else "#d1fae5" if key in {"QUALITY", "DUP_CHECK", "RESULTS", "GOV_VALIDATE"} else "#ffffff"
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" fill="{fill}" stroke="#94a3b8"/>')
        words = labels[key].split()
        lines, current = [], []
        for word in words:
            if len(" ".join(current + [word])) > 30:
                lines.append(" ".join(current)); current = []
            current.append(word)
        if current: lines.append(" ".join(current))
        for line_no, line in enumerate(lines[:4]):
            parts.append(f'<text class="box" x="{x+11}" y="{y+26+18*line_no}">{html.escape(line)}</text>')
        if previous:
            px, py, prow = previous
            if row == prow:
                a, b = (px + box_w, x) if px < x else (px, x + box_w)
                parts.append(f'<path class="arrow" d="M{a} {y+box_h/2} H{b}"/>')
            else:
                parts.append(f'<path class="arrow" d="M{x+box_w/2} {py+box_h} V{y}"/>')
        previous = (x, y, row)
parts.append('<text x="45" y="680" font-size="14">Invalid results stop before insight generation. Cache misses use read-only SQL; reports use saved PDF bytes. See architecture.mmd for recovery branches.</text>')
parts.append('</svg>')
Path("docs/architecture.svg").write_text("\n".join(parts), encoding="utf-8")
