"""
app/ingestion/__init__.py
==========================
Makes 'ingestion' a Python package.

The ingestion/ directory contains the ingestion service layer —
pure business logic, completely separated from FastAPI routing.

Modules:
  - file_validator.py  → Extension, size, and emptiness checks
  - file_reader.py     → Reads CSV/XLSX into a pandas DataFrame
  - metadata.py        → Extracts structural metadata from the DataFrame
  - quality_checker.py → Data quality analysis (missing, duplicates, etc.)

Architecture:
    FastAPI Route (api/ingestion.py)
          ↓
    Ingestion Service (file_validator → file_reader → metadata → quality_checker)
          ↓
    Pydantic Response (schemas/ingestion.py)
"""
