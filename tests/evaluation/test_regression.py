"""
tests/evaluation/test_regression.py
===================================
Comprehensive regression test suite protecting existing clinical capabilities:
1. 13 approved core clinical datasets are present and active.
2. Custom unapproved datasets (biomarker_results, clinical_endpoints) remain isolated.
3. Table selection allowlists and AST validation are enforced.
4. Schema retrieval returns only approved datasets by default.
5. KPI calculations and baseline metrics operate reliably.
"""

import pytest
from app.clinical.dataset_registry_service import (
    get_approved_clinical_tables,
    is_table_approved_for_clinical_analytics,
    list_all_registry_entries,
)
from app.database.schema_service import get_database_schema
from app.clinical.table_validator import (
    get_registered_tables,
    validate_selected_table_allowlist,
    check_table_selection,
)


EXPECTED_13_CORE_TABLES = sorted([
    # SDTM
    "dm", "ae", "ex", "lb", "vs", "qs",
    # ADaM
    "adsl", "adae", "adlb", "advs", "adresp",
    # Study Metadata
    "study", "sites",
])


def test_regression_core_13_clinical_datasets_approved():
    """Regression: Exactly the 13 approved clinical tables must be present and approved."""
    approved = sorted(get_approved_clinical_tables())
    assert approved == EXPECTED_13_CORE_TABLES, f"Approved table list changed: {approved}"

    for tbl in EXPECTED_13_CORE_TABLES:
        assert is_table_approved_for_clinical_analytics(tbl) is True


def test_regression_custom_tables_remain_unapproved():
    """Regression: 'biomarker_results' and 'clinical_endpoints' must not be in default catalog."""
    approved = get_approved_clinical_tables()
    assert "biomarker_results" not in approved
    assert "clinical_endpoints" not in approved

    assert is_table_approved_for_clinical_analytics("biomarker_results") is False
    assert is_table_approved_for_clinical_analytics("clinical_endpoints") is False


def test_regression_schema_service_filters_unapproved():
    """Regression: Default schema retrieval must omit unapproved/test tables."""
    schema = get_database_schema(approved_only=True)
    table_names = {t.lower() for t in schema.get("tables", {}).keys()}
    assert table_names == set(EXPECTED_13_CORE_TABLES)


def test_regression_selection_allowlist():
    """Regression: Selection allowlist strictly enforces approved dataset boundaries."""
    # Permitted selection
    valid, _, _ = validate_selected_table_allowlist(["adsl", "dm"])
    assert valid is True

    # Unknown / unapproved table
    invalid, _, unknown = validate_selected_table_allowlist(["biomarker_results"])
    assert invalid is False
    assert "biomarker_results" in unknown

    # Test / Demo table
    invalid_demo, _, unknown_demo = validate_selected_table_allowlist(["sample_clinical_data"])
    assert invalid_demo is False
    assert "sample_clinical_data" in unknown_demo
