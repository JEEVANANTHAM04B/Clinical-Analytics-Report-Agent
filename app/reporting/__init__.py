"""
app/reporting/__init__.py
=========================
Package for clinical analytics report generation.
"""

from app.reporting.pdf_generator import build_clinical_pdf_report

__all__ = ["build_clinical_pdf_report"]
