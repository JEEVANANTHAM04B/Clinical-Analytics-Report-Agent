"""
tests/test_clinical_dashboard.py
================================
Automated test suite verifying the Clinical-Trial Dataset Dashboard Service migration:
1. Dynamic MySQL execution of all 17 clinical trial KPIs from app.clinical.kpi_definitions.
2. Dynamic dashboard payload generation across single and multi-table combinations.
3. Schema conformity to DashboardCustomizationResponse and OverviewResponse.
4. Relational connectivity and table validation.
5. Dynamic retrieval from MySQL (no hardcoded fake values).
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import pytest
from app.analytics.dashboard_service import (
    generate_custom_dashboard,
    calculate_clinical_kpi,
    validate_selected_tables,
    get_clinical_dashboard_summary,
)
from app.api.analytics import get_analytics_overview
from app.schemas.analytics import DashboardCustomizationResponse, OverviewResponse


# =============================================================================
# 1. TEST ALL 17 CLINICAL KPIS FROM MYSQL
# =============================================================================

class TestAllClinicalKPIs:
    """Verifies that all 17 clinical KPIs execute on MySQL and return live data."""

    def test_01_total_subjects(self):
        rows = calculate_clinical_kpi("TOTAL_SUBJECTS")
        assert len(rows) == 1
        assert rows[0]["total_subjects"] == 10000

    def test_02_enrollment_by_site(self):
        rows = calculate_clinical_kpi("ENROLLMENT_BY_SITE")
        assert len(rows) == 10
        total_recruited = sum(r["enrolled_subjects"] for r in rows)
        assert total_recruited == 10000
        for r in rows:
            assert "SITEID" in r
            assert "SITE_NAME" in r
            assert r["enrolled_subjects"] > 0

    def test_03_subjects_by_treatment_arm(self):
        rows = calculate_clinical_kpi("SUBJECTS_BY_TREATMENT_ARM")
        assert len(rows) == 2
        arms = {r["TRT01A"] for r in rows}
        assert arms == {"Drug X", "Placebo"}
        total_arm_subjects = sum(r["subject_count"] for r in rows)
        assert total_arm_subjects == 10000

    def test_04_average_age(self):
        rows = calculate_clinical_kpi("AVERAGE_AGE")
        assert len(rows) == 1
        mean_age = float(rows[0]["mean_age"])
        assert 50.0 <= mean_age <= 60.0
        assert rows[0]["min_age"] >= 10
        assert rows[0]["max_age"] <= 120

    def test_05_sex_distribution(self):
        rows = calculate_clinical_kpi("SEX_DISTRIBUTION")
        assert len(rows) == 2
        sexes = {r["SEX"] for r in rows}
        assert sexes == {"F", "M"}
        total_sex = sum(r["subject_count"] for r in rows)
        assert total_sex == 10000

    def test_06_adverse_event_count(self):
        rows = calculate_clinical_kpi("ADVERSE_EVENT_COUNT")
        assert len(rows) == 1
        assert rows[0]["total_adverse_events"] == 10000

    def test_07_serious_ae_count(self):
        rows = calculate_clinical_kpi("SERIOUS_AE_COUNT")
        assert len(rows) == 1
        sae_cnt = rows[0]["serious_adverse_events"]
        assert sae_cnt > 0
        assert sae_cnt < 10000

    def test_08_adverse_event_rate(self):
        rows = calculate_clinical_kpi("ADVERSE_EVENT_RATE")
        assert len(rows) == 1
        ae_rate = float(rows[0]["overall_ae_rate_pct"])
        assert 50.0 <= ae_rate <= 100.0

    def test_09_ae_rate_by_treatment(self):
        rows = calculate_clinical_kpi("AE_RATE_BY_TREATMENT")
        assert len(rows) == 2
        for r in rows:
            assert r["TRT01A"] in {"Drug X", "Placebo"}
            assert r["total_subjects"] > 0
            assert r["ae_subjects"] > 0
            assert float(r["ae_rate_pct"]) > 0

    def test_10_ae_severity_distribution(self):
        rows = calculate_clinical_kpi("AE_SEVERITY_DISTRIBUTION")
        assert len(rows) == 3
        sevs = {r["severity"] for r in rows}
        assert sevs == {"MILD", "MODERATE", "SEVERE"}
        total_events = sum(r["event_count"] for r in rows)
        assert total_events == 10000

    def test_11_laboratory_value(self):
        rows = calculate_clinical_kpi("LAB_VALUE")
        assert len(rows) >= 2
        for r in rows:
            assert "PARAMCD" in r
            assert "AVISIT" in r
            assert float(r["mean_aval"]) > 0

    def test_12_laboratory_change_from_baseline(self):
        rows = calculate_clinical_kpi("LAB_CHANGE_FROM_BASELINE")
        assert len(rows) >= 2
        for r in rows:
            assert r["AVISIT"] == "WEEK 8"
            assert "PARAMCD" in r
            assert "TRT01A" in r
            assert "mean_change" in r
            assert "mean_pct_change" in r

    def test_13_vital_sign_value(self):
        rows = calculate_clinical_kpi("VITAL_SIGN_VALUE")
        assert len(rows) >= 2
        for r in rows:
            assert "PARAMCD" in r
            assert "AVISIT" in r
            assert float(r["mean_val"]) > 0

    def test_14_vital_sign_change_from_baseline(self):
        rows = calculate_clinical_kpi("VITAL_SIGN_CHANGE_FROM_BASELINE")
        assert len(rows) >= 2
        for r in rows:
            assert r["AVISIT"] == "WEEK 8"
            assert "PARAMCD" in r
            assert "TRT01A" in r
            assert "mean_change" in r
            assert "mean_pct_change" in r

    def test_15_efficacy_response_count(self):
        rows = calculate_clinical_kpi("EFFICACY_RESPONSE_COUNT")
        assert len(rows) >= 1
        for r in rows:
            assert "AVISIT" in r
            assert r["responder_count"] > 0

    def test_16_efficacy_response_rate(self):
        rows = calculate_clinical_kpi("EFFICACY_RESPONSE_RATE")
        assert len(rows) >= 2
        for r in rows:
            assert r["AVISIT"] == "WEEK 8"
            assert r["TRT01A"] in {"Drug X", "Placebo"}
            assert r["evaluable_subjects"] > 0
            assert float(r["response_rate_pct"]) >= 0.0

    def test_17_subject_disposition(self):
        rows = calculate_clinical_kpi("SUBJECT_DISPOSITION")
        assert len(rows) == 2
        for r in rows:
            assert r["TRT01A"] in {"Drug X", "Placebo"}
            assert r["randomized_subjects"] > 0
            assert r["treated_subjects"] > 0
            assert r["completed_study_subjects"] > 0


# =============================================================================
# 2. TEST TABLE COMBINATIONS & DASHBOARD CUSTOMIZATION PAYLOADS
# =============================================================================

class TestDashboardCustomizationCombinations:
    """Verifies that generate_custom_dashboard produces valid response payloads."""

    def test_safety_combination_adsl_adae(self):
        payload = generate_custom_dashboard(["adsl", "adae"])
        # Validate against Pydantic schema
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert validated.status == "success"
        assert len(validated.kpi_cards) == 6
        assert len(validated.chart_categories) == 2
        assert len(validated.chart_values) == 2
        assert "Adverse Event" in validated.chart_title
        assert validated.primary_metric_label == "OVERALL AE INCIDENCE RATE"
        assert len(validated.verified_results) > 0
        assert validated.insight is not None

    def test_safety_combination_dm_ae(self):
        payload = generate_custom_dashboard(["dm", "ae"])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert validated.total_patients == 10000
        assert validated.total_encounters == 10000
        assert len(validated.kpi_cards) == 6

    def test_demographics_sites_dm(self):
        payload = generate_custom_dashboard(["sites", "dm"])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert "Site" in validated.chart_title
        assert len(validated.chart_categories) > 0
        assert len(validated.chart_values) > 0
        assert validated.primary_metric_label == "TOTAL ENROLLED SUBJECTS"
        assert validated.primary_metric_value == "10,000"

    def test_multi_table_study_sites_dm(self):
        payload = generate_custom_dashboard(["study", "sites", "dm"])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert len(validated.selected_tables) == 3

    def test_laboratory_combination_adsl_adlb(self):
        payload = generate_custom_dashboard(["adsl", "adlb"])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert "Laboratory" in validated.chart_title
        assert len(validated.chart_categories) > 0
        assert len(validated.chart_values) > 0
        assert "PEAK" in validated.primary_metric_label

    def test_vitals_combination_adsl_advs(self):
        payload = generate_custom_dashboard(["adsl", "advs"])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert "Vital" in validated.chart_title
        assert len(validated.chart_categories) > 0

    def test_efficacy_combination_adsl_adresp(self):
        payload = generate_custom_dashboard(["adsl", "adresp"])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert "Response Rate" in validated.chart_title
        assert len(validated.chart_categories) == 2
        assert validated.primary_metric_label == "CLINICAL RESPONSE RATE"


# =============================================================================
# 3. TEST SINGLE TABLES (13 CDISC DATASETS)
# =============================================================================

class TestSingleClinicalTables:
    """Verifies that all 13 single clinical tables produce complete dashboards."""

    @pytest.mark.parametrize("table_name", [
        "study", "sites", "dm", "ae", "ex", "lb", "qs", "vs",
        "adsl", "adae", "adlb", "advs", "adresp",
    ])
    def test_single_table_dashboard(self, table_name):
        payload = generate_custom_dashboard([table_name])
        validated = DashboardCustomizationResponse(**payload)
        assert validated.valid_combination is True
        assert validated.status == "success"
        assert validated.selected_tables == [table_name]
        assert len(validated.kpi_cards) == 6
        assert len(validated.chart_categories) > 0
        assert len(validated.chart_values) > 0
        assert validated.chart_title is not None
        assert validated.key_finding is not None
        assert len(validated.suggested_questions) >= 2


# =============================================================================
# 4. TEST INVALID SELECTIONS & DISCONNECTED SUBGRAPHS
# =============================================================================

class TestTableValidation:
    """Verifies security and validation checks on user-selected tables."""

    def test_empty_selection(self):
        payload = generate_custom_dashboard([])
        assert payload["valid_combination"] is False
        assert payload["status"] == "error"

    def test_unapproved_table(self):
        payload = generate_custom_dashboard(["unapproved_table_xyz"])
        assert payload["valid_combination"] is False
        assert "not an approved clinical table" in payload["message"]

    def test_disconnected_tables(self):
        # sites and adae have no direct edge without intermediate bridge
        payload = generate_custom_dashboard(["sites", "adae"])
        assert payload["valid_combination"] is False
        assert "cannot currently be combined" in payload["message"]


# =============================================================================
# 5. TEST GENERAL OVERVIEW ENDPOINT (LIVE MYSQL)
# =============================================================================

class TestOverviewEndpoint:
    """Verifies that get_analytics_overview returns live CDISC data dynamically."""

    def test_overview_metrics(self):
        res = get_analytics_overview()
        assert isinstance(res, OverviewResponse)
        assert res.status == "success"
        assert res.total_patients == 10000
        assert res.total_encounters == 10000
        assert 50.0 <= res.avg_length_of_stay <= 60.0
        assert res.readmission_rate > 0.0
        assert res.dataset_name == "Clinical Trial CDISC Dataset"
        assert len(res.encounter_classes) == 2
        assert len(res.top_diagnoses) > 0
        assert len(res.monthly_trends) > 0
