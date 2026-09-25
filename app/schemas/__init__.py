"""
app/schemas/__init__.py
========================
Makes 'schemas' a Python package.

The schemas/ directory contains Pydantic response models used by
the API layer to define structured, validated JSON responses.

Current modules:
  - ingestion.py  → Response models for /ingestion/upload endpoint

Future phases will add:
  - analytics.py  → Response models for query results
  - reports.py    → Response models for PDF generation status
"""
