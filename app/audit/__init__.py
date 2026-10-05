"""
app/audit/__init__.py
=====================
Centralized Audit Trail Service Package
"""
from app.audit.service import record_audit_event, get_audit_trail

__all__ = ["record_audit_event", "get_audit_trail"]
