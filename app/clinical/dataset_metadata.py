"""
app/clinical/dataset_metadata.py
================================
Defines domain metadata, column profiles, and analytical usage for all 13
clinical-trial datasets in CDISC SDTM and ADaM formats.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ColumnMetadata:
    """Metadata for an individual clinical dataset column."""
    name: str
    data_type: str
    semantic_type: str  # identifier, categorical, numeric, date, flag, text
    nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_target: Optional[str] = None  # e.g. "study.STUDYID"
    description: str = ""
    example_values: List[Any] = field(default_factory=list)


@dataclass
class DatasetMetadata:
    """Metadata for a CDISC SDTM or ADaM clinical-trial dataset."""
    name: str  # lowercase table name, e.g. "dm", "adsl"
    domain: str  # standard CDISC domain name
    category: str  # "Study Management", "SDTM", "ADaM"
    description: str
    purpose: str
    primary_key: List[str]
    foreign_keys: Dict[str, str]  # local_column -> "parent_table.parent_column"
    subject_level: bool  # True if 1 row per subject
    analysis_level: str  # "study", "site", "subject", "event", "visit_parameter", "finding"
    clinical_role: str
    important_columns: Dict[str, ColumnMetadata]
    kpi_usage: List[str]


# =============================================================================
# CLINICAL TRIAL DATASET REGISTRY DEFINITIONS
# =============================================================================

DATASETS: Dict[str, DatasetMetadata] = {
    # ── 1. STUDY ─────────────────────────────────────────────────────────────
    "study": DatasetMetadata(
        name="study",
        domain="Study Metadata",
        category="Study Management",
        description="High-level clinical trial protocol metadata and overall timeline.",
        purpose="Defines core study parameters, phase, therapeutic area, indication, and sponsor.",
        primary_key=["STUDYID"],
        foreign_keys={},
        subject_level=False,
        analysis_level="study",
        clinical_role="Root trial metadata",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, True, False, description="Unique study identifier (e.g. STDY001)", example_values=["STDY001"]),
            "STUDY_TITLE": ColumnMetadata("STUDY_TITLE", "VARCHAR(255)", "text", False, False, False, description="Full clinical protocol title", example_values=["Phase 3 Study of Drug X in Moderate Rheumatoid Arthritis"]),
            "PHASE": ColumnMetadata("PHASE", "VARCHAR(50)", "categorical", False, False, False, description="Clinical trial phase (e.g. Phase 3)", example_values=["Phase 3"]),
            "THERAPEUTIC_AREA": ColumnMetadata("THERAPEUTIC_AREA", "VARCHAR(100)", "categorical", False, False, False, description="Therapeutic area", example_values=["Rheumatology"]),
            "INDICATION": ColumnMetadata("INDICATION", "VARCHAR(100)", "categorical", False, False, False, description="Target disease indication", example_values=["Rheumatoid Arthritis"]),
            "SPONSOR": ColumnMetadata("SPONSOR", "VARCHAR(100)", "categorical", False, False, False, description="Trial sponsor organization", example_values=["Demo Pharma"]),
            "STUDY_STATUS": ColumnMetadata("STUDY_STATUS", "VARCHAR(50)", "categorical", False, False, False, description="Current operational status", example_values=["Completed"]),
            "START_DATE": ColumnMetadata("START_DATE", "DATE", "date", False, False, False, description="Study initiation date", example_values=["2025-01-15"]),
            "END_DATE": ColumnMetadata("END_DATE", "DATE", "date", False, False, False, description="Study completion date", example_values=["2026-06-30"]),
        },
        kpi_usage=["Study Duration", "Study Protocol Info"],
    ),

    # ── 2. SITES ─────────────────────────────────────────────────────────────
    "sites": DatasetMetadata(
        name="sites",
        domain="Sites",
        category="Study Management",
        description="Participating clinical trial research centers and target enrollments.",
        purpose="Tracks investigator sites, locations, planned subjects, and actual recruited subjects.",
        primary_key=["SITEID"],
        foreign_keys={"STUDYID": "study.STUDYID"},
        subject_level=False,
        analysis_level="site",
        clinical_role="Site-level operational metadata",
        important_columns={
            "SITEID": ColumnMetadata("SITEID", "VARCHAR(50)", "identifier", False, True, False, description="Unique clinical site identifier", example_values=["SITE001", "SITE002"]),
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, True, "study.STUDYID", "Foreign key to study protocol", example_values=["STDY001"]),
            "SITE_NAME": ColumnMetadata("SITE_NAME", "VARCHAR(100)", "categorical", False, False, False, description="Clinical center institution name", example_values=["Clinical Center 1"]),
            "COUNTRY": ColumnMetadata("COUNTRY", "VARCHAR(100)", "categorical", False, False, False, description="Country location of the site", example_values=["India"]),
            "CITY": ColumnMetadata("CITY", "VARCHAR(100)", "categorical", False, False, False, description="City location of the site", example_values=["Delhi", "Hyderabad"]),
            "PI_NAME": ColumnMetadata("PI_NAME", "VARCHAR(100)", "text", False, False, False, description="Principal Investigator name", example_values=["Dr. PI 1"]),
            "PLANNED_SUBJECTS": ColumnMetadata("PLANNED_SUBJECTS", "INT", "numeric", False, False, False, description="Target enrollment allocation", example_values=[1000]),
            "ACTUAL_SUBJECTS": ColumnMetadata("ACTUAL_SUBJECTS", "INT", "numeric", False, False, False, description="Recruited subject count", example_values=[1000]),
        },
        kpi_usage=["Site Enrollment", "Planned vs Actual Recruitment"],
    ),

    # ── 3. DM (Demographics - SDTM) ──────────────────────────────────────────
    "dm": DatasetMetadata(
        name="dm",
        domain="Demographics",
        category="SDTM",
        description="Demographics domain describing baseline subject characteristics.",
        purpose="Defines all enrolled subjects, demographics, randomized treatment arms, and trial participation dates.",
        primary_key=["USUBJID"],
        foreign_keys={
            "STUDYID": "study.STUDYID",
            "SITEID": "sites.SITEID"
        },
        subject_level=True,
        analysis_level="subject",
        clinical_role="Subject baseline demographics and randomization",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, True, "study.STUDYID", "Study identifier", example_values=["STDY001"]),
            "DOMAIN": ColumnMetadata("DOMAIN", "VARCHAR(10)", "categorical", False, False, False, description="CDISC domain identifier ('DM')", example_values=["DM"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, False, description="Unique subject identifier across the study", example_values=["STDY001-0001"]),
            "SUBJID": ColumnMetadata("SUBJID", "INT", "identifier", False, False, False, description="Subject sequence number within site", example_values=[1, 2]),
            "SITEID": ColumnMetadata("SITEID", "VARCHAR(50)", "identifier", False, False, True, "sites.SITEID", "Clinical site where subject enrolled", example_values=["SITE003"]),
            "AGE": ColumnMetadata("AGE", "INT", "numeric", False, False, False, description="Age in years at baseline", example_values=[55, 38, 51]),
            "SEX": ColumnMetadata("SEX", "VARCHAR(10)", "categorical", False, False, False, description="Sex of subject (M/F)", example_values=["M", "F"]),
            "RACE": ColumnMetadata("RACE", "VARCHAR(50)", "categorical", False, False, False, description="Race of subject", example_values=["ASIAN"]),
            "COUNTRY": ColumnMetadata("COUNTRY", "VARCHAR(50)", "categorical", False, False, False, description="Country of enrollment", example_values=["INDIA"]),
            "ARMCD": ColumnMetadata("ARMCD", "VARCHAR(50)", "categorical", False, False, False, description="Planned Arm code (e.g. PLC, DRUGX)", example_values=["PLC", "TRT"]),
            "ARM": ColumnMetadata("ARM", "VARCHAR(100)", "categorical", False, False, False, description="Planned Arm name (e.g. Placebo, Active Treatment)", example_values=["Placebo", "Drug X 100mg"]),
            "RFSTDTC": ColumnMetadata("RFSTDTC", "DATE", "date", False, False, False, description="Subject reference start date", example_values=["2025-02-01"]),
            "RFENDTC": ColumnMetadata("RFENDTC", "DATE", "date", False, False, False, description="Subject reference end date", example_values=["2025-08-15"]),
        },
        kpi_usage=["Total Subjects", "Average Age", "Sex Distribution", "Enrollment by Site", "Arm Breakdown"],
    ),

    # ── 4. AE (Adverse Events - SDTM) ────────────────────────────────────────
    "ae": DatasetMetadata(
        name="ae",
        domain="Adverse Events",
        category="SDTM",
        description="Adverse events domain capturing observed toxicities and medical incidents.",
        purpose="Records all adverse events, MedDRA preferred terms, body systems, severity, and causality.",
        primary_key=["USUBJID", "AESEQ"],
        foreign_keys={"USUBJID": "dm.USUBJID"},
        subject_level=False,
        analysis_level="event",
        clinical_role="Safety event reporting and MedDRA categorization",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "DOMAIN": ColumnMetadata("DOMAIN", "VARCHAR(10)", "categorical", False, False, False, description="CDISC domain ('AE')", example_values=["AE"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "dm.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "AESEQ": ColumnMetadata("AESEQ", "INT", "identifier", False, True, False, description="Adverse event sequence number for subject", example_values=[1]),
            "AETERM": ColumnMetadata("AETERM", "VARCHAR(255)", "text", False, False, False, description="Verbatim reported adverse event term", example_values=["Serious Infection", "Headache"]),
            "AEDECOD": ColumnMetadata("AEDECOD", "VARCHAR(255)", "categorical", False, False, False, description="MedDRA Preferred Term (PT)", example_values=["Serious Infection", "Headache"]),
            "AEBODSYS": ColumnMetadata("AEBODSYS", "VARCHAR(255)", "categorical", False, False, False, description="MedDRA System Organ Class (SOC)", example_values=["Infections and Infestations", "Nervous System Disorders"]),
            "AESEV": ColumnMetadata("AESEV", "VARCHAR(50)", "categorical", False, False, False, description="Adverse event severity (MILD, MODERATE, SEVERE)", example_values=["MILD", "MODERATE", "SEVERE"]),
            "AESER": ColumnMetadata("AESER", "VARCHAR(1)", "flag", False, False, False, description="Serious Adverse Event flag (Y/N)", example_values=["Y", "N"]),
            "AEREL": ColumnMetadata("AEREL", "VARCHAR(50)", "categorical", False, False, False, description="Causality relationship to study treatment", example_values=["RELATED", "NOT RELATED"]),
            "AESTDTC": ColumnMetadata("AESTDTC", "DATE", "date", False, False, False, description="Adverse event onset start date", example_values=["2025-03-15"]),
            "AEENDTC": ColumnMetadata("AEENDTC", "DATE", "date", False, False, False, description="Adverse event resolution end date", example_values=["2025-03-20"]),
        },
        kpi_usage=["Adverse Event Count", "Serious Adverse Event Count", "AE Severity Distribution", "MedDRA SOC Frequency"],
    ),

    # ── 5. EX (Exposure - SDTM) ──────────────────────────────────────────────
    "ex": DatasetMetadata(
        name="ex",
        domain="Exposure",
        category="SDTM",
        description="Records study drug administration and dosage history.",
        purpose="Tracks actual dosing amounts, dose units, administration route, and exposure duration.",
        primary_key=["USUBJID", "EXSEQ"],
        foreign_keys={"USUBJID": "dm.USUBJID"},
        subject_level=False,
        analysis_level="record",
        clinical_role="Treatment dosing and exposure verification",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "DOMAIN": ColumnMetadata("DOMAIN", "VARCHAR(10)", "categorical", False, False, False, description="CDISC domain ('EX')", example_values=["EX"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "dm.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "EXSEQ": ColumnMetadata("EXSEQ", "INT", "identifier", False, True, False, description="Exposure sequence number", example_values=[1]),
            "EXTRT": ColumnMetadata("EXTRT", "VARCHAR(100)", "categorical", False, False, False, description="Administered treatment name", example_values=["Placebo", "Drug X 100mg"]),
            "EXDOSE": ColumnMetadata("EXDOSE", "DOUBLE", "numeric", False, False, False, description="Dose amount administered", example_values=[0, 100]),
            "EXDOSU": ColumnMetadata("EXDOSU", "VARCHAR(50)", "categorical", False, False, False, description="Dose units (e.g. mg)", example_values=["mg"]),
            "EXROUTE": ColumnMetadata("EXROUTE", "VARCHAR(50)", "categorical", False, False, False, description="Route of administration (e.g. ORAL)", example_values=["ORAL"]),
            "EXSTDTC": ColumnMetadata("EXSTDTC", "DATE", "date", False, False, False, description="Start date of treatment exposure", example_values=["2025-02-01"]),
            "EXENDTC": ColumnMetadata("EXENDTC", "DATE", "date", False, False, False, description="End date of treatment exposure", example_values=["2025-08-15"]),
        },
        kpi_usage=["Treatment Exposure", "Cumulative Dose", "Treatment Duration"],
    ),

    # ── 6. LB (Laboratory - SDTM) ────────────────────────────────────────────
    "lb": DatasetMetadata(
        name="lb",
        domain="Laboratory",
        category="SDTM",
        description="Clinical laboratory test results and normal reference indicators.",
        purpose="Raw lab measurements, standard units, visit schedules, and reference ranges.",
        primary_key=["USUBJID", "LBSEQ"],
        foreign_keys={"USUBJID": "dm.USUBJID"},
        subject_level=False,
        analysis_level="finding",
        clinical_role="Raw laboratory findings",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "DOMAIN": ColumnMetadata("DOMAIN", "VARCHAR(10)", "categorical", False, False, False, description="CDISC domain ('LB')", example_values=["LB"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "dm.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "LBTESTCD": ColumnMetadata("LBTESTCD", "VARCHAR(50)", "categorical", False, False, False, description="Short lab test code (e.g. HGB)", example_values=["HGB"]),
            "LBTEST": ColumnMetadata("LBTEST", "VARCHAR(100)", "categorical", False, False, False, description="Full lab test name (e.g. Hemoglobin)", example_values=["Hemoglobin"]),
            "LBORRES": ColumnMetadata("LBORRES", "DOUBLE", "numeric", False, False, False, description="Original lab measurement result", example_values=[10.3, 10.2]),
            "LBORRESU": ColumnMetadata("LBORRESU", "VARCHAR(50)", "categorical", False, False, False, description="Original unit of measurement (e.g. g/dL)", example_values=["g/dL"]),
            "VISIT": ColumnMetadata("VISIT", "VARCHAR(50)", "categorical", False, False, False, description="Clinical visit name (BASELINE, WEEK 8)", example_values=["BASELINE", "WEEK 8"]),
            "LBSEQ": ColumnMetadata("LBSEQ", "INT", "identifier", False, True, False, description="Lab sequence number for subject", example_values=[1, 2]),
            "LBDTC": ColumnMetadata("LBDTC", "DATE", "date", False, False, False, description="Date of lab specimen collection", example_values=["2025-02-01"]),
            "LBNRIND": ColumnMetadata("LBNRIND", "VARCHAR(50)", "categorical", False, False, False, description="Reference range indicator (NORMAL, HIGH, LOW)", example_values=["NORMAL"]),
        },
        kpi_usage=["Raw Lab Measurement", "Lab Normal Range Frequency"],
    ),

    # ── 7. QS (Questionnaires / Scales - SDTM) ───────────────────────────────
    "qs": DatasetMetadata(
        name="qs",
        domain="Questionnaires",
        category="SDTM",
        description="Patient-reported outcomes and clinician disease rating scale measurements.",
        purpose="Tracks questionnaire items, disease severity scales, and score outcomes across visits.",
        primary_key=["USUBJID", "QSSEQ"],
        foreign_keys={"USUBJID": "dm.USUBJID"},
        subject_level=False,
        analysis_level="finding",
        clinical_role="Disease scale rating and patient-reported outcomes",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "DOMAIN": ColumnMetadata("DOMAIN", "VARCHAR(10)", "categorical", False, False, False, description="CDISC domain ('QS')", example_values=["QS"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "dm.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "QSTESTCD": ColumnMetadata("QSTESTCD", "VARCHAR(50)", "categorical", False, False, False, description="Short questionnaire test code (DISEASE)", example_values=["DISEASE"]),
            "QSTEST": ColumnMetadata("QSTEST", "VARCHAR(100)", "categorical", False, False, False, description="Full scale name (Clinical Disease Score)", example_values=["Clinical Disease Score"]),
            "QSORRES": ColumnMetadata("QSORRES", "DOUBLE", "numeric", False, False, False, description="Score result value", example_values=[64.2, 59.1]),
            "QSORRESU": ColumnMetadata("QSORRESU", "VARCHAR(50)", "categorical", False, False, False, description="Score unit", example_values=["SCORE"]),
            "VISIT": ColumnMetadata("VISIT", "VARCHAR(50)", "categorical", False, False, False, description="Visit name (BASELINE, WEEK 8)", example_values=["BASELINE", "WEEK 8"]),
            "QSSEQ": ColumnMetadata("QSSEQ", "INT", "identifier", False, True, False, description="Questionnaire sequence number", example_values=[1, 2]),
            "QSDTC": ColumnMetadata("QSDTC", "DATE", "date", False, False, False, description="Assessment date", example_values=["2025-02-01"]),
        },
        kpi_usage=["Disease Activity Score", "Questionnaire Longitudinal Score"],
    ),

    # ── 8. VS (Vital Signs - SDTM) ───────────────────────────────────────────
    "vs": DatasetMetadata(
        name="vs",
        domain="Vital Signs",
        category="SDTM",
        description="Physical vital signs measurements (Blood Pressure, Heart Rate, etc.).",
        purpose="Records raw vital parameter readings across clinical visits.",
        primary_key=["USUBJID", "VSSEQ"],
        foreign_keys={"USUBJID": "dm.USUBJID"},
        subject_level=False,
        analysis_level="finding",
        clinical_role="Physical vital sign observations",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "DOMAIN": ColumnMetadata("DOMAIN", "VARCHAR(10)", "categorical", False, False, False, description="CDISC domain ('VS')", example_values=["VS"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "dm.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "VSTESTCD": ColumnMetadata("VSTESTCD", "VARCHAR(50)", "categorical", False, False, False, description="Short test code (e.g. SYSBP)", example_values=["SYSBP"]),
            "VSTEST": ColumnMetadata("VSTEST", "VARCHAR(100)", "categorical", False, False, False, description="Full vital test name (e.g. Systolic Blood Pressure)", example_values=["Systolic Blood Pressure"]),
            "VSORRES": ColumnMetadata("VSORRES", "DOUBLE", "numeric", False, False, False, description="Vital measurement value", example_values=[131.4, 129.6]),
            "VSORRESU": ColumnMetadata("VSORRESU", "VARCHAR(50)", "categorical", False, False, False, description="Measurement unit (e.g. mmHg)", example_values=["mmHg"]),
            "VISIT": ColumnMetadata("VISIT", "VARCHAR(50)", "categorical", False, False, False, description="Visit name (BASELINE, WEEK 8)", example_values=["BASELINE", "WEEK 8"]),
            "VSSEQ": ColumnMetadata("VSSEQ", "INT", "identifier", False, True, False, description="Sequence number for subject", example_values=[1, 2]),
            "VSDTC": ColumnMetadata("VSDTC", "DATE", "date", False, False, False, description="Date of vital measurement", example_values=["2025-02-01"]),
        },
        kpi_usage=["Raw Vital Sign Measurement", "Blood Pressure Tracking"],
    ),

    # ── 9. ADSL (Subject-Level Analysis Dataset - ADaM) ──────────────────────
    "adsl": DatasetMetadata(
        name="adsl",
        domain="Subject-Level Analysis",
        category="ADaM",
        description="One-record-per-subject ADaM dataset containing analysis populations, treatment, and dates.",
        purpose="Primary denominator dataset for all statistical and clinical efficacy and safety analyses.",
        primary_key=["USUBJID"],
        foreign_keys={"USUBJID": "dm.USUBJID"},
        subject_level=True,
        analysis_level="subject",
        clinical_role="Analysis master subject table; denominator for incidence and rate calculations",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "dm.USUBJID", "Unique subject identifier", example_values=["STDY001-0001"]),
            "SUBJID": ColumnMetadata("SUBJID", "INT", "identifier", False, False, False, description="Subject ID within site", example_values=[1, 2]),
            "SITEID": ColumnMetadata("SITEID", "VARCHAR(50)", "identifier", False, False, False, description="Enrolling site ID", example_values=["SITE003"]),
            "AGE": ColumnMetadata("AGE", "INT", "numeric", False, False, False, description="Baseline age in years", example_values=[55, 38]),
            "SEX": ColumnMetadata("SEX", "VARCHAR(10)", "categorical", False, False, False, description="Sex (M/F)", example_values=["M", "F"]),
            "TRT01P": ColumnMetadata("TRT01P", "VARCHAR(100)", "categorical", False, False, False, description="Planned treatment for Period 01", example_values=["Placebo", "Drug X 100mg"]),
            "TRT01A": ColumnMetadata("TRT01A", "VARCHAR(100)", "categorical", False, False, False, description="Actual treatment for Period 01 (governs safety analysis)", example_values=["Placebo", "Drug X 100mg"]),
            "SAFFL": ColumnMetadata("SAFFL", "VARCHAR(1)", "flag", False, False, False, description="Safety Population Flag (Y/N)", example_values=["Y"]),
            "ITTFL": ColumnMetadata("ITTFL", "VARCHAR(1)", "flag", False, False, False, description="Intent-To-Treat Population Flag (Y/N)", example_values=["Y"]),
            "PPROTFL": ColumnMetadata("PPROTFL", "VARCHAR(1)", "flag", False, False, False, description="Per-Protocol Population Flag (Y/N)", example_values=["Y"]),
            "RANDDT": ColumnMetadata("RANDDT", "DATE", "date", False, False, False, description="Randomization date", example_values=["2025-01-25"]),
            "TRTSDT": ColumnMetadata("TRTSDT", "DATE", "date", False, False, False, description="First treatment start date", example_values=["2025-02-01"]),
            "TRTEDT": ColumnMetadata("TRTEDT", "DATE", "date", False, False, False, description="Last treatment end date", example_values=["2025-08-15"]),
            "EOSDT": ColumnMetadata("EOSDT", "DATE", "date", False, False, False, description="End of study disposition date", example_values=["2025-08-15"]),
        },
        kpi_usage=["Total Subjects", "Subjects by Treatment Arm", "Safety Population", "ITT Population", "Subject Disposition"],
    ),

    # ── 10. ADAE (Adverse Event Analysis - ADaM) ─────────────────────────────
    "adae": DatasetMetadata(
        name="adae",
        domain="Adverse Event Analysis",
        category="ADaM",
        description="Analysis-ready adverse events dataset with treatment assignment and timing flags.",
        purpose="Used for calculating adverse event rates, treatment-emergent AEs, and safety summaries.",
        primary_key=["USUBJID"],
        foreign_keys={"USUBJID": "adsl.USUBJID"},
        subject_level=True,
        analysis_level="event",
        clinical_role="Safety and adverse event statistical analysis",
        important_columns={
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "adsl.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "AEDECOD": ColumnMetadata("AEDECOD", "VARCHAR(255)", "categorical", False, False, False, description="MedDRA Preferred Term (PT)", example_values=["Serious Infection", "Headache"]),
            "AEBODSYS": ColumnMetadata("AEBODSYS", "VARCHAR(255)", "categorical", False, False, False, description="MedDRA System Organ Class (SOC)", example_values=["Infections and Infestations", "Nervous System Disorders"]),
            "AESEV": ColumnMetadata("AESEV", "VARCHAR(50)", "categorical", False, False, False, description="Adverse event severity (MILD, MODERATE, SEVERE)", example_values=["MILD", "MODERATE", "SEVERE"]),
            "AESER": ColumnMetadata("AESER", "VARCHAR(1)", "flag", False, False, False, description="Serious Adverse Event flag (Y/N)", example_values=["Y", "N"]),
            "AEREL": ColumnMetadata("AEREL", "VARCHAR(50)", "categorical", False, False, False, description="Causality relationship (RELATED, NOT RELATED)", example_values=["RELATED", "NOT RELATED"]),
            "TRT01A": ColumnMetadata("TRT01A", "VARCHAR(100)", "categorical", False, False, False, description="Actual treatment received", example_values=["Placebo", "Drug X 100mg"]),
            "ASTDT": ColumnMetadata("ASTDT", "DATE", "date", False, False, False, description="Analysis AE start date", example_values=["2025-03-15"]),
            "AENDT": ColumnMetadata("AENDT", "DATE", "date", False, False, False, description="Analysis AE end date", example_values=["2025-03-20"]),
            "TRTEMFL": ColumnMetadata("TRTEMFL", "VARCHAR(1)", "flag", False, False, False, description="Treatment-Emergent Adverse Event flag (Y/N)", example_values=["Y"]),
            "SAFFL": ColumnMetadata("SAFFL", "VARCHAR(1)", "flag", False, False, False, description="Safety Population flag (Y/N)", example_values=["Y"]),
        },
        kpi_usage=["Adverse Event Rate", "AE Rate by Treatment Arm", "Serious AE Rate", "Treatment-Emergent AE Count"],
    ),

    # ── 11. ADLB (Laboratory Analysis - ADaM) ────────────────────────────────
    "adlb": DatasetMetadata(
        name="adlb",
        domain="Laboratory Analysis",
        category="ADaM",
        description="Analysis-ready laboratory dataset with derived baseline values and change from baseline.",
        purpose="Used for evaluating drug efficacy and safety effects on laboratory biomarkers.",
        primary_key=["USUBJID", "PARAMCD", "AVISIT"],
        foreign_keys={"USUBJID": "adsl.USUBJID"},
        subject_level=False,
        analysis_level="visit_parameter",
        clinical_role="Biomarker efficacy and safety statistical evaluation",
        important_columns={
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "adsl.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "TRT01A": ColumnMetadata("TRT01A", "VARCHAR(100)", "categorical", False, False, False, description="Actual treatment received", example_values=["Placebo", "Drug X 100mg"]),
            "AVISIT": ColumnMetadata("AVISIT", "VARCHAR(50)", "categorical", False, True, False, description="Analysis visit name (BASELINE, WEEK 8)", example_values=["BASELINE", "WEEK 8"]),
            "AVAL": ColumnMetadata("AVAL", "DOUBLE", "numeric", False, False, False, description="Analysis numeric value at visit", example_values=[10.3, 10.2]),
            "BASE": ColumnMetadata("BASE", "DOUBLE", "numeric", False, False, False, description="Baseline value for parameter", example_values=[10.3]),
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "PARAMCD": ColumnMetadata("PARAMCD", "VARCHAR(50)", "categorical", False, True, False, description="Parameter code (e.g. HGB)", example_values=["HGB"]),
            "PARAM": ColumnMetadata("PARAM", "VARCHAR(100)", "categorical", False, False, False, description="Parameter description (e.g. Hemoglobin)", example_values=["Hemoglobin"]),
            "AVALU": ColumnMetadata("AVALU", "VARCHAR(50)", "categorical", False, False, False, description="Analysis parameter unit (g/dL)", example_values=["g/dL"]),
            "CHG": ColumnMetadata("CHG", "DOUBLE", "numeric", False, False, False, description="Absolute change from baseline (AVAL - BASE)", example_values=[0.0, -0.1]),
            "PCHG": ColumnMetadata("PCHG", "DOUBLE", "numeric", False, False, False, description="Percentage change from baseline ((AVAL - BASE) / BASE * 100)", example_values=[0.0, -0.97]),
            "ANL01FL": ColumnMetadata("ANL01FL", "VARCHAR(1)", "flag", False, False, False, description="Primary analysis record flag (Y/N)", example_values=["Y"]),
        },
        kpi_usage=["Mean Laboratory Value", "Lab Change from Baseline", "Lab Percent Change from Baseline"],
    ),

    # ── 12. ADVS (Vital Signs Analysis - ADaM) ───────────────────────────────
    "advs": DatasetMetadata(
        name="advs",
        domain="Vital Signs Analysis",
        category="ADaM",
        description="Analysis-ready vital signs dataset with baseline and change from baseline.",
        purpose="Used for evaluating hemodynamic effects, blood pressure changes, and vital sign shifts.",
        primary_key=["USUBJID", "PARAMCD", "AVISIT"],
        foreign_keys={"USUBJID": "adsl.USUBJID"},
        subject_level=False,
        analysis_level="visit_parameter",
        clinical_role="Hemodynamic and vital signs analysis",
        important_columns={
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "adsl.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "TRT01A": ColumnMetadata("TRT01A", "VARCHAR(100)", "categorical", False, False, False, description="Actual treatment received", example_values=["Placebo", "Drug X 100mg"]),
            "AVISIT": ColumnMetadata("AVISIT", "VARCHAR(50)", "categorical", False, True, False, description="Analysis visit name (BASELINE, WEEK 8)", example_values=["BASELINE", "WEEK 8"]),
            "AVAL": ColumnMetadata("AVAL", "DOUBLE", "numeric", False, False, False, description="Analysis vital sign reading", example_values=[131.4, 129.6]),
            "BASE": ColumnMetadata("BASE", "DOUBLE", "numeric", False, False, False, description="Baseline vital sign reading", example_values=[131.4]),
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "PARAMCD": ColumnMetadata("PARAMCD", "VARCHAR(50)", "categorical", False, True, False, description="Vital parameter code (SYSBP)", example_values=["SYSBP"]),
            "PARAM": ColumnMetadata("PARAM", "VARCHAR(100)", "categorical", False, False, False, description="Vital parameter description (Systolic Blood Pressure)", example_values=["Systolic Blood Pressure"]),
            "AVALU": ColumnMetadata("AVALU", "VARCHAR(50)", "categorical", False, False, False, description="Vital measurement unit (mmHg)", example_values=["mmHg"]),
            "CHG": ColumnMetadata("CHG", "DOUBLE", "numeric", False, False, False, description="Absolute change from baseline", example_values=[0.0, -1.8]),
            "PCHG": ColumnMetadata("PCHG", "DOUBLE", "numeric", False, False, False, description="Percentage change from baseline", example_values=[0.0, -1.37]),
            "ANL01FL": ColumnMetadata("ANL01FL", "VARCHAR(1)", "flag", False, False, False, description="Primary analysis record flag (Y/N)", example_values=["Y"]),
        },
        kpi_usage=["Mean Vital Sign Value", "Vital Sign Change from Baseline", "Blood Pressure Reduction"],
    ),

    # ── 13. ADRESP (Response / Efficacy Analysis - ADaM) ─────────────────────
    "adresp": DatasetMetadata(
        name="adresp",
        domain="Response / Efficacy Analysis",
        category="ADaM",
        description="Analysis dataset for primary and secondary efficacy clinical response endpoints.",
        purpose="Evaluates therapeutic disease score change, responder thresholds, and treatment efficacy.",
        primary_key=["USUBJID", "PARAMCD", "AVISIT"],
        foreign_keys={"USUBJID": "adsl.USUBJID"},
        subject_level=False,
        analysis_level="visit_parameter",
        clinical_role="Primary trial efficacy evaluation and responder analysis",
        important_columns={
            "USUBJID": ColumnMetadata("USUBJID", "VARCHAR(50)", "identifier", False, True, True, "adsl.USUBJID", "Subject identifier", example_values=["STDY001-0001"]),
            "TRT01A": ColumnMetadata("TRT01A", "VARCHAR(100)", "categorical", False, False, False, description="Actual treatment received", example_values=["Placebo", "Drug X 100mg"]),
            "AVISIT": ColumnMetadata("AVISIT", "VARCHAR(50)", "categorical", False, True, False, description="Analysis visit name (BASELINE, WEEK 8)", example_values=["BASELINE", "WEEK 8"]),
            "AVAL": ColumnMetadata("AVAL", "DOUBLE", "numeric", False, False, False, description="Efficacy score value", example_values=[64.2, 59.1]),
            "BASE": ColumnMetadata("BASE", "DOUBLE", "numeric", False, False, False, description="Baseline efficacy score value", example_values=[64.2]),
            "STUDYID": ColumnMetadata("STUDYID", "VARCHAR(50)", "identifier", False, False, False, description="Study identifier", example_values=["STDY001"]),
            "PARAMCD": ColumnMetadata("PARAMCD", "VARCHAR(50)", "categorical", False, True, False, description="Efficacy parameter code (DISEASE)", example_values=["DISEASE"]),
            "PARAM": ColumnMetadata("PARAM", "VARCHAR(100)", "categorical", False, False, False, description="Efficacy parameter description (Clinical Disease Score)", example_values=["Clinical Disease Score"]),
            "AVALU": ColumnMetadata("AVALU", "VARCHAR(50)", "categorical", False, False, False, description="Efficacy unit (SCORE)", example_values=["SCORE"]),
            "CHG": ColumnMetadata("CHG", "DOUBLE", "numeric", False, False, False, description="Disease score reduction (AVAL - BASE)", example_values=[0.0, -5.1]),
            "PCHG": ColumnMetadata("PCHG", "DOUBLE", "numeric", False, False, False, description="Disease score percentage reduction", example_values=[0.0, -7.94]),
            "ANL01FL": ColumnMetadata("ANL01FL", "VARCHAR(1)", "flag", False, False, False, description="Analysis flag (Y/N)", example_values=["Y"]),
            "RESPFL": ColumnMetadata("RESPFL", "VARCHAR(1)", "flag", False, False, False, description="Efficacy clinical responder indicator (Y/N)", example_values=["Y", "N"]),
        },
        kpi_usage=["Efficacy Response Count", "Efficacy Response Rate", "Disease Score Reduction by Treatment Arm"],
    ),
}
