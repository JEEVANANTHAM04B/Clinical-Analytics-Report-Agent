"""
tests/test_clinical_schema_mapping.py
=====================================
Test suite for Clinical Schema Registry, Dataset Metadata, Relationships,
KPI Definitions, and Question Planning Layer.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
from app.clinical import (
    registry,
    DATASETS,
    RELATIONSHIPS,
    KPIS,
    build_clinical_question_plan,
    get_all_relationships,
    find_direct_relationship,
    are_tables_connected,
    get_kpi,
    list_kpis_by_category,
)


class TestClinicalSchemaRegistry:
    """Test registry dataset coverage, keys, and metadata completeness."""

    def test_all_13_datasets_exist(self):
        expected_tables = {
            "study", "sites", "dm", "ae", "ex", "lb", "qs", "vs",
            "adsl", "adae", "adlb", "advs", "adresp"
        }
        actual_tables = set(registry.get_dataset_names())
        assert expected_tables == actual_tables, f"Missing datasets: {expected_tables - actual_tables}"

    def test_dataset_primary_keys_defined(self):
        for name in registry.get_dataset_names():
            ds = registry.get_dataset(name)
            assert ds is not None
            assert len(ds.primary_key) > 0, f"Dataset '{name}' has empty primary_key"
            for pk_col in ds.primary_key:
                assert pk_col in ds.important_columns, f"PK col '{pk_col}' missing from columns in '{name}'"
                assert ds.important_columns[pk_col].is_primary_key is True

    def test_dataset_domains_and_descriptions(self):
        for ds in registry.list_datasets():
            assert ds.domain, f"Dataset '{ds.name}' missing domain"
            assert ds.category in ("Study Management", "SDTM", "ADaM")
            assert ds.description, f"Dataset '{ds.name}' missing description"
            assert ds.purpose, f"Dataset '{ds.name}' missing purpose"
            assert len(ds.important_columns) > 0, f"Dataset '{ds.name}' has no columns"

    def test_column_metadata_retrieval(self):
        col = registry.get_column("dm", "USUBJID")
        assert col is not None
        assert col.name == "USUBJID"
        assert col.is_primary_key is True
        assert col.semantic_type == "identifier"

        age_col = registry.get_column("dm", "AGE")
        assert age_col is not None
        assert age_col.semantic_type == "numeric"

    def test_validate_required_columns(self):
        valid, missing = registry.validate_required_columns("adsl", ["USUBJID", "TRT01A", "AGE"])
        assert valid is True
        assert len(missing) == 0

        valid, missing = registry.validate_required_columns("adsl", ["USUBJID", "FAKE_COLUMN"])
        assert valid is False
        assert "FAKE_COLUMN" in missing


class TestClinicalRelationships:
    """Test relationship topology, cardinalities, and connectivity."""

    def test_all_expected_relationships_exist(self):
        rels = get_all_relationships()
        assert len(rels) >= 13

        # Check key joins
        study_sites = find_direct_relationship("study", "sites")
        assert study_sites is not None
        assert study_sites.parent_column == "STUDYID"
        assert study_sites.child_column == "STUDYID"

        dm_ae = find_direct_relationship("dm", "ae")
        assert dm_ae is not None
        assert dm_ae.parent_column == "USUBJID"

        adsl_adae = find_direct_relationship("adsl", "adae")
        assert adsl_adae is not None
        assert adsl_adae.parent_column == "USUBJID"

    def test_join_conditions(self):
        rel = registry.get_relationship("sites", "dm")
        assert rel is not None
        assert rel.join_condition == "sites.SITEID = dm.SITEID"

    def test_table_connectivity(self):
        # Connected clinical paths
        assert are_tables_connected(["study", "sites", "dm"]) is True
        assert are_tables_connected(["dm", "ae"]) is True
        assert are_tables_connected(["adsl", "adae", "adlb"]) is True

        # Disconnected or nonexistent table
        assert are_tables_connected(["study", "unrelated_bogus_table"]) is False


class TestKPIDefinitions:
    """Test standard clinical KPI definitions and formula integrity."""

    def test_all_17_kpis_registered(self):
        expected_kpis = [
            "TOTAL_SUBJECTS",
            "ENROLLMENT_BY_SITE",
            "SUBJECTS_BY_TREATMENT_ARM",
            "AVERAGE_AGE",
            "SEX_DISTRIBUTION",
            "ADVERSE_EVENT_COUNT",
            "SERIOUS_AE_COUNT",
            "ADVERSE_EVENT_RATE",
            "AE_RATE_BY_TREATMENT",
            "AE_SEVERITY_DISTRIBUTION",
            "LAB_VALUE",
            "LAB_CHANGE_FROM_BASELINE",
            "VITAL_SIGN_VALUE",
            "VITAL_SIGN_CHANGE_FROM_BASELINE",
            "EFFICACY_RESPONSE_COUNT",
            "EFFICACY_RESPONSE_RATE",
            "SUBJECT_DISPOSITION",
        ]
        registered = registry.get_kpi_ids()
        for k in expected_kpis:
            assert k in registered, f"KPI '{k}' missing from registry"

    def test_kpi_properties(self):
        ae_rate = get_kpi("AE_RATE_BY_TREATMENT")
        assert ae_rate is not None
        assert ae_rate.category == "Safety"
        assert "adsl" in ae_rate.required_datasets
        assert "adae" in ae_rate.required_datasets
        assert "TRT01A" in ae_rate.dimensions
        assert "adsl.TRT01A" in ae_rate.required_columns
        assert "sql_template" in ae_rate.__dict__ and len(ae_rate.sql_template) > 0

    def test_kpi_category_filtering(self):
        safety_kpis = list_kpis_by_category("Safety")
        assert len(safety_kpis) >= 4
        assert all(k.category == "Safety" for k in safety_kpis)

        efficacy_kpis = list_kpis_by_category("Efficacy")
        assert len(efficacy_kpis) >= 2


class TestClinicalQuestionPlanner:
    """Test deterministic mapping of clinical questions to execution plans."""

    def test_enrollment_question(self):
        plan = build_clinical_question_plan("How many patients are enrolled?")
        assert plan.is_supported is True
        assert plan.question_type == "enrollment"
        assert plan.matched_kpi_id == "TOTAL_SUBJECTS"
        assert "dm" in plan.datasets
        assert "dm.USUBJID" in plan.required_columns

    def test_average_age_question(self):
        plan = build_clinical_question_plan("What is the average age of patients?")
        assert plan.is_supported is True
        assert plan.question_type == "demographics"
        assert plan.matched_kpi_id == "AVERAGE_AGE"
        assert "dm.AGE" in plan.required_columns

    def test_ae_rate_by_treatment_question(self):
        plan = build_clinical_question_plan("Which treatment arm has the highest adverse event rate?")
        assert plan.is_supported is True
        assert plan.question_type == "safety"
        assert plan.matched_kpi_id == "AE_RATE_BY_TREATMENT"
        assert "adsl" in plan.datasets
        assert "adae" in plan.datasets
        assert plan.requires_join is True
        assert "TRT01A" in plan.dimensions

    def test_serious_ae_count_question(self):
        plan = build_clinical_question_plan("How many serious adverse events occurred?")
        assert plan.is_supported is True
        assert plan.question_type == "safety"
        assert plan.matched_kpi_id == "SERIOUS_AE_COUNT"
        assert "ae.AESER" in plan.required_columns

    def test_laboratory_change_question(self):
        plan = build_clinical_question_plan("What is the laboratory change from baseline to Week 8?")
        assert plan.is_supported is True
        assert plan.question_type == "laboratory"
        assert plan.matched_kpi_id == "LAB_CHANGE_FROM_BASELINE"
        assert "adlb" in plan.datasets

    def test_efficacy_response_rate_question(self):
        plan = build_clinical_question_plan("What is the efficacy response rate by treatment?")
        assert plan.is_supported is True
        assert plan.question_type == "efficacy"
        assert plan.matched_kpi_id == "EFFICACY_RESPONSE_RATE"
        assert "adresp" in plan.datasets
        assert "adresp.RESPFL" in plan.required_columns

    def test_site_enrollment_question(self):
        plan = build_clinical_question_plan("Which site has the highest enrollment?")
        assert plan.is_supported is True
        assert plan.question_type == "enrollment"
        assert plan.matched_kpi_id == "ENROLLMENT_BY_SITE"
        assert "sites" in plan.datasets
        assert "dm" in plan.datasets
        assert plan.requires_join is True


class TestNegativeCasesAndSafety:
    """Test safe fallbacks on invalid, unknown, or corrupted queries."""

    def test_empty_question_returns_unsupported(self):
        plan = build_clinical_question_plan("")
        assert plan.is_supported is False
        assert plan.question_type == "unknown"
        assert plan.confidence == 0.0

    def test_unknown_irrelevant_question(self):
        plan = build_clinical_question_plan("What is the capital of France and tomorrow's weather?")
        assert plan.is_supported is False
        assert plan.question_type == "unknown"
        assert plan.matched_kpi_id is None
        assert plan.confidence == 0.0

    def test_nonexistent_dataset_lookup(self):
        ds = registry.get_dataset("nonexistent_clinical_table")
        assert ds is None

    def test_nonexistent_column_lookup(self):
        col = registry.get_column("dm", "NOT_A_REAL_COLUMN")
        assert col is None

    def test_nonexistent_kpi_lookup(self):
        kpi = registry.get_kpi("BOGUS_KPI_123")
        assert kpi is None

    def test_prompt_context_generation(self):
        ctx = registry.build_schema_context_for_prompt(["dm", "ae"])
        assert "Table `dm`" in ctx
        assert "Table `ae`" in ctx
        assert "dm.USUBJID = ae.USUBJID" in ctx
        assert "Table `adsl`" not in ctx  # Only requested tables
