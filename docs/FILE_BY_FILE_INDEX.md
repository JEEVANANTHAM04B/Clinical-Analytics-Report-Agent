# Maintained-file index — current checkout

Generated from source by `scripts/build_file_index.py`. Each entry gives the file's purpose, line count, external/direct imports, and exact source locations for top-level Python symbols or selected frontend declarations. Open the source for statement-level behavior; read [CURRENT_PROJECT_WORKFLOW_GUIDE.md](CURRENT_PROJECT_WORKFLOW_GUIDE.md) for the call chain and clinical meaning.

Maintained files indexed: **247** (including this generated index). This omits installed packages, generated builds, output PDFs/images, temporary browser/test files, and clinical source datasets. `.env` is deliberately omitted because it may contain secrets; `.env.example` is indexed.

## .env.example

### [.env.example](../.env.example)

Non-secret template for MySQL, model, Redis, and upload settings; copy to a private `.env` before local startup. **41 lines.**

## .gitignore

### [.gitignore](../.gitignore)

Ignore rules for local secrets, dependencies, caches, and generated artifacts. **101 lines.**

## app

### [app/__init__.py](../app/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **11 lines.**

### [app/ai/__init__.py](../app/ai/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **0 lines.**

### [app/ai/insight_generator.py](../app/ai/insight_generator.py)

Produces narrative insight from verified rows with deterministic fallback. **347 lines.**

Direct imports: `decimal`, `re`, `typing`.

Entry points/declarations: `_is_clinical_context` function L16–40 — Determine if the current analysis belongs to the CDISC clinical trial dataset.; `_deterministic_insight_fallback` function L43–233 — Generate an insight directly from verified query results and; `generate_insight` function L236–347 — Generate a clinical analytics insight using:.

### [app/ai/insight_regenerator.py](../app/ai/insight_regenerator.py)

Retries an insight with validation feedback. **70 lines.**

Direct imports: `typing`.

Entry points/declarations: `regenerate_insight` function L6–70 — Regenerate an insight after deterministic validation failure..

### [app/ai/insight_validator.py](../app/ai/insight_validator.py)

Checks insight claims against result evidence. **435 lines.**

Direct imports: `decimal`, `re`, `typing`.

Entry points/declarations: `_is_numeric` function L6–16 — Check whether a value is a supported numeric type.; `_extract_numbers` function L19–46 — Extract numeric values from insight text.; `_result_numeric_values` function L49–70 — Extract numeric values from verified SQL results.; `_result_categories` function L73–90 — Extract textual category values from verified SQL results.; `_number_exists_in_results` function L93–129 — Check whether a number exists in the verified SQL results.; `validate_insight` function L132–435 — Deterministically validate an LLM-generated insight..

### [app/ai/llm.py](../app/ai/llm.py)

Gemini client, model cascade, generation, and retry/failure handling. **206 lines.**

Direct imports: `dotenv`, `google`, `os`, `time`.

Entry points/declarations: `_generate_with_model` function L60–78; `generate_response` function L85–206 — Generate a response using Gemini..

### [app/ai/llm_test.py](../app/ai/llm_test.py)

Maintained project file for llm test. **12 lines.**

### [app/analytics/__init__.py](../app/analytics/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **0 lines.**

### [app/analytics/cache.py](../app/analytics/cache.py)

Optional dataset-version-scoped Redis validated-result cache. **70 lines.**

Direct imports: `hashlib`, `json`, `logging`, `os`, `redis`, `time`.

Entry points/declarations: `canonical` function L12–13; `ResultCache` class L16–70.

### [app/analytics/dashboard_service.py](../app/analytics/dashboard_service.py)

Clinical and selected-table KPI/dashboard queries. **2046 lines.**

Direct imports: `decimal`, `sqlalchemy`, `typing`.

Entry points/declarations: `_safe_float` function L42–49 — Helper to convert Decimal/int/float/None to float safely.; `_safe_int` function L51–58 — Helper to convert Decimal/int/str/None to int safely.; `calculate_clinical_kpi` function L64–73 — Executes the verified SQL template for the given KPI definition; `get_clinical_dashboard_summary` function L76–88 — Executes and aggregates all 17 clinical trial KPIs dynamically from MySQL.; `validate_selected_tables` function L95–120 — Validates selected tables against the approved MySQL schema.; `are_tables_connected` function L123–152 — Verifies that all selected tables form a single connected component; `generate_custom_dashboard` function L159–254 — Executes real MySQL queries against the selected tables and returns; `_dashboard_clinical_safety` function L261–387 — Safety analysis dashboard covering:; `_dashboard_clinical_enrollment_demographics` function L390–525 — Enrollment and Demographics analysis dashboard covering:; `_dashboard_clinical_laboratory` function L528–618 — Laboratory analysis dashboard covering:; `_dashboard_clinical_vitals` function L621–711 — Vital signs analysis dashboard covering:; `_dashboard_clinical_efficacy` function L714–807 — Efficacy analysis dashboard covering:; `_dashboard_clinical_disposition` function L810–889 — Subject disposition and trial milestone dashboard (adsl):; `_dashboard_clinical_single_table` function L892–1163 — Dedicated handler for individual CDISC clinical tables.; `_dashboard_clinical_general` function L1166–1242 — General clinical combination fallback for linked clinical tables.; `_dashboard_encounters_conditions` function L1249–1334; `_dashboard_encounters_medications` function L1337–1413; `_dashboard_encounters_procedures` function L1416–1491; `_dashboard_encounters_observations` function L1494–1569; `_dashboard_patients_encounters` function L1572–1645; `_dashboard_patients_conditions` function L1648–1709; `_dashboard_patients_medications` function L1712–1773; `_dashboard_patients_procedures` function L1776–1837; `_dashboard_patients_observations` function L1840–1901; `_dashboard_single_table` function L1904–2046.

### [app/analytics/eda.py](../app/analytics/eda.py)

Result-level quality assessment helper; dataset-wide EDA is under ingestion. **89 lines.**

Direct imports: `collections`, `datetime`, `pandas`.

Entry points/declarations: `assess_results` function L8–89.

### [app/analytics/followup_service.py](../app/analytics/followup_service.py)

Answers follow-up questions using prior analysis context. **630 lines.**

Direct imports: `logging`, `re`, `typing`.

Entry points/declarations: `_is_clinical_context` function L25–80 — Detect whether the follow-up session targets the CDISC clinical-trial dataset; `_is_unrelated_new_analysis` function L83–110 — Detect if the user is asking for a completely new, unrelated analytical topic; `_extract_metric_key_and_label` function L113–166 — Identify category key, metric key, and friendly label from a result row.; `_format_metric_val` function L169–184 — Format numeric value with appropriate clinical unit.; `_get_category_group` function L187–206 — Return plural category group and singular form.; `_answer_deterministically` function L209–304 — Provide an accurate, verified deterministic answer directly from result rows; `_generate_llm_answer` function L307–397 — Generate a natural, clinician-friendly answer using Gemini over the verified data context.; `_try_follow_up_sql` function L400–508 — If additional data is genuinely needed, generate and execute a minimal,; `process_followup_question` function L511–630 — Main entry point for processing a follow-up analysis question..

### [app/analytics/insight_evidence.py](../app/analytics/insight_evidence.py)

Builds numerical/category evidence from verified result rows. **373 lines.**

Direct imports: `decimal`, `re`, `typing`.

Entry points/declarations: `_is_num` function L6–7; `_find_category_key` function L10–42; `build_insight_evidence` function L45–149 — Build deterministic evidence from validated SQL results.; `_extract_numbers` function L152–177 — Extract numeric values from insight text.; `_result_numeric_values` function L180–194 — Extract all numeric values from verified SQL results.; `_result_categories` function L197–211 — Extract textual category values from verified SQL results.; `_number_exists_in_results` function L214–227 — Check whether an insight number exists; `validate_insight` function L230–373 — Deterministically validate an LLM-generated insight.

### [app/analytics/query_executor.py](../app/analytics/query_executor.py)

Revalidates and executes bounded read-only SQL against MySQL. **30 lines.**

Direct imports: `sqlalchemy`.

Entry points/declarations: `execute_query` function L7–30.

### [app/analytics/result_validator.py](../app/analytics/result_validator.py)

Checks result row shape and values, with transport normalization. **101 lines.**

Direct imports: `datetime`, `decimal`, `math`, `sqlglot`, `typing`.

Entry points/declarations: `normalize_value` function L8–13; `normalize_row` function L16–17; `result_contract` function L20–57 — Derive output names/grain only when the SELECT explicitly supplies them.; `validate_results` function L60–101.

### [app/analytics/sql_generator.py](../app/analytics/sql_generator.py)

Gemini/deterministic clinical question-and-plan to SQL conversion. **674 lines.**

Direct imports: `re`, `typing`.

Entry points/declarations: `_is_clinical_context` function L16–33 — Detect whether the execution context targets CDISC clinical-trial schema; `_build_clinical_prompt` function L40–225 — Builds an authoritative prompt for Gemini targeting the 13 CDISC; `_check_sql_vs_clinical_plan` function L232–291 — Lightweight inline validation: does the LLM-generated SQL satisfy; `_build_legacy_ehr_prompt` function L298–367 — Builds prompt for legacy EHR schema queries.; `_build_sql_from_plan` function L370–469 — Build a SQL query deterministically from the key requirements; `_check_sql_vs_plan` function L471–532 — Lightweight inline check for legacy EHR plan consistency.; `_deterministic_sql_fallback` function L538–553 — Fallback used specifically when the LLM is temporarily unavailable.; `generate_sql` function L560–674 — Main SQL generation engine..

### [app/analytics/sql_validator.py](../app/analytics/sql_validator.py)

Read-only SQL AST, schema, column, and safety validation. **515 lines.**

Direct imports: `re`, `typing`.

Entry points/declarations: `_check_unqualified_columns` function L35–94 — Validates unqualified column names referenced in the query against; `_extract_plan_datasets` function L97–155 — Extract dataset table names from Section 1 ('Relevant Tables and Columns'); `validate_sql` function L157–515 — Validates a SQL query for safety, security, and strict clinical schema conformance..

### [app/api/__init__.py](../app/api/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **13 lines.**

### [app/api/analytics.py](../app/api/analytics.py)

Analytics, dashboards, follow-up, and PDF generation endpoints. **527 lines.**

Direct imports: `fastapi`, `sqlalchemy`, `uuid`.

Entry points/declarations: `_top_adverse_events` function L36–47 — Use the dashboard's distinct-subject definition for ADAE event terms.; `customize_dashboard` function L56–64; `get_analytics_overview` function L72–241; `run_analytics` function L249–373; `answer_followup` function L382–389; `generate_pdf_report` function L397–494; `download_latest_pdf_report` function L499–503; `download_pdf_report_get` function L507–514; `saved_analysis` function L518–527.

### [app/api/database.py](../app/api/database.py)

Dataset registry, metadata, load, and audit-list endpoints. **444 lines.**

Direct imports: `fastapi`, `sqlalchemy`, `typing`.

Entry points/declarations: `load_clinical_dataset` function L86–149 — Load a validated clinical dataset into MySQL.; `list_dataset_versions` function L163–173 — Retrieve history of loaded dataset versions.; `get_version_columns` function L191–209 — Retrieve column metadata for a specific dataset version.; `list_persisted_relationships` function L223–229 — Retrieve analyst-reviewed relationships persisted in MySQL.; `list_audit_logs` function L243–277 — Retrieve platform audit logs from MySQL, ordered newest first.; `list_clinical_tables` function L290–355 — Retrieve approved clinical data tables and schema columns from the authoritative registry.; `get_dataset_registry` function L369–395 — Returns dataset registry entries with classifications and approval status.; `update_dataset_registry_status` function L404–424 — Updates dataset classification and approval status in the registry.; `approve_clinical_dataset` function L433–444 — Approves a dataset for clinical analytics..

### [app/api/health.py](../app/api/health.py)

API and MySQL health endpoints. **149 lines.**

Direct imports: `datetime`, `fastapi`.

Entry points/declarations: `health_check` function L63–87 — Basic liveness check — confirms the FastAPI server is running.; `database_health_check` function L103–149 — Full health check — confirms both API and MySQL are working..

### [app/api/ingestion.py](../app/api/ingestion.py)

Upload, preview, and multi-file analysis endpoints. **710 lines.**

Direct imports: `datetime`, `fastapi`, `os`, `pandas`, `re`, `sqlalchemy`, `typing`.

Entry points/declarations: `upload_dataset` function L92–337 — Upload and validate a clinical dataset file.; `preview_dataset` function L355–613 — Previews dataset file before committing to MySQL.; `analyze_clinical_datasets` function L638–710 — Analyzes one or more clinical CSV/XLSX datasets..

### [app/api/relationships.py](../app/api/relationships.py)

Relationship-candidate inspection and review endpoints. **464 lines.**

Direct imports: `fastapi`, `pathlib`.

Entry points/declarations: `list_relationship_candidates` function L79–92 — Retrieve all relationship candidates discovered during dataset analysis.; `list_approved_relationships` function L109–117 — Retrieve all relationships approved by the analyst.; `list_rejected_relationships` function L131–139 — Retrieve all relationship candidates rejected by the analyst.; `review_relationship` function L162–264 — Process an analyst decision on a candidate relationship.; `regenerate_relationship_endpoint` function L293–464 — Generate and validate an alternative relationship proposal..

### [app/audit/__init__.py](../app/audit/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **8 lines.**

### [app/audit/service.py](../app/audit/service.py)

Persists and reads operational audit events in MySQL. **151 lines.**

Direct imports: `datetime`, `sqlalchemy`, `typing`.

Entry points/declarations: `record_audit_event` function L34–95 — Persists a real audit event record directly into the MySQL 'audit_logs' table.; `get_audit_trail` function L98–151 — Retrieves real audit log records from the MySQL 'audit_logs' table, ordered newest first..

### [app/clinical/__init__.py](../app/clinical/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **54 lines.**

### [app/clinical/dataset_metadata.py](../app/clinical/dataset_metadata.py)

Clinical domain dataset and column metadata definitions. **418 lines.**

Direct imports: `dataclasses`, `typing`.

Entry points/declarations: `ColumnMetadata` class L13–23 — Metadata for an individual clinical dataset column.; `DatasetMetadata` class L27–40 — Metadata for a CDISC SDTM or ADaM clinical-trial dataset..

### [app/clinical/dataset_registry_service.py](../app/clinical/dataset_registry_service.py)

Approved dataset registry persistence and status changes. **468 lines.**

Direct imports: `datetime`, `sqlalchemy`, `typing`.

Entry points/declarations: `ensure_registry_initialized` function L155–264 — Initializes the clinical_dataset_registry table in MySQL and seeds; `get_approved_clinical_tables` function L267–295 — Returns the list of lowercase table names that are:; `is_table_approved_for_clinical_analytics` function L298–303 — Verifies whether a specific table name is approved for clinical analytics.; `register_dataset` function L306–360 — Registers or updates a dataset in the clinical dataset registry.; `update_dataset_status` function L363–404 — Updates the classification or approval status of an existing dataset.; `approve_dataset` function L407–413 — Approves a dataset for clinical analytics.; `list_all_registry_entries` function L416–468 — Lists all dataset entries in the registry with their row count and status..

### [app/clinical/kpi_definitions.py](../app/clinical/kpi_definitions.py)

Canonical clinical KPI definitions and SQL templates. **484 lines.**

Direct imports: `dataclasses`, `typing`.

Entry points/declarations: `KPIDefinition` class L13–28 — Specification of a clinical key performance indicator (KPI).; `get_kpi` function L475–477 — Retrieves a KPI definition by its identifier.; `list_kpis_by_category` function L480–484 — Returns all KPIs, optionally filtered by category..

### [app/clinical/question_mapping.py](../app/clinical/question_mapping.py)

Deterministic natural-language clinical intent and KPI mapping. **726 lines.**

Direct imports: `dataclasses`, `re`, `typing`.

Entry points/declarations: `ClinicalQuestionPlan` class L18–35 — Structured execution plan for answering a clinical question.; `build_clinical_question_plan` function L42–726 — Parses a user clinical question and deterministically resolves:.

### [app/clinical/relationship_map.py](../app/clinical/relationship_map.py)

Approved clinical relationships and join lookup. **227 lines.**

Direct imports: `dataclasses`, `typing`.

Entry points/declarations: `ClinicalRelationship` class L13–31 — Represents an approved relational link between two clinical tables.; `get_all_relationships` function L172–174 — Returns all verified clinical relationships.; `find_direct_relationship` function L177–186 — Finds a direct relationship between table_a and table_b regardless of parent/child order.; `are_tables_connected` function L189–217 — Verifies whether a given list of clinical tables forms a connected relational component.; `get_join_condition` function L220–227 — Returns SQL JOIN ON condition between table_a and table_b if directly related..

### [app/clinical/schema_registry.py](../app/clinical/schema_registry.py)

Clinical dataset/column/relationship schema catalog for prompts and checks. **213 lines.**

Direct imports: `typing`.

Entry points/declarations: `ClinicalSchemaRegistry` class L23–209 — Central registry for CDISC SDTM and ADaM clinical-trial metadata,.

### [app/clinical/table_validator.py](../app/clinical/table_validator.py)

Selected/approved table requirements and SQL table-boundary enforcement. **287 lines.**

Direct imports: `re`, `sqlglot`, `typing`.

Entry points/declarations: `get_registered_tables` function L22–43 — Returns the set of registered lowercase database table names in the active clinical database.; `validate_selected_table_allowlist` function L46–59 — Validates user-selected tables against the registered database allowlist.; `identify_required_tables` function L62–159 — Identifies the minimum required tables to answer the clinical question.; `check_table_selection` function L162–233 — Validates that user-selected tables fulfill the strict boundary required by the question.; `extract_sql_tables_ast` function L236–274 — Extracts all physical table references from a SQL query using sqlglot AST parsing.; `enforce_sql_table_boundaries` function L277–287 — Verifies that every table referenced in the SQL query (via AST) belongs.

### [app/config.py](../app/config.py)

Typed environment settings for the API, database, and uploads. **135 lines.**

Direct imports: `pydantic`, `pydantic_settings`, `typing`, `urllib`.

Entry points/declarations: `Settings` class L36–119 — Application-wide settings loaded from .env file..

### [app/core/__init__.py](../app/core/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **9 lines.**

### [app/core/database.py](../app/core/database.py)

SQLAlchemy engine, sessions, and database health helpers. **220 lines.**

Direct imports: `contextlib`, `sqlalchemy`, `typing`.

Entry points/declarations: `Base` class L86–98 — Base class for all SQLAlchemy ORM models.; `get_db_session` function L105–133 — FastAPI dependency that provides a database session per request.; `get_db_context` function L141–160 — Context manager for database sessions outside of FastAPI routes.; `check_db_connection` function L167–220 — Tests the MySQL database connection..

### [app/core/logging_config.py](../app/core/logging_config.py)

Structured application logging setup. **163 lines.**

Direct imports: `datetime`, `json`, `logging`, `sys`.

Entry points/declarations: `JSONFormatter` class L49–79 — Custom JSON log formatter for production/structured logging.; `setup_logging` function L86–133 — Configure the root logger for the entire application.; `get_logger` function L140–163 — Get a named logger for a specific module..

### [app/database/__init__.py](../app/database/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **5 lines.**

### [app/database/models.py](../app/database/models.py)

SQLAlchemy ORM models for metadata, audit, and saved reports. **205 lines.**

Direct imports: `datetime`, `sqlalchemy`, `typing`.

Entry points/declarations: `DatasetVersion` class L40–73 — Tracks versions and load history of clinical datasets in MySQL.; `DatasetColumn` class L80–111 — Stores column-level schema, data type, and semantic profiling metadata; `ApprovedRelationship` class L118–140 — Stores analyst-reviewed relationships (approved or rejected).; `AuditLog` class L147–166 — Records clinical data platform operations (ingestion, loads, review decisions).; `ClinicalDatasetRegistry` class L173–205 — Tracks clinical dataset registration, approval status, and classification..

### [app/database/repository.py](../app/database/repository.py)

Database repository CRUD for metadata and audit records. **254 lines.**

Direct imports: `datetime`, `sqlalchemy`, `typing`.

Entry points/declarations: `create_dataset_version` function L37–73 — Creates and persists a new DatasetVersion record.; `get_dataset_versions` function L76–84 — Retrieves dataset versions, optionally filtered by dataset_name.; `get_dataset_version_by_id` function L87–92 — Retrieves a single dataset version by its primary key ID.; `save_dataset_columns` function L99–127 — Persists column-level schema and profiling metadata for a dataset version.; `get_dataset_columns` function L130–140 — Retrieves column metadata for a given dataset version.; `save_relationship_review` function L147–200 — Persists an analyst review decision (APPROVE or REJECT) in MySQL.; `get_approved_relationships_from_db` function L203–211 — Retrieves relationships persisted in MySQL, optionally filtered by status (e.g. 'APPROVED' or 'REJECTED').; `create_audit_log` function L218–246 — Creates a persistent platform audit log record in MySQL.; `get_audit_logs` function L249–254 — Retrieves the most recent audit logs..

### [app/database/schema_service.py](../app/database/schema_service.py)

Reads the live MySQL table/column schema for planning and validation. **85 lines.**

Direct imports: `sqlalchemy`.

Entry points/declarations: `get_database_schema` function L16–85 — Build the analytical database schema using only approved clinical datasets.

### [app/database/session.py](../app/database/session.py)

Initializes and serves operational metadata tables/sessions. **86 lines.**

Direct imports: `sqlalchemy`, `typing`.

Entry points/declarations: `init_db` function L38–86 — Initializes metadata tables in MySQL..

### [app/ingestion/__init__.py](../app/ingestion/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **21 lines.**

### [app/ingestion/analyzer.py](../app/ingestion/analyzer.py)

Single/multi-dataset profiling, quality summaries, and relationship detection. **774 lines.**

Direct imports: `os`, `pandas`, `pathlib`, `typing`.

Entry points/declarations: `generate_dataset_quality_flags` function L51–160 — Generates human-readable, severity-ranked quality flags for an individual dataset.; `read_dataset_schema` function L167–221 — Reads only the dataset header/schema without loading the full dataset.; `analyze_single_dataset` function L228–402 — Performs full schema and data quality analysis on a single dataset file.; `analyze_datasets` function L409–609 — Analyzes multiple datasets:; `resolve_files_to_analyze` function L624–774 — Resolves actual file paths based on request parameters.

### [app/ingestion/file_reader.py](../app/ingestion/file_reader.py)

Saves uploaded files and parses CSV/XLSX into pandas DataFrames. **369 lines.**

Direct imports: `csv`, `fastapi`, `io`, `os`, `pandas`, `pathlib`, `uuid`.

Entry points/declarations: `FileReadResult` class L71–95 — Container for the output of reading an uploaded file.; `_generate_safe_filename` function L102–133 — Generate a safe, unique filename for local storage.; `_ensure_upload_directory` function L140–152 — Ensure the upload directory exists. Create it if it doesn't.; `read_uploaded_file` function L159–225 — Save an uploaded file to disk and read it into a pandas DataFrame.; `_parse_file` function L232–254 — Parse raw file bytes into a pandas DataFrame.; `_read_csv` function L257–307 — Read a CSV file from a bytes buffer into a DataFrame.; `_read_excel` function L310–350 — Read an Excel (.xlsx) file from a bytes buffer into a DataFrame.; `_check_dataframe_not_empty` function L353–369 — Raise ValueError if the DataFrame has no rows or no columns..

### [app/ingestion/file_validator.py](../app/ingestion/file_validator.py)

Checks upload type, size, and non-emptiness. **198 lines.**

Direct imports: `fastapi`, `os`.

Entry points/declarations: `ValidationResult` class L51–78 — Simple container for the outcome of file validation.; `validate_upload` function L85–198 — Validate an uploaded file before processing..

### [app/ingestion/metadata.py](../app/ingestion/metadata.py)

Extracts dataset/column structure for upload responses. **191 lines.**

Direct imports: `numpy`, `pandas`.

Entry points/declarations: `extract_metadata` function L49–101 — Extract structural metadata from a pandas DataFrame.; `_extract_column_metadata` function L108–162 — Extract metadata for a single column.; `_safe_float` function L169–191 — Convert a numpy numeric value to a Python float safely..

### [app/ingestion/mysql_loader.py](../app/ingestion/mysql_loader.py)

Validates, profiles, deduplicates, type-maps, loads, and registers MySQL datasets. **1198 lines.**

Direct imports: `datetime`, `os`, `pandas`, `pathlib`, `re`, `sqlalchemy`, `typing`.

Entry points/declarations: `sanitize_table_name` function L119–169 — Converts a dataset name or filename into a safe, valid MySQL identifier.; `validate_table_name` function L172–187 — Validates and sanitizes table name.; `validate_and_sanitize_column_names` function L190–249 — Validates column headers:; `resolve_target_table_name` function L256–411 — Deterministically resolves the target MySQL table name for an uploaded dataset.; `DuplicatePrimaryKeyError` class L418–456 — Raised when an uploaded dataset contains duplicate primary-key values; `get_table_primary_keys` function L459–473 — Retrieves the actual primary key columns defined in MySQL for a target table.; `_normalize_pk_val` function L476–482 — Safely normalizes primary key cell values for deterministic comparison.; `identify_duplicate_records` function L485–642 — Identifies duplicate primary-key values between an uploaded DataFrame and an existing table.; `resolve_safe_file_path` function L649–709 — Resolves a dataset file path while strictly preventing directory traversal.; `map_pandas_dtype` function L717–827 — Deterministically maps a single pandas Series and optional ColumnAnalysis; `map_pandas_to_sqlalchemy_dtypes` function L830–855 — Deterministically maps Pandas DataFrame columns to SQLAlchemy types for MySQL.; `load_dataframe_to_mysql` function L858–878 — Loads a pandas DataFrame directly into MySQL using pandas.to_sql and the provided engine/connection.; `load_dataset_to_mysql` function L885–1198 — Validates, profiles, and loads a clinical dataset into MySQL..

### [app/ingestion/privacy_detector.py](../app/ingestion/privacy_detector.py)

Flags potential direct/sensitive identifiers in uploaded columns. **155 lines.**

Direct imports: `re`, `typing`.

Entry points/declarations: `detect_sensitive_column` function L102–155 — Evaluates whether a given column is a sensitive direct identifier or quasi-identifier..

### [app/ingestion/quality_checker.py](../app/ingestion/quality_checker.py)

Computes initial missing/blank/duplicate/constant quality metrics. **328 lines.**

Direct imports: `pandas`, `typing`.

Entry points/declarations: `check_quality` function L59–143 — Perform initial data quality analysis on a DataFrame.; `_check_duplicates` function L150–169 — Count fully duplicate rows (every column value is identical).; `_check_missing_values` function L172–193 — Compute missing value statistics across all columns.; `_find_empty_columns` function L196–206 — Find columns where every single value is null/NaN.; `_find_constant_columns` function L209–229 — Find columns where all non-null values are identical.; `_generate_quality_flags` function L236–328 — Generate human-readable quality warning flags..

### [app/ingestion/relationship_detector.py](../app/ingestion/relationship_detector.py)

Scores possible primary/foreign-key relationships across datasets. **238 lines.**

Direct imports: `pandas`, `typing`.

Entry points/declarations: `find_primary_key_candidates` function L33–96 — Evaluates columns in a DataFrame to identify potential primary key candidates.; `evaluate_relationship` function L117–203 — Evaluates referential integrity between parent primary key and child foreign key.; `detect_relationships_across_datasets` function L206–238 — Evaluates referential relationships across a collection of datasets..

### [app/ingestion/relationship_regenerator.py](../app/ingestion/relationship_regenerator.py)

Proposes/validates alternate relationship candidates with model assistance. **1065 lines.**

Direct imports: `json`, `pydantic`, `re`, `typing`.

Entry points/declarations: `ProposedRelationship` class L55–103 — Structured relationship proposal produced by the LLM.; `extract_schema_catalog` function L110–156 — Normalizes the supplied schema into:; `format_catalog_for_prompt` function L159–175 — Formats the schema catalog for the LLM prompt.; `parse_llm_json_response` function L182–291 — Safely extracts a JSON object from LLM output.; `propose_alternative_relationship` function L298–939 — Ask LLM to propose an alternative relationship.; `validate_proposed_relationship` function L946–1065 — Validates the LLM proposal against the actual DataFrames..

### [app/ingestion/relationship_review.py](../app/ingestion/relationship_review.py)

Stores and applies human relationship review decisions. **777 lines.**

Direct imports: `typing`.

Entry points/declarations: `CandidateNotFoundError` class L61–67 — Raised when an analyst attempts to review a relationship; `_make_key` function L88–104 — Creates a normalized, case-insensitive key for relationship lookups.; `set_relationship_candidates` function L111–145 — Stores detected relationship candidates from dataset analysis.; `get_relationship_candidates` function L148–153 — Returns all currently registered relationship candidates.; `find_candidate` function L156–175 — Finds a candidate relationship by parent and child coordinates.; `approve_relationship` function L182–289 — Approves an existing relationship candidate.; `reject_relationship` function L296–401 — Rejects an existing relationship candidate.; `regenerate_relationship` function L407–523 — Generate an alternative relationship proposal using schema information.; `edit_relationship` function L528–676 — Edits and approves a detected relationship candidate.; `get_approved_relationships` function L683–721 — Returns all approved relationships.; `get_rejected_relationships` function L724–760 — Returns all rejected relationships.; `clear_review_stores` function L766–777 — Resets all in-memory relationship stores..

### [app/ingestion/schema_inference.py](../app/ingestion/schema_inference.py)

Infers semantic column types, dates, statistics, and missingness. **355 lines.**

Direct imports: `math`, `numpy`, `pandas`, `re`, `typing`.

Entry points/declarations: `classify_missingness` function L37–55 — Classifies null percentage into standardized reporting brackets:; `detect_date_column` function L64–141 — Evaluates whether a column contains date or datetime values.; `profile_column` function L148–288 — Profiles a single dataset column:; `analyze_observations_special` function L295–355 — Performs specialized deep analysis of the clinical observations dataset..

### [app/main.py](../app/main.py)

FastAPI app creation, startup lifespan, middleware, and router registration. **188 lines.**

Direct imports: `contextlib`, `fastapi`.

Entry points/declarations: `lifespan` function L57–101 — Manages application startup and shutdown events.; `root` function L162–188 — Root endpoint — confirms the API is running and provides navigation links..

### [app/reporting/__init__.py](../app/reporting/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **9 lines.**

### [app/reporting/pdf_generator.py](../app/reporting/pdf_generator.py)

Builds ReportLab clinical PDF pages, tables, rules, charts, and provenance. **668 lines.**

Direct imports: `datetime`, `html`, `io`, `matplotlib`, `re`, `reportlab`, `sqlalchemy`, `typing`.

Entry points/declarations: `NumberedCanvas` class L41–83 — Two-pass canvas that computes total pages dynamically and stamps; `clean_markdown_for_reportlab` function L89–110 — Converts markdown markers into valid ReportLab XML tags (<b>, <i>).; `parse_insight_to_paragraphs` function L113–164 — Parses natural language insight strings into structured ReportLab Flowables; `_is_clinical_context` function L313–369 — Determine whether the current report request pertains to the CDISC clinical trial dataset.; `_get_active_tables` function L372–393 — Resolves the active tables list, overriding stale EHR defaults when in clinical trial context.; `get_table_metadata` function L396–437 — Returns verified table schema details, primary keys, relationships, and row counts.; `_get_clinical_joins_text` function L440–475 — Builds a human-readable summary of CDISC relational joins used.; `_extract_metric_info` function L478–541 — Extracts category key, metric key, unit, and min/max extremes from tabular results.; `generate_chart_image` function L547–660 — Generates a clean, publication-grade clinical bar chart using Matplotlib.; `build_clinical_pdf_report` function L664–668 — Render only facts present in the report input and its provenance metadata..

### [app/reporting/safe_pdf.py](../app/reporting/safe_pdf.py)

PDF-safe text, layout, and rendering helpers. **469 lines.**

Direct imports: `datetime`, `html`, `io`, `matplotlib`, `re`, `reportlab`.

Entry points/declarations: `_esc` function L21–22; `_label` function L25–27; `_value` function L30–41; `_styles` function L44–66; `_box` function L69–79; `_table` function L82–96; `_arm_key` function L99–102; `_summary_table` function L105–121; `_chart` function L124–156; `_count_chart` function L159–205 — Show two supplied participant counts without estimating missing values.; `_top_adverse_events_chart` function L208–241 — Plot the separately queried ADAE participant counts, when available.; `_analysis_rules` function L244–302 — Summarize the supplied plan without restating SQL as clinical policy.; `_paragraphs` function L305–313; `build_report` function L316–463; `_canvas` function L466–469.

### [app/reporting/validation.py](../app/reporting/validation.py)

Checks completed PDF bytes before saving. **15 lines.**

Direct imports: `io`, `pypdf`.

Entry points/declarations: `validate_pdf` function L6–15.

### [app/schemas/__init__.py](../app/schemas/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **15 lines.**

### [app/schemas/analytics.py](../app/schemas/analytics.py)

Pydantic transport models for analytics API data. **199 lines.**

Direct imports: `pydantic`, `typing`.

Entry points/declarations: `AnalyticsRequest` class L12–73; `AnalyticsResponse` class L76–107 — Response returned by the clinical analytics workflow.; `OverviewResponse` class L110–124 — Response for general clinical overview dashboard.; `DashboardCustomizationRequest` class L127–134 — Request payload for customizing the dashboard by table selection.; `DashboardCustomizationResponse` class L137–161 — Response containing real MySQL calculations for selected tables.; `ConversationTurn` class L164–167 — A single turn in the session conversation history.; `FollowUpRequest` class L170–182 — Request payload for answering a lightweight clinical follow-up question.; `FollowUpResponse` class L185–197 — Response returned by the lightweight follow-up analysis engine..

### [app/schemas/database.py](../app/schemas/database.py)

Pydantic transport models for database API data. **232 lines.**

Direct imports: `datetime`, `pydantic`, `typing`.

Entry points/declarations: `DatasetLoadRequest` class L24–47 — Request payload to load a validated clinical dataset into MySQL.; `DatasetLoadResponse` class L50–61 — Response returned when a clinical dataset is successfully loaded into MySQL.; `DatasetVersionOut` class L68–81 — Metadata schema representing a single loaded dataset version.; `ListVersionsResponse` class L84–88 — Response containing a list of dataset versions.; `DatasetColumnOut` class L95–109 — Metadata schema for a column stored in dataset_columns.; `ListColumnsResponse` class L112–117 — Response containing column metadata for a dataset version.; `ApprovedRelationshipOut` class L124–137 — Schema for an approved or rejected relationship persisted in MySQL.; `AuditLogOut` class L144–158 — Schema for a platform audit log record.; `ListAuditLogsResponse` class L161–167 — Response containing a list of audit logs.; `TableColumnInfo` class L174–178 — Column definition for dynamic table selection.; `TableMetadataOut` class L181–189 — Metadata for an active clinical table available for dashboard selection.; `ListTablesResponse` class L192–196 — Response containing list of available clinical tables.; `RegistryEntryOut` class L203–217 — Schema representing an entry in the authoritative clinical dataset registry.; `UpdateRegistryStatusRequest` class L220–225 — Request to update classification or approval status of a dataset.; `ListRegistryResponse` class L228–232 — Response containing all dataset registry entries..

### [app/schemas/ingestion.py](../app/schemas/ingestion.py)

Pydantic transport models for ingestion API data. **191 lines.**

Direct imports: `pydantic`, `typing`.

Entry points/declarations: `ColumnMetadata` class L42–62 — Metadata for a single column in the uploaded dataset.; `DatasetMetadata` class L69–84 — Structural metadata describing the uploaded dataset as a whole.; `QualityReport` class L91–110 — Data quality summary for the uploaded dataset.; `UploadResponse` class L117–142 — Top-level response returned by POST /ingestion/upload.; `ErrorResponse` class L149–160 — Structured error response for failed uploads.; `ColumnPreview` class L167–172; `PreviewResponse` class L175–191.

### [app/schemas/relationships.py](../app/schemas/relationships.py)

Pydantic transport models for relationships API data. **218 lines.**

Direct imports: `enum`, `pydantic`, `typing`.

Entry points/declarations: `RelationshipAction` class L27–31 — Allowed actions an analyst can take on a relationship candidate.; `RelationshipReviewRequest` class L34–78 — Analyst decision for a detected relationship candidate.; `ApprovedRelationship` class L81–101 — Relationship that has been explicitly approved by a human analyst.; `RejectedRelationship` class L104–116 — Relationship candidate that has been rejected by a human analyst.; `RelationshipReviewResponse` class L119–128 — Response returned after processing an analyst relationship decision.; `RelationshipCandidatesResponse` class L131–141 — Response returned by GET /relationships/candidates containing all detected candidates.; `ApprovedRelationshipsResponse` class L144–153 — Response returned by GET /relationships/approved.; `RejectedRelationshipsResponse` class L156–165 — Response returned by GET /relationships/rejected.; `RelationshipRegenerateRequest` class L166–204 — Request to generate an alternative relationship proposal; `RelationshipRegenerateResponse` class L207–218 — Response containing the AI-proposed alternative relationship.

### [app/schemas/reports.py](../app/schemas/reports.py)

Pydantic transport models for reports API data. **119 lines.**

Direct imports: `pydantic`, `typing`.

Entry points/declarations: `PDFReportRequest` class L11–119 — Payload for generating an evidence-scoped A4 PDF report..

### [app/schemas/validation.py](../app/schemas/validation.py)

Pydantic transport models for validation API data. **218 lines.**

Direct imports: `pydantic`, `typing`.

Entry points/declarations: `DateColumnMetadata` class L28–35 — Details for a column identified as containing date or datetime values.; `SensitiveColumnMetadata` class L42–47 — Identifies sensitive or direct-identifier fields requiring HIPAA/privacy safeguards.; `ColumnAnalysis` class L54–81 — Complete profiling and semantic analysis for a single column.; `PrimaryKeyCandidate` class L88–96 — Evidence evaluating a column as a primary key candidate.; `RelationshipAnalysis` class L103–119 — Analysis of relational foreign key candidate between parent and child tables.; `ObservationsAnalysis` class L126–138 — Specialized analysis for heterogeneous clinical observations table.; `DatasetAnalysis` class L145–163 — Comprehensive schema and data quality analysis for an individual dataset file.; `OverallQuality` class L170–181 — Global quality and relational integrity summary across all analyzed datasets.; `AnalyzeRequest` class L188–209 — Request payload for POST /ingestion/analyze.; `AnalyzeResponse` class L212–218 — Response payload returned by POST /ingestion/analyze..

### [app/visualization/__init__.py](../app/visualization/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **0 lines.**

### [app/visualization/chart_generator.py](../app/visualization/chart_generator.py)

Builds chart specifications from validated SQL rows. **183 lines.**

Direct imports: `decimal`, `pandas`, `plotly`.

Entry points/declarations: `_is_numeric` function L6–15; `create_chart_spec` function L18–136 — Create a chart specification from validated SQL results.; `create_bar_chart` function L139–183 — Create a Plotly bar chart from validated SQL results..

### [app/visualization/validation.py](../app/visualization/validation.py)

Verifies chart labels and numbers match validated rows. **30 lines.**

Direct imports: `math`, `numbers`.

Entry points/declarations: `validate_chart` function L6–30.

### [app/workflow/__init__.py](../app/workflow/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **0 lines.**

### [app/workflow/graph.py](../app/workflow/graph.py)

LangGraph nodes, conditional routers, plan approval, SQL/result/insight/chart pipeline. **2460 lines.**

Direct imports: `dataclasses`, `langgraph`, `re`, `traceback`, `typing`.

Entry points/declarations: `_cache_context` function L18–23; `_is_clinical_context` function L48–65 — Detect whether the execution context targets CDISC clinical-trial schema; `format_clinical_analysis_plan` function L68–137 — Format a ClinicalQuestionPlan into the standard 5-section markdown analysis plan; `validate_table_selection_node` function L145–204 — Strict boundary check: ensures user table selection covers all datasets; `table_selection_router` function L207–214 — Conditional edge router after table selection validation at the execution boundary.; `load_schema` function L221–231; `_deterministic_analysis_plan` function L238–533 — Generate a deterministic analysis plan for a supported; `analyze_question` function L542–839; `human_approval_node` function L847–976 — Human reviews the analysis plan.; `_is_explicitly_removed` function L983–1034 — Check if the user explicitly requested the removal of a specific requirement.; `_remove_inpatient_filter` function L1037–1064 — Remove any inpatient filter from the plan when it conflicts with the analysis.; `_remove_conditions_table_and_join` function L1067–1115 — Remove the conditions table and encounters-conditions join when; `_remove_filter_from_plan` function L1118–1140 — Remove a filter block or line from the plan if explicitly requested.; `_inject_filter_into_plan` function L1143–1157 — Insert a filter block cleanly under the 'Filtering' section.; `_sanitize_clinical_plan` function L1160–1237 — Apply clinical safety validation to an analysis plan:; `_enforce_logical_consistency` function L1240–1319 — Perform a comprehensive logical consistency check on the regenerated analysis plan:; `_preserve_plan_requirements` function L1322–1501 — Ensure that regenerating an analysis plan preserves all valid requirements; `regenerate_analysis_plan` function L1504–1684 — Regenerate the analysis plan using:; `regeneration_router` function L1691–1705 — Route the workflow after analysis plan regeneration.; `approval_router` function L1712–1725; `_resolve_authorized_clinical_schema` function L1731–1808 — Derives the authorized database schema scope for SQL generation and validation.; `generate_sql_node` function L1811–1868; `validate_sql_node` function L1875–1936; `execute_sql_node` function L1943–1988; `validate_results_node` function L1995–2014; `_cache_result` function L2017–2022; `correct_results_node` function L2025–2032; `generate_insight_node` function L2039–2069; `validate_insight_node` function L2076–2133 — Deterministically validate the generated insight; `regenerate_insight_node` function L2140–2192 — Regenerate the insight after deterministic validation fails.; `generate_sql_router` function L2199–2202; `validate_sql_router` function L2205–2208; `execute_sql_router` function L2211–2214; `validate_results_router` function L2217–2224; `insight_validation_router` function L2227–2241; `generate_chart_node` function L2248–2278 — Generate a chart specification from ONLY validated SQL results.; `build_graph` function L2285–2453.

### [app/workflow/graph_test.py](../app/workflow/graph_test.py)

Maintained project file for graph test. **44 lines.**

Direct imports: `pprint`, `sys`.

### [app/workflow/recovery.py](../app/workflow/recovery.py)

Saved-run start/resume, version checks, and stage recovery. **93 lines.**

Direct imports: `fastapi`, `sqlalchemy`, `threading`.

Entry points/declarations: `signature` function L19–25; `execute` function L28–93.

### [app/workflow/reliability.py](../app/workflow/reliability.py)

Error classification, retry policy, and user-safe failure messages. **33 lines.**

Direct imports: `datetime`, `os`, `sqlalchemy`.

Entry points/declarations: `retry_limit` function L7–8; `transient` function L11–16; `failure` function L19–33.

### [app/workflow/runtime.py](../app/workflow/runtime.py)

Stage wrapper, status recording, and bounded retry handling. **49 lines.**

Entry points/declarations: `stage_wrapper` function L6–49.

### [app/workflow/state.py](../app/workflow/state.py)

Typed state passed among LangGraph nodes. **63 lines.**

Direct imports: `typing`.

Entry points/declarations: `ClinicalAnalyticsState` class L4–63.

### [app/workflow/store.py](../app/workflow/store.py)

SQL tables and CRUD for runs, snapshots, workflow events, and notices. **116 lines.**

Direct imports: `datetime`, `json`, `sqlalchemy`, `uuid`.

Entry points/declarations: `now` function L9–10; `uid` function L13–14; `Store` class L39–116.

## COMPLETE_PROJECT_DOCUMENTATION.md

### [COMPLETE_PROJECT_DOCUMENTATION.md](../COMPLETE_PROJECT_DOCUMENTATION.md)

Archived architecture manual; contains removed RAG/Governed Workspace details and is not current implementation authority. **1957 lines.**

## docs

### [docs/architecture-flow.mmd](../docs/architecture-flow.mmd)

Project documentation: architecture flow. Historical files may describe retired paths. **78 lines.**

### [docs/architecture.mmd](../docs/architecture.mmd)

Project documentation: architecture. Historical files may describe retired paths. **188 lines.**

### [docs/AUDIT.md](../docs/AUDIT.md)

Project documentation: Audit and implementation direction. Historical files may describe retired paths. **24 lines.**

### [docs/CHANGES.md](../docs/CHANGES.md)

Project documentation: File-by-file change summary. Historical files may describe retired paths. **33 lines.**

### [docs/CURRENT_PROJECT_WORKFLOW_GUIDE.md](../docs/CURRENT_PROJECT_WORKFLOW_GUIDE.md)

Project documentation: Current project workflow and code guide. Historical files may describe retired paths. **91 lines.**

### [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)

Project documentation: Run the Clinical Analytics application. Historical files may describe retired paths. **21 lines.**

### [docs/EDA_WORKFLOW_SIMPLIFICATION.md](../docs/EDA_WORKFLOW_SIMPLIFICATION.md)

Project documentation: EDA workflow simplification. Historical files may describe retired paths. **15 lines.**

### [docs/ENHANCEMENT_CHECKLIST.md](../docs/ENHANCEMENT_CHECKLIST.md)

Project documentation: Reliability enhancement checklist. Historical files may describe retired paths. **38 lines.**

### [docs/GOVERNED_WORKSPACE_REMOVAL.md](../docs/GOVERNED_WORKSPACE_REMOVAL.md)

Project documentation: Governed Workspace removal — 2026-10-18. Historical files may describe retired paths. **13 lines.**

### [docs/IMPLEMENTATION.md](../docs/IMPLEMENTATION.md)

Project documentation: Current implementation. Historical files may describe retired paths. **7 lines.**

### [docs/RELIABILITY_REPORT.md](../docs/RELIABILITY_REPORT.md)

Project documentation: Clinical analytics reliability implementation report. Historical files may describe retired paths. **42 lines.**

### [docs/REPOSITORY_INVENTORY.md](../docs/REPOSITORY_INVENTORY.md)

Project documentation: Repository source inventory. Historical files may describe retired paths. **214 lines.**

## evals

### [evals/CLINICAL_UAT_REPORT.json](../evals/CLINICAL_UAT_REPORT.json)

Offline/evaluation script or result for CLINICAL UAT REPORT; not a live request stage. **1698 lines.**

### [evals/datasets/analysis_plan_test_cases.json](../evals/datasets/analysis_plan_test_cases.json)

Maintained evaluation-case data for analysis plan test cases; fixtures, not production records. **97 lines.**

### [evals/datasets/chart_test_cases.json](../evals/datasets/chart_test_cases.json)

Maintained evaluation-case data for chart test cases; fixtures, not production records. **82 lines.**

### [evals/datasets/clinical_golden_benchmark.json](../evals/datasets/clinical_golden_benchmark.json)

Maintained evaluation-case data for clinical golden benchmark; fixtures, not production records. **803 lines.**

### [evals/datasets/clinical_natural_language_uat.json](../evals/datasets/clinical_natural_language_uat.json)

Maintained evaluation-case data for clinical natural language uat; fixtures, not production records. **1303 lines.**

### [evals/datasets/e2e_test_cases.json](../evals/datasets/e2e_test_cases.json)

Maintained evaluation-case data for e2e test cases; fixtures, not production records. **144 lines.**

### [evals/datasets/insight_deepeval_test_cases.json](../evals/datasets/insight_deepeval_test_cases.json)

Maintained evaluation-case data for insight deepeval test cases; fixtures, not production records. **77 lines.**

### [evals/datasets/insight_test_cases.json](../evals/datasets/insight_test_cases.json)

Maintained evaluation-case data for insight test cases; fixtures, not production records. **105 lines.**

### [evals/datasets/legacy/analysis_plan_test_cases.json](../evals/datasets/legacy/analysis_plan_test_cases.json)

Maintained evaluation-case data for analysis plan test cases; fixtures, not production records. **141 lines.**

### [evals/datasets/legacy/chart_test_cases.json](../evals/datasets/legacy/chart_test_cases.json)

Maintained evaluation-case data for chart test cases; fixtures, not production records. **91 lines.**

### [evals/datasets/legacy/e2e_test_cases.json](../evals/datasets/legacy/e2e_test_cases.json)

Maintained evaluation-case data for e2e test cases; fixtures, not production records. **144 lines.**

### [evals/datasets/legacy/insight_deepeval_test_cases.json](../evals/datasets/legacy/insight_deepeval_test_cases.json)

Maintained evaluation-case data for insight deepeval test cases; fixtures, not production records. **86 lines.**

### [evals/datasets/legacy/insight_test_cases.json](../evals/datasets/legacy/insight_test_cases.json)

Maintained evaluation-case data for insight test cases; fixtures, not production records. **112 lines.**

### [evals/datasets/legacy/plan_regeneration_test_cases.json](../evals/datasets/legacy/plan_regeneration_test_cases.json)

Maintained evaluation-case data for plan regeneration test cases; fixtures, not production records. **156 lines.**

### [evals/datasets/legacy/sql_execution_test_cases.json](../evals/datasets/legacy/sql_execution_test_cases.json)

Maintained evaluation-case data for sql execution test cases; fixtures, not production records. **90 lines.**

### [evals/datasets/legacy/sql_plan_test_cases.json](../evals/datasets/legacy/sql_plan_test_cases.json)

Maintained evaluation-case data for sql plan test cases; fixtures, not production records. **114 lines.**

### [evals/datasets/legacy/sql_test_cases.json](../evals/datasets/legacy/sql_test_cases.json)

Maintained evaluation-case data for sql test cases; fixtures, not production records. **170 lines.**

### [evals/datasets/plan_regeneration_test_cases.json](../evals/datasets/plan_regeneration_test_cases.json)

Maintained evaluation-case data for plan regeneration test cases; fixtures, not production records. **138 lines.**

### [evals/datasets/sql_execution_test_cases.json](../evals/datasets/sql_execution_test_cases.json)

Maintained evaluation-case data for sql execution test cases; fixtures, not production records. **136 lines.**

### [evals/datasets/sql_plan_test_cases.json](../evals/datasets/sql_plan_test_cases.json)

Maintained evaluation-case data for sql plan test cases; fixtures, not production records. **122 lines.**

### [evals/datasets/sql_test_cases.json](../evals/datasets/sql_test_cases.json)

Maintained evaluation-case data for sql test cases; fixtures, not production records. **170 lines.**

### [evals/DEEPEVAL_CLINICAL_REPORT.json](../evals/DEEPEVAL_CLINICAL_REPORT.json)

Offline/evaluation script or result for DEEPEVAL CLINICAL REPORT; not a live request stage. **731 lines.**

### [evals/DEEPEVAL_CLINICAL_REPORT.md](../evals/DEEPEVAL_CLINICAL_REPORT.md)

Offline/evaluation script or result for DEEPEVAL CLINICAL REPORT; not a live request stage. **117 lines.**

### [evals/DEEPEVAL_CURRENT_2026-10-19.md](../evals/DEEPEVAL_CURRENT_2026-10-19.md)

Offline/evaluation script or result for DEEPEVAL CURRENT 2026 10 19; not a live request stage. **37 lines.**

### [evals/DEEPEVAL_OFFLINE_2026-10-19.json](../evals/DEEPEVAL_OFFLINE_2026-10-19.json)

Offline/evaluation script or result for DEEPEVAL OFFLINE 2026 10 19; not a live request stage. **264 lines.**

### [evals/INSIGHT_DEEPEVAL_REPORT.md](../evals/INSIGHT_DEEPEVAL_REPORT.md)

Offline/evaluation script or result for INSIGHT DEEPEVAL REPORT; not a live request stage. **106 lines.**

### [evals/print_uat_summary.py](../evals/print_uat_summary.py)

Offline/evaluation script or result for print uat summary; not a live request stage. **12 lines.**

Direct imports: `json`.

### [evals/run_clinical_benchmark.py](../evals/run_clinical_benchmark.py)

Offline/evaluation script or result for run clinical benchmark; not a live request stage. **392 lines.**

Direct imports: `json`, `pathlib`, `re`, `sys`, `time`, `typing`.

Entry points/declarations: `load_golden_benchmark` function L39–41; `evaluate_analytical_case` function L44–262 — Evaluates an analytical clinical trial case through the real pipeline:; `run_benchmark` function L265–388.

### [evals/run_clinical_uat.py](../evals/run_clinical_uat.py)

Offline/evaluation script or result for run clinical uat; not a live request stage. **488 lines.**

Direct imports: `json`, `os`, `pathlib`, `sys`, `time`, `typing`.

Entry points/declarations: `load_uat_cases` function L59–61; `check_sql_semantics` function L64–91; `check_multi_row_additive_equivalence` function L94–143 — Checks if a multi-row partitioned result (e.g. grouped by treatment arm, sex, site); `evaluate_sql_uat_case` function L146–311; `evaluate_ambiguous_case` function L314–371; `run_full_uat` function L374–484.

### [evals/test_analysis_plan.py](../evals/test_analysis_plan.py)

Offline/evaluation script or result for test analysis plan; not a live request stage. **138 lines.**

Direct imports: `json`, `pathlib`, `sys`.

Entry points/declarations: `load_test_cases` function L16–18; `check_requirement` function L21–40 — Deterministically check if an expected requirement is present in the plan text.; `run_analysis_plan_eval` function L43–133.

### [evals/test_chart_generation.py](../evals/test_chart_generation.py)

Offline/evaluation script or result for test chart generation; not a live request stage. **181 lines.**

Direct imports: `json`, `pathlib`, `sys`.

Entry points/declarations: `load_test_cases` function L19–21; `validate_chart_spec` function L24–103 — Deterministically validate the generated chart specification against expected requirements.; `run_chart_generation_eval` function L106–176.

### [evals/test_e2e_workflow.py](../evals/test_e2e_workflow.py)

Offline/evaluation script or result for test e2e workflow; not a live request stage. **301 lines.**

Direct imports: `json`, `langgraph`, `pathlib`, `sys`.

Entry points/declarations: `load_test_cases` function L30–32; `run_e2e_evaluation` function L35–296.

### [evals/test_insight_deepeval.py](../evals/test_insight_deepeval.py)

Offline/evaluation script or result for test insight deepeval; not a live request stage. **279 lines.**

Direct imports: `asyncio`, `deepeval`, `json`, `os`, `pathlib`, `re`, `sys`, `time`.

Entry points/declarations: `RateLimitedGeminiModel` class L32–70 — GeminiModel subclass with automatic rate-limit backoff.; `load_test_cases` function L73–75; `build_analysis_context` function L78–109 — Format verified SQL results, deterministic evidence summary,; `run_insight_deepeval` function L112–275.

### [evals/test_insight_generation.py](../evals/test_insight_generation.py)

Offline/evaluation script or result for test insight generation; not a live request stage. **195 lines.**

Direct imports: `json`, `pathlib`, `re`, `sys`.

Entry points/declarations: `load_test_cases` function L22–24; `check_fact_present` function L27–50 — Deterministically check if an expected fact is present in the insight.; `run_insight_generation_eval` function L53–190.

### [evals/test_plan_regeneration.py](../evals/test_plan_regeneration.py)

Offline/evaluation script or result for test plan regeneration; not a live request stage. **263 lines.**

Direct imports: `json`, `langgraph`, `pathlib`, `sys`.

Entry points/declarations: `load_test_cases` function L57–59; `run_router_tests` function L62–108; `run_plan_regeneration_tests` function L111–227; `run_full_evaluation` function L230–258.

### [evals/test_sql_execution.py](../evals/test_sql_execution.py)

Offline/evaluation script or result for test sql execution; not a live request stage. **151 lines.**

Direct imports: `decimal`, `json`, `pathlib`, `sys`, `typing`.

Entry points/declarations: `load_test_cases` function L17–19; `verify_numeric_fields` function L25–48 — Verify that expected numeric aggregations contain valid numeric values.; `run_sql_execution_eval` function L51–147.

### [evals/test_sql_plan_validator.py](../evals/test_sql_plan_validator.py)

Offline/evaluation script or result for test sql plan validator; not a live request stage. **86 lines.**

Direct imports: `json`, `pathlib`, `sys`.

Entry points/declarations: `load_test_cases` function L16–18; `run_sql_plan_validator_eval` function L21–82.

### [evals/test_sql_validator.py](../evals/test_sql_validator.py)

Offline/evaluation script or result for test sql validator; not a live request stage. **68 lines.**

Direct imports: `json`, `pathlib`, `sys`.

Entry points/declarations: `load_test_cases` function L15–17; `run_sql_validator_eval` function L20–64.

## frontend

### [frontend/index.html](../frontend/index.html)

Vite HTML entry containing the React mount element. **16 lines.**

### [frontend/package-lock.json](../frontend/package-lock.json)

Locked frontend dependency graph used by `npm ci`; installed package internals are excluded. **7373 lines.**

### [frontend/package.json](../frontend/package.json)

Frontend runtime/dev package manifest and dev/build/test commands. **40 lines.**

### [frontend/postcss.config.js](../frontend/postcss.config.js)

PostCSS/Tailwind/autoprefixer build configuration. **6 lines.**

### [frontend/src/__tests__/App.test.tsx](../frontend/src/__tests__/App.test.tsx)

Vitest/Testing Library regression checks for App.test. **39 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

### [frontend/src/__tests__/ClinicalApprovalCard.test.tsx](../frontend/src/__tests__/ClinicalApprovalCard.test.tsx)

Vitest/Testing Library regression checks for ClinicalApprovalCard.test. **151 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `adverseEventPlan` L7; `laboratoryPlan` L22; `vitalPlan` L34; `savedAgePlan` L44.

### [frontend/src/__tests__/ClinicalTopbar.test.tsx](../frontend/src/__tests__/ClinicalTopbar.test.tsx)

Vitest/Testing Library regression checks for ClinicalTopbar.test. **16 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `onOpenTechnical` L8.

### [frontend/src/__tests__/DatasetUploadModal.test.tsx](../frontend/src/__tests__/DatasetUploadModal.test.tsx)

Vitest/Testing Library regression checks for DatasetUploadModal.test. **214 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

### [frontend/src/__tests__/ErrorHandlingAndRendering.test.tsx](../frontend/src/__tests__/ErrorHandlingAndRendering.test.tsx)

Vitest/Testing Library regression checks for ErrorHandlingAndRendering.test. **105 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `backendHttp400Detail` L13.

### [frontend/src/__tests__/ReportHistory.test.tsx](../frontend/src/__tests__/ReportHistory.test.tsx)

Vitest/Testing Library regression checks for ReportHistory.test. **26 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `fetchMock` L13; `onGenerate` L14.

### [frontend/src/__tests__/ReportModal.test.tsx](../frontend/src/__tests__/ReportModal.test.tsx)

Vitest/Testing Library regression checks for ReportModal.test. **55 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `fetchMock` L15; `fetchMock` L33; `click` L42.

### [frontend/src/__tests__/TableSelector.test.tsx](../frontend/src/__tests__/TableSelector.test.tsx)

Vitest/Testing Library regression checks for TableSelector.test. **328 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `MOCK_CLINICAL_TABLES` L16; `expandTables` L32; `handleApply` L46; `TestSynchronizedDashboard` L237.

### [frontend/src/__tests__/VerifiedResultsTable.test.tsx](../frontend/src/__tests__/VerifiedResultsTable.test.tsx)

Vitest/Testing Library regression checks for VerifiedResultsTable.test. **18 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

### [frontend/src/__tests__/WorkflowNotice.test.tsx](../frontend/src/__tests__/WorkflowNotice.test.tsx)

Vitest/Testing Library regression checks for WorkflowNotice.test. **73 lines.**

Direct imports: `@testing-library/react`, `react`, `vitest`.

Entry points/declarations: `act` L8; `act` L19; `act` L27.

### [frontend/src/api/analytics.ts](../frontend/src/api/analytics.ts)

Typed analytics and follow-up HTTP requests. **33 lines.**

Entry points/declarations: `analyticsApi` L11; `res` L13; `res` L18; `res` L23; `res` L28.

### [frontend/src/api/client.ts](../frontend/src/api/client.ts)

Shared Axios API client/base URL. **23 lines.**

Direct imports: `axios`.

Entry points/declarations: `API_BASE_URL` L3; `apiClient` L6.

### [frontend/src/api/database.ts](../frontend/src/api/database.ts)

Typed database/metadata HTTP requests. **80 lines.**

Entry points/declarations: `RelationshipItem` L4; `AuditLogItem` L15; `databaseApi` L29; `res` L31; `res` L38; `res` L43; `logs` L44.

### [frontend/src/api/datasets.ts](../frontend/src/api/datasets.ts)

Typed upload, preview, and dataset HTTP requests. **151 lines.**

Entry points/declarations: `DatasetVersionItem` L3; `ListVersionsResponse` L15; `UploadDatasetResponse` L21; `InferredColumnPreview` L59; `PreviewDatasetResponse` L67; `datasetsApi` L86.

### [frontend/src/App.css](../frontend/src/App.css)

Styles for App; affects appearance, not backend calculations. **184 lines.**

### [frontend/src/App.tsx](../frontend/src/App.tsx)

Switches between lazy-loaded Clinical and Technical workspaces. **35 lines.**

Direct imports: `react`.

Entry points/declarations: `ClinicalDashboard` L4; `TechnicalDashboard` L5; `WorkspaceView` L7; `App` L9.

### [frontend/src/assets/hero.png](../frontend/src/assets/hero.png)

Static image asset (hero); no executable logic. **0 lines.**

### [frontend/src/assets/react.svg](../frontend/src/assets/react.svg)

Static image asset (react); no executable logic. **0 lines.**

### [frontend/src/assets/vite.svg](../frontend/src/assets/vite.svg)

Static image asset (vite); no executable logic. **0 lines.**

### [frontend/src/components/ChartCustomizer.tsx](../frontend/src/components/ChartCustomizer.tsx)

React UI component/helper for ChartCustomizer; receives props and renders a workspace section. **428 lines.**

Direct imports: `lucide-react`, `plotly.js-dist-min`, `react`, `react-plotly.js/factory`.

Entry points/declarations: `Plot` L7; `ChartCustomizerProps` L9; `ChartType` L15; `AggregationType` L16; `AxisScale` L17; `SortOrder` L18; `ChartCustomizer` L20; `availableColumns` L25; `numericColumns` L31; `val` L34; `initialX` L40; `initialY` L41; `initialTitle` L42.

### [frontend/src/components/Clinical/ActiveDatasetCard.tsx](../frontend/src/components/Clinical/ActiveDatasetCard.tsx)

React UI component/helper for ActiveDatasetCard; receives props and renders a workspace section. **54 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ActiveDatasetCardProps` L4; `ActiveDatasetCard` L9.

### [frontend/src/components/Clinical/AskQuestionSection.tsx](../frontend/src/components/Clinical/AskQuestionSection.tsx)

React UI component/helper for AskQuestionSection; receives props and renders a workspace section. **110 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `AskQuestionSectionProps` L4; `AskQuestionSection` L12; `handleSubmit` L28.

### [frontend/src/components/Clinical/ClinicalApprovalCard.tsx](../frontend/src/components/Clinical/ClinicalApprovalCard.tsx)

React UI component/helper for ClinicalApprovalCard; receives props and renders a workspace section. **223 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ClinicalApprovalCardProps` L5; `ClinicalApprovalCard` L19; `handleRejectSubmit` L35; `isRevised` L42; `summary` L43.

### [frontend/src/components/Clinical/ClinicalInsightsCard.tsx](../frontend/src/components/Clinical/ClinicalInsightsCard.tsx)

React UI component/helper for ClinicalInsightsCard; receives props and renders a workspace section. **91 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ClinicalInsightsCardProps` L4; `ClinicalInsightsCard` L12; `displayMetric` L19; `displayCategory` L20; `rawText` L23; `extractedBullets` L26; `findings` L31; `isOverview` L34.

### [frontend/src/components/Clinical/ClinicalMetricsRow.tsx](../frontend/src/components/Clinical/ClinicalMetricsRow.tsx)

React UI component/helper for ClinicalMetricsRow; receives props and renders a workspace section. **83 lines.**

Direct imports: `react`.

Entry points/declarations: `ClinicalMetricsRowProps` L3; `ClinicalMetricsRow` L14; `selectedTablesLabel` L24; `metrics` L28.

### [frontend/src/components/Clinical/clinicalPlanSummary.ts](../frontend/src/components/Clinical/clinicalPlanSummary.ts)

React UI component/helper for clinicalPlanSummary; receives props and renders a workspace section. **165 lines.**

Entry points/declarations: `ClinicalPlanSummary` L1; `dimensionLabels` L9; `metricLabels` L17; `unique` L41; `has` L42; `identifyMetric` L44; `summarizeClinicalPlan` L61.

### [frontend/src/components/Clinical/ClinicalSidebar.tsx](../frontend/src/components/Clinical/ClinicalSidebar.tsx)

React UI component/helper for ClinicalSidebar; receives props and renders a workspace section. **99 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ClinicalSidebarProps` L16; `ClinicalSidebar` L26; `menuItems` L35; `Icon` L62.

### [frontend/src/components/Clinical/ClinicalTopbar.tsx](../frontend/src/components/Clinical/ClinicalTopbar.tsx)

React UI component/helper for ClinicalTopbar; receives props and renders a workspace section. **49 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ClinicalTopbarProps` L4; `ClinicalTopbar` L10.

### [frontend/src/components/Clinical/DynamicCharts.tsx](../frontend/src/components/Clinical/DynamicCharts.tsx)

React UI component/helper for DynamicCharts; receives props and renders a workspace section. **1019 lines.**

Direct imports: `lucide-react`, `plotly.js-dist-min`, `react`, `react-plotly.js/factory`.

Entry points/declarations: `Plot` L7; `DynamicChartsProps` L9; `ChartType` L22; `CompanionView` L23; `colorPalette` L26; `severityColorMap` L31; `formatClinicalLabel` L38; `lower` L40; `DynamicCharts` L72.

### [frontend/src/components/Clinical/FollowUpAnswerCard.tsx](../frontend/src/components/Clinical/FollowUpAnswerCard.tsx)

React UI component/helper for FollowUpAnswerCard; receives props and renders a workspace section. **175 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `FollowUpHistoryItem` L15; `FollowUpAnswerCardProps` L25; `FollowUpAnswerCard` L34; `isTechnical` L46.

### [frontend/src/components/Clinical/FollowUpSection.tsx](../frontend/src/components/Clinical/FollowUpSection.tsx)

React UI component/helper for FollowUpSection; receives props and renders a workspace section. **104 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `FollowUpSectionProps` L4; `defaultSuggested` L9; `FollowUpSection` L15; `handleSubmit` L21; `handleChipClick` L28.

### [frontend/src/components/Clinical/VerifiedResultsTable.tsx](../frontend/src/components/Clinical/VerifiedResultsTable.tsx)

React UI component/helper for VerifiedResultsTable; receives props and renders a workspace section. **85 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `VerifiedResultsTableProps` L4; `VerifiedResultsTable` L10; `displayRows` L15; `countBadge` L17; `firstItem` L20; `keys` L21; `diagCol` L22; `valCol` L23; `label` L24; `formatValue` L27.

### [frontend/src/components/Clinical/WorkflowNotice.tsx](../frontend/src/components/Clinical/WorkflowNotice.tsx)

React UI component/helper for WorkflowNotice; receives props and renders a workspace section. **27 lines.**

Direct imports: `react`.

Entry points/declarations: `RecoveryAction` L4; `WorkflowNotice` L5; `actions` L9; `findings` L10.

### [frontend/src/components/DatasetUploadModal.tsx](../frontend/src/components/DatasetUploadModal.tsx)

React UI component/helper for DatasetUploadModal; receives props and renders a workspace section. **746 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `DatasetUploadModalProps` L20; `DatasetUploadModal` L28.

### [frontend/src/components/ErrorBoundary.tsx](../frontend/src/components/ErrorBoundary.tsx)

React UI component/helper for ErrorBoundary; receives props and renders a workspace section. **62 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `Props` L4; `State` L9; `ErrorBoundary` L14.

### [frontend/src/components/IngestionResultModal.tsx](../frontend/src/components/IngestionResultModal.tsx)

React UI component/helper for IngestionResultModal; receives props and renders a workspace section. **333 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `IngestionState` L18; `IngestionResultModalProps` L20; `useCopyToClipboard` L27; `copy` L29; `resolveIngestionState` L38; `inserted` L43; `skipped` L44; `failed` L45; `StatRowProps` L52; `StatRow` L57; `IngestionResultModal` L64; `StateCfg` L91; `CFG` L101.

### [frontend/src/components/PDFPageCanvas.tsx](../frontend/src/components/PDFPageCanvas.tsx)

React UI component/helper for PDFPageCanvas; receives props and renders a workspace section. **144 lines.**

Direct imports: `pdfjs-dist`, `react`.

Entry points/declarations: `PDFPageCanvasProps` L4; `PDFPageCanvas` L11; `canvasRef` L17; `containerRef` L18; `renderTaskRef` L19; `renderPage` L26; `page` L28; `viewport` L41; `canvas` L44; `ctx` L47; `outputScale` L50.

### [frontend/src/components/PDFViewer.tsx](../frontend/src/components/PDFViewer.tsx)

React UI component/helper for PDFViewer; receives props and renders a workspace section. **390 lines.**

Direct imports: `lucide-react`, `pdfjs-dist`, `pdfjs-dist/build/pdf.worker?url`, `react`.

Entry points/declarations: `PDFViewerProps` L22; `PDFViewer` L28; `containerRef` L33; `scrollAreaRef` L34; `A4_WIDTH` L121; `A4_HEIGHT` L122.

### [frontend/src/components/ReportHistory.tsx](../frontend/src/components/ReportHistory.tsx)

React UI component/helper for ReportHistory; receives props and renders a workspace section. **28 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ReportHistoryProps` L4; `ReportHistory` L9.

### [frontend/src/components/ReportModal.tsx](../frontend/src/components/ReportModal.tsx)

React UI component/helper for ReportModal; receives props and renders a workspace section. **405 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `EMPTY_RESULTS` L17; `EMPTY_FOLLOW_UPS` L18; `ReportModalProps` L20; `ReportModal` L35.

### [frontend/src/components/ReportTriggerBanner.tsx](../frontend/src/components/ReportTriggerBanner.tsx)

React UI component/helper for ReportTriggerBanner; receives props and renders a workspace section. **42 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ReportTriggerBannerProps` L4; `ReportTriggerBanner` L10.

### [frontend/src/components/SidebarTableSelector.tsx](../frontend/src/components/SidebarTableSelector.tsx)

React UI component/helper for SidebarTableSelector; receives props and renders a workspace section. **288 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `APPROVED_CLINICAL_TABLES` L14; `LEGACY_EHR_TABLES` L19; `filterApprovedClinicalTables` L23; `withoutLegacy` L24; `availableNames` L28; `getAvailableClinicalTableNames` L38; `SidebarTableSelectorProps` L41; `SidebarTableSelector` L50.

### [frontend/src/components/TableSelectorPopover.tsx](../frontend/src/components/TableSelectorPopover.tsx)

React UI component/helper for TableSelectorPopover; receives props and renders a workspace section. **277 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `TableSelectorPopoverProps` L15; `TableSelectorPopover` L25; `popoverRef` L36; `handleClickOutside` L40.

### [frontend/src/components/Technical/ActiveDatabaseCard.tsx](../frontend/src/components/Technical/ActiveDatabaseCard.tsx)

React UI component/helper for ActiveDatabaseCard; receives props and renders a workspace section. **52 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ActiveDatabaseCardProps` L4; `ActiveDatabaseCard` L9.

### [frontend/src/components/Technical/PipelineVisualizer.tsx](../frontend/src/components/Technical/PipelineVisualizer.tsx)

React UI component/helper for PipelineVisualizer; receives props and renders a workspace section. **201 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `PipelineVisualizerProps` L13; `nodeDescriptions` L22; `PipelineVisualizer` L39.

### [frontend/src/components/Technical/SqlInspectorCard.tsx](../frontend/src/components/Technical/SqlInspectorCard.tsx)

React UI component/helper for SqlInspectorCard; receives props and renders a workspace section. **283 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `SqlInspectorCardProps` L4; `formatSql` L9; `tokens` L19; `char` L26; `SqlInspectorCard` L155.

### [frontend/src/components/Technical/SystemHealthCard.tsx](../frontend/src/components/Technical/SystemHealthCard.tsx)

React UI component/helper for SystemHealthCard; receives props and renders a workspace section. **55 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `SystemHealthCard` L4; `components` L5.

### [frontend/src/components/Technical/TechnicalApprovalPopup.tsx](../frontend/src/components/Technical/TechnicalApprovalPopup.tsx)

React UI component/helper for TechnicalApprovalPopup; receives props and renders a workspace section. **133 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `TechnicalApprovalPopupProps` L4; `TechnicalApprovalPopup` L13; `handleRejectSubmit` L26.

### [frontend/src/components/Technical/TechnicalMetricsRow.tsx](../frontend/src/components/Technical/TechnicalMetricsRow.tsx)

React UI component/helper for TechnicalMetricsRow; receives props and renders a workspace section. **85 lines.**

Direct imports: `react`.

Entry points/declarations: `TechnicalMetricsRowProps` L3; `TechnicalMetricsRow` L12; `metrics` L20.

### [frontend/src/components/Technical/TechnicalSidebar.tsx](../frontend/src/components/Technical/TechnicalSidebar.tsx)

React UI component/helper for TechnicalSidebar; receives props and renders a workspace section. **115 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `TechnicalSidebarProps` L18; `TechnicalSidebar` L29; `menuItems` L39; `Icon` L68.

### [frontend/src/components/Technical/TechnicalTopbar.tsx](../frontend/src/components/Technical/TechnicalTopbar.tsx)

React UI component/helper for TechnicalTopbar; receives props and renders a workspace section. **38 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `TechnicalTopbarProps` L4; `TechnicalTopbar` L9.

### [frontend/src/components/TopPlatformBar.tsx](../frontend/src/components/TopPlatformBar.tsx)

React UI component/helper for TopPlatformBar; receives props and renders a workspace section. **61 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `TopPlatformBarProps` L4; `TopPlatformBar` L9.

### [frontend/src/index.css](../frontend/src/index.css)

Styles for index; affects appearance, not backend calculations. **53 lines.**

### [frontend/src/main.tsx](../frontend/src/main.tsx)

Mounts the React application under StrictMode. **10 lines.**

Direct imports: `react`, `react-dom/client`.

### [frontend/src/pages/ClinicalDashboard.tsx](../frontend/src/pages/ClinicalDashboard.tsx)

Clinical question, approval, result, chart, report, and recovery UI state. **1277 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `ClinicalDashboardProps` L42; `ClinicalDashboard` L46.

### [frontend/src/pages/TechnicalDashboard.tsx](../frontend/src/pages/TechnicalDashboard.tsx)

Technical dataset, database, pipeline, and inspection workspace. **1546 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `TechnicalDashboardProps` L53; `TechnicalDashboard` L73.

### [frontend/src/pages/WorkspaceSelection.tsx](../frontend/src/pages/WorkspaceSelection.tsx)

Workspace choice presentation component (not the current App entry view). **137 lines.**

Direct imports: `lucide-react`, `react`.

Entry points/declarations: `WorkspaceSelectionProps` L4; `WorkspaceSelection` L8.

### [frontend/src/services/api.ts](../frontend/src/services/api.ts)

Project configuration or data contract for api. **11 lines.**

Entry points/declarations: `apiService` L5.

### [frontend/src/studio.css](../frontend/src/studio.css)

Styles for studio; affects appearance, not backend calculations. **123 lines.**

### [frontend/src/types/analytics.ts](../frontend/src/types/analytics.ts)

TypeScript request, workflow, result, and chart contracts. **176 lines.**

Entry points/declarations: `AnalyticsRequest` L1; `TableColumn` L16; `ClinicalTable` L22; `ListTablesResponse` L32; `KpiCard` L38; `DashboardCustomizationResponse` L44; `ChartSpec` L68; `StageStatus` L78; `AnalyticsResponse` L81; `EncounterClassItem` L109; `TopDiagnosisItem` L114; `MonthlyTrendItem` L120; `OverviewResponse` L125; `PipelineNodeStatus` L139; `PipelineNode` L141; `ConversationTurn` L149; `FollowUpRequest` L154; `FollowUpResponse` L166.

### [frontend/tailwind.config.js](../frontend/tailwind.config.js)

Tailwind theme/content scanning configuration. **28 lines.**

### [frontend/tsconfig.app.json](../frontend/tsconfig.app.json)

Browser-side TypeScript compiler checks. **25 lines.**

### [frontend/tsconfig.json](../frontend/tsconfig.json)

TypeScript project references. **7 lines.**

### [frontend/tsconfig.node.json](../frontend/tsconfig.node.json)

Build-tool-side TypeScript compiler checks. **23 lines.**

### [frontend/vite.config.ts](../frontend/vite.config.ts)

Vite React plugin, Vitest environment, dev server, and `/api` proxy. **23 lines.**

Direct imports: `@vitejs/plugin-react`, `vitest/config`.

## pytest.ini

### [pytest.ini](../pytest.ini)

Pytest discovery and runner configuration. **4 lines.**

## README.md

### [README.md](../README.md)

Current application scope, startup, API locations, and future enhancement note. **35 lines.**

## requirements.txt

### [requirements.txt](../requirements.txt)

Pinned or bounded Python runtime and test dependencies. **43 lines.**

## scripts

### [scripts/build_file_index.py](../scripts/build_file_index.py)

Manually invoked setup, migration, validation, or artifact script for build file index. **228 lines.**

Direct imports: `__future__`, `ast`, `pathlib`, `re`.

Entry points/declarations: `role` function L104–135; `python_symbols` function L138–160; `frontend_symbols` function L163–171; `include` function L174–184; `main` function L187–224.

### [scripts/migrate_clinical_trials.py](../scripts/migrate_clinical_trials.py)

Manually invoked setup, migration, validation, or artifact script for migrate clinical trials. **610 lines.**

Direct imports: `datetime`, `os`, `pandas`, `pymysql`, `sys`, `typing`.

Entry points/declarations: `get_mysql_connection` function L351–360; `execute_migration` function L362–606.

### [scripts/render_architecture.py](../scripts/render_architecture.py)

Manually invoked setup, migration, validation, or artifact script for render architecture. **52 lines.**

Direct imports: `html`, `pathlib`, `re`.

### [scripts/render_project_architecture.py](../scripts/render_project_architecture.py)

Manually invoked setup, migration, validation, or artifact script for render project architecture. **168 lines.**

Direct imports: `html`, `pathlib`.

Entry points/declarations: `txt` function L30–31; `rect` function L34–40; `line` function L43–49; `path` function L52–58; `section` function L61–66; `card` function L69–86.

### [scripts/run_deepeval_evaluation.py](../scripts/run_deepeval_evaluation.py)

Manually invoked setup, migration, validation, or artifact script for run deepeval evaluation. **353 lines.**

Direct imports: `datetime`, `deepeval`, `json`, `os`, `pathlib`, `sys`, `time`, `typing`.

Entry points/declarations: `run_evaluation_suite` function L61–306; `generate_markdown_report` function L309–348.

### [scripts/setup_clinical_trial_db.py](../scripts/setup_clinical_trial_db.py)

Manually invoked setup, migration, validation, or artifact script for setup clinical trial db. **589 lines.**

Direct imports: `datetime`, `os`, `pandas`, `pymysql`, `sys`, `typing`, `zipfile`.

Entry points/declarations: `ensure_extracted_csvs` function L402–416; `main` function L418–586.

### [scripts/test_custom_datasets_removal.py](../scripts/test_custom_datasets_removal.py)

Manually invoked setup, migration, validation, or artifact script for test custom datasets removal. **145 lines.**

Direct imports: `os`, `requests`, `sqlalchemy`, `sys`.

Entry points/declarations: `run_tests` function L52–141.

### [scripts/test_dataset_registry_cleanup.py](../scripts/test_dataset_registry_cleanup.py)

Manually invoked setup, migration, validation, or artifact script for test dataset registry cleanup. **240 lines.**

Direct imports: `io`, `os`, `requests`, `sqlalchemy`, `sys`.

Entry points/declarations: `print_test` function L35–36; `run_all_tests` function L38–237.

### [scripts/test_upload_and_create_table.py](../scripts/test_upload_and_create_table.py)

Manually invoked setup, migration, validation, or artifact script for test upload and create table. **347 lines.**

Direct imports: `io`, `os`, `pandas`, `requests`, `sqlalchemy`, `sys`, `tempfile`.

Entry points/declarations: `print_test` function L28–29; `cleanup_table` function L31–38; `run_all_tests` function L40–344.

### [scripts/test_upload_flow.py](../scripts/test_upload_flow.py)

Manually invoked setup, migration, validation, or artifact script for test upload flow. **38 lines.**

Direct imports: `requests`, `sqlalchemy`.

### [scripts/verify_e2e_selection_pipeline.py](../scripts/verify_e2e_selection_pipeline.py)

Manually invoked setup, migration, validation, or artifact script for verify e2e selection pipeline. **206 lines.**

Direct imports: `json`, `os`, `pymysql`, `sys`, `urllib`.

Entry points/declarations: `post_api` function L32–39; `run_verification` function L42–202.

## tests

### [tests/__init__.py](../tests/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **3 lines.**

### [tests/evaluation/__init__.py](../tests/evaluation/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **5 lines.**

### [tests/evaluation/conftest.py](../tests/evaluation/conftest.py)

Pytest regression or evaluation coverage for conftest. **106 lines.**

Direct imports: `deepeval`, `json`, `os`, `pathlib`, `pytest`, `sys`, `typing`.

Entry points/declarations: `pytest_addoption` function L37–44 — Adds optional command-line flag to run LLM-as-a-judge DeepEval tests.; `eval_dataset` function L48–52 — Loads the master clinical evaluation dataset.; `synthetic_data` function L56–64 — Provides synthetic clinical datasets and ground truth KPIs.; `correctness_metric` function L68–69; `sql_safety_metric` function L73–74; `pipeline_metric` function L78–79; `evidence_metric` function L83–84; `deepeval_gemini_judge` function L88–106 — Returns a rate-limited Gemini model for DeepEval evaluation..

### [tests/evaluation/datasets/clinical_eval_cases.json](../tests/evaluation/datasets/clinical_eval_cases.json)

Maintained evaluation-case data for clinical eval cases; fixtures, not production records. **299 lines.**

### [tests/evaluation/fixtures/clinical_test_data.py](../tests/evaluation/fixtures/clinical_test_data.py)

Pytest regression or evaluation coverage for clinical test data. **186 lines.**

Direct imports: `typing`.

### [tests/evaluation/metrics/__init__.py](../tests/evaluation/metrics/__init__.py)

Marks this directory as a Python package; inspect exports/imports below. **15 lines.**

Direct imports: `clinical_correctness`, `evidence_quality`, `pipeline_completeness`, `sql_safety`.

### [tests/evaluation/metrics/clinical_correctness.py](../tests/evaluation/metrics/clinical_correctness.py)

Pytest regression or evaluation coverage for clinical correctness. **126 lines.**

Direct imports: `math`, `typing`.

Entry points/declarations: `ClinicalCorrectnessMetric` class L12–126 — Evaluates whether actual query results or calculated clinical metrics.

### [tests/evaluation/metrics/evidence_quality.py](../tests/evaluation/metrics/evidence_quality.py)

Pytest regression or evaluation coverage for evidence quality. **125 lines.**

Direct imports: `re`, `typing`.

Entry points/declarations: `EvidenceQualityMetric` class L13–125 — Evaluates factual grounding between generated clinical text,.

### [tests/evaluation/metrics/pipeline_completeness.py](../tests/evaluation/metrics/pipeline_completeness.py)

Pytest regression or evaluation coverage for pipeline completeness. **107 lines.**

Direct imports: `typing`.

Entry points/declarations: `PipelineCompletenessMetric` class L12–107 — Evaluates whether the clinical analytics LangGraph execution trace.

### [tests/evaluation/metrics/sql_safety.py](../tests/evaluation/metrics/sql_safety.py)

Pytest regression or evaluation coverage for sql safety. **115 lines.**

Direct imports: `re`, `typing`.

Entry points/declarations: `SQLSafetyMetric` class L35–115 — Evaluates generated or executed SQL queries for syntax safety,.

### [tests/evaluation/test_clinical_analytics_e2e.py](../tests/evaluation/test_clinical_analytics_e2e.py)

Pytest regression or evaluation coverage for test clinical analytics e2e. **166 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_e2e_subject_distribution_workflow` function L14–53 — E2E Test: Subject distribution across treatment arms.; `test_e2e_adverse_event_rate_workflow` function L56–85 — E2E Test: Adverse event incidence rate by treatment arm.; `test_e2e_missing_table_blocked_workflow` function L88–111 — E2E Test: Missing table early termination.; `test_synthetic_kpi_mathematical_invariants` function L114–166 — Phase 7: Evaluates KPI formulas against trusted synthetic fixtures.

### [tests/evaluation/test_insight_generation.py](../tests/evaluation/test_insight_generation.py)

Pytest regression or evaluation coverage for test insight generation. **112 lines.**

Direct imports: `deepeval`, `pytest`.

Entry points/declarations: `test_insight_factual_grounding_deterministic` function L14–38 — Deterministic evaluation: Verifies that numbers cited in insight text; `test_insight_empty_result_handling` function L41–61 — Deterministic evaluation: Verifies that an empty query result; `test_deepeval_llm_judge_metrics` function L64–112 — DeepEval LLM-as-a-judge evaluation: AnswerRelevancy and Faithfulness..

### [tests/evaluation/test_question_understanding.py](../tests/evaluation/test_question_understanding.py)

Pytest regression or evaluation coverage for test question understanding. **64 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_question_understanding_categories` function L13–42 — Evaluates that natural-language clinical questions map to the; `test_question_plan_dimensions_and_metrics` function L45–64 — Verifies that structured analytical questions extract the correct.

### [tests/evaluation/test_regression.py](../tests/evaluation/test_regression.py)

Pytest regression or evaluation coverage for test regression. **76 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_regression_core_13_clinical_datasets_approved` function L36–42 — Regression: Exactly the 13 approved clinical tables must be present and approved.; `test_regression_custom_tables_remain_unapproved` function L45–52 — Regression: 'biomarker_results' and 'clinical_endpoints' must not be in default catalog.; `test_regression_schema_service_filters_unapproved` function L55–59 — Regression: Default schema retrieval must omit unapproved/test tables.; `test_regression_selection_allowlist` function L62–76 — Regression: Selection allowlist strictly enforces approved dataset boundaries..

### [tests/evaluation/test_security_boundaries.py](../tests/evaluation/test_security_boundaries.py)

Pytest regression or evaluation coverage for test security boundaries. **169 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_sec_1_approved_and_selected_tables` function L26–39 — TEST 1: Approved and selected tables proceed normally.; `test_sec_2_required_table_missing_from_selection` function L42–66 — TEST 2: Required table missing from selection.; `test_sec_3_custom_unapproved_table_biomarker_results` function L69–84 — TEST 3: Custom unapproved table.; `test_sec_4_custom_unapproved_table_clinical_endpoints` function L87–102 — TEST 4: Another unapproved custom table.; `test_sec_5_hidden_table_referenced_by_sql` function L105–119 — TEST 5: Hidden or unapproved table referenced by SQL.; `test_sec_6_test_demo_table_access` function L122–133 — TEST 6: Test/demo table.; `test_sec_7_approved_table_not_selected` function L136–147 — TEST 7: Approved clinical table that was NOT selected by user.; `test_sec_8_destructive_malicious_sql` function L150–169 — TEST 8: Malicious and destructive SQL queries..

### [tests/evaluation/test_sql_generation.py](../tests/evaluation/test_sql_generation.py)

Pytest regression or evaluation coverage for test sql generation. **87 lines.**

Direct imports: `pytest`.

Entry points/declarations: `clinical_schema` function L16–17; `test_sql_subject_count_by_arm` function L20–39 — Verifies single-table subject count by treatment arm.; `test_sql_ae_incidence_join` function L42–65 — Verifies relational join between ADSL and ADAE on USUBJID for adverse event rate.; `test_sql_top_adverse_events_ordering` function L68–87 — Verifies DESC ordering and LIMIT 5 for top adverse events query..

### [tests/evaluation/test_visualization.py](../tests/evaluation/test_visualization.py)

Pytest regression or evaluation coverage for test visualization. **56 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_chart_spec_treatment_arm_distribution` function L15–29 — Verifies vertical/horizontal bar chart generation for treatment arm subject distribution.; `test_chart_spec_top_adverse_events` function L32–46 — Verifies chart specification for ranked top adverse events.; `test_chart_spec_empty_results_handling` function L49–56 — Verifies clean empty-state chart behavior: raises ValueError when results are empty..

### [tests/test_authorized_scope_fix.py](../tests/test_authorized_scope_fix.py)

Pytest regression or evaluation coverage for test authorized scope fix. **166 lines.**

Direct imports: `os`, `pytest`, `sys`.

Entry points/declarations: `test_clinical_single_table_authorized` function L20–39 — Clinical single-table query -> ADAE authorized when in approved schema.; `test_clinical_table_not_in_approved_schema_rejected` function L42–55 — ADAE query is rejected when ADAE is not in the approved schema.; `test_clinical_multi_table_authorized` function L58–90 — Clinical multi-table query -> ADSL + ADAE authorized when in approved schema.; `test_unapproved_arbitrary_table_rejected` function L93–104 — Unapproved/arbitrary table (e.g. billing_records or patients) is still rejected.; `test_end_to_end_distribution_across_treatment_arms_blocked_when_unselected` function L107–134 — Negative reproduction test:; `test_end_to_end_distribution_across_treatment_arms_with_default_selected_tables` function L137–166 — Positive reproduction test:.

### [tests/test_clinical_dashboard.py](../tests/test_clinical_dashboard.py)

Pytest regression or evaluation coverage for test clinical dashboard. **307 lines.**

Direct imports: `os`, `pytest`, `sys`.

Entry points/declarations: `TestAllClinicalKPIs` class L31–167 — Verifies that all 17 clinical KPIs execute on MySQL and return live data.; `TestDashboardCustomizationCombinations` class L174–237 — Verifies that generate_custom_dashboard produces valid response payloads.; `TestSingleClinicalTables` class L244–262 — Verifies that all 13 single clinical tables produce complete dashboards.; `TestTableValidation` class L269–286 — Verifies security and validation checks on user-selected tables.; `TestOverviewEndpoint` class L293–307 — Verifies that get_analytics_overview returns live CDISC data dynamically..

### [tests/test_clinical_evaluation.py](../tests/test_clinical_evaluation.py)

Pytest regression or evaluation coverage for test clinical evaluation. **485 lines.**

Direct imports: `json`, `os`, `pathlib`, `pytest`, `sys`.

Entry points/declarations: `test_golden_benchmark_file_exists_and_structure` function L38–49 — Verify that the master clinical benchmark dataset exists and contains 25 valid cases.; `test_golden_benchmark_categories_distribution` function L52–74 — Verify that all 7 analytical clinical domains are represented in the benchmark.; `test_golden_benchmark_ground_truth_values` function L77–102 — Verify ground truth numerical metrics against clinical_trial_analytics_db schema.; `test_cdisc_sql_test_cases_suite` function L105–120 — Verify that evals/datasets/sql_test_cases.json has 21 CDISC cases and all valid queries pass validation.; `test_cdisc_sql_plan_test_cases_suite` function L123–139 — Verify that evals/datasets/sql_plan_test_cases.json has 15 CDISC plans and all pass plan validation.; `test_cdisc_sql_execution_test_cases_suite` function L142–153 — Verify that evals/datasets/sql_execution_test_cases.json queries execute against MySQL.; `test_legacy_ehr_datasets_preservation` function L156–173 — Verify that all 9 remaining legacy EHR benchmark datasets are archived and intact.; `test_clinical_datasets_coverage` function L176–188 — Verify that golden benchmark exercises SDTM and ADaM clinical trial domains.; `test_regression_age_distribution_by_treatment_arm_semantics` function L195–206 — Regression test: Age question with arm breakdown must group by ARM and compute mean per arm.; `test_regression_treatment_emergent_ae_filter_semantics` function L209–218 — Regression test: TEAE questions must explicitly filter on TRTEMFL = 'Y'.; `test_regression_evaluator_cdisc_arm_equivalence` function L221–237 — Regression test: Semantic evaluator recognizes ADaM TRT01A as valid equivalent of concept ARM.; `test_regression_evaluator_ranking_equivalence` function L240–256 — Regression test: Semantic evaluator recognizes ORDER BY ... DESC as ranking semantics for LIMIT.; `test_regression_uat_natural_language_treatment_group_mapping` function L259–268 — Regression test: 'treatment group' and 'study population by treatment' resolve to SUBJECTS_BY_TREATMENT_ARM.; `test_regression_uat_natural_language_age_profile_mapping` function L271–276 — Regression test: 'Show the age profile for each treatment group' groups age by ARM.; `test_regression_uat_natural_language_ae_more_comparison` function L279–283 — Regression test: 'Which treatment group had more adverse events' resolves to AE_RATE_BY_TREATMENT.; `test_regression_uat_sql_generator_forbids_window_functions` function L286–299 — Regression test: _check_sql_vs_clinical_plan rejects queries with OVER () or STDDEV.; `test_regression_uat_ambiguous_queries_safety` function L302–308 — Regression test: Ambiguous queries produce safe broad responses or safe rejections without invalid SQL.; `test_regression_issue1_treatment_comparison_intent_priority` function L315–338 — Issue 1 Regression:; `test_regression_issue2_teae_fallback_preserves_clinical_semantics` function L341–377 — Issue 2 Regression:; `test_regression_issue3_discontinuation_vs_completion_logic` function L380–431 — Issue 3 Regression:; `test_regression_issue4_multi_row_additive_equivalence_evaluation` function L434–485 — Issue 4 Regression:.

### [tests/test_clinical_insight_followup.py](../tests/test_clinical_insight_followup.py)

Pytest regression or evaluation coverage for test clinical insight followup. **411 lines.**

Direct imports: `os`, `pytest`, `sys`.

Entry points/declarations: `test_insight_context_detection` function L45–50 — Verify CDISC clinical trial context detection in insight generator.; `test_followup_context_detection` function L53–69 — Verify CDISC clinical trial context detection in followup service.; `test_insight_fallback_total_subjects` function L76–86; `test_insight_fallback_average_age` function L89–99; `test_insight_fallback_serious_ae_count` function L102–112; `test_insight_fallback_ae_rate_by_treatment` function L115–128; `test_insight_fallback_efficacy_response_rate` function L131–144; `test_insight_fallback_enrollment_by_site` function L147–161; `test_build_evidence_clinical_trial` function L168–179; `test_validate_insight_valid_claim` function L182–191; `test_validate_insight_unsupported_number_fails` function L194–204; `test_validate_insight_wrong_ranking_fails` function L207–217; `test_followup_highest_treatment_arm` function L224–241; `test_followup_lowest_treatment_arm` function L244–257; `test_followup_threshold_check` function L260–274; `test_followup_specific_entity` function L277–289; `test_followup_unrelated_domain_detection` function L296–306; `test_followup_prompt_uses_original_and_latest_results_and_conversation` function L309–340; `test_followup_without_verified_results_reports_insufficient_context` function L343–357; `test_followup_lightweight_sql_total_subjects` function L360–376; `test_followup_lightweight_sql_sae_count` function L379–390; `test_legacy_ehr_followup_backward_compatibility` function L397–411.

### [tests/test_clinical_langgraph.py](../tests/test_clinical_langgraph.py)

Pytest regression or evaluation coverage for test clinical langgraph. **693 lines.**

Direct imports: `os`, `pytest`, `sys`, `unittest`.

Entry points/declarations: `active_schema` function L45–46; `test_langgraph_nodes_preserved` function L53–74 — Verify that the active LangGraph workflow nodes are registered.; `test_validated_results_route_to_insights_without_generic_eda` function L77–79; `test_schema_context_detection` function L82–87 — Verify detection of CDISC clinical trial context vs legacy EHR context.; `test_canonical_questions_deterministic_plan` function L153–171 — Verify deterministic clinical question plan generation and formatting for all 9 canonical questions.; `test_age_distribution_and_mean_plan_is_specific_and_executable` function L174–193; `test_canonical_questions_pending_approval_flow` function L197–222 — Verify flow through load_schema -> analyze_question -> human_approval (pending).; `test_pending_plan_with_explicitly_empty_selection_remains_blocked` function L225–236 — An explicitly empty selection must not be inferred as authorization.; `test_canonical_questions_full_approved_execution` function L240–289 — Verify complete end-to-end execution of approved questions through the full LangGraph pipeline.; `test_execution_boundary_blocked_on_empty_selected_tables` function L296–310 — Verify execution is blocked when selected_tables is empty upon approval.; `test_execution_boundary_blocked_on_missing_required_tables` function L313–328 — Verify execution is blocked when required tables (ADAE, ADSL) are not in selected_tables.; `test_execution_boundary_blocked_on_unknown_tables` function L331–345 — Verify execution is blocked when unknown/arbitrary tables are in selected_tables.; `test_execution_boundary_blocked_on_unapproved_custom_datasets` function L348–362 — Verify execution is blocked when unapproved custom datasets (e.g. biomarker_results) are selected.; `test_plan_regeneration_on_rejection` function L369–386 — Verify that plan rejection triggers regenerate_analysis_plan and returns pending status.; `test_legacy_ehr_deterministic_plan_fallback` function L393–434 — Verify backward compatibility fallback for legacy EHR questions when requested.; `test_join_conditions_header_not_classified_as_ehr` function L441–484 — 1. Clinical plan containing '#### 2. Join Conditions' must NOT be classified as EHR,; `test_clinical_ae_severity_unstratified` function L487–498 — 2. Clinical AE severity question:; `test_clinical_ae_severity_stratified` function L501–524 — 3. Clinical treatment-arm severity question:; `test_clinical_ae_severity_equivalent_phrasings` function L535–551 — 7. Test multiple equivalent phrasings:; `test_regeneration_with_gemini_unavailable_incorporates_feedback` function L554–643 — 4 & 5. Regeneration with Gemini unavailable / 429:; `test_clinical_plan_sanitization` function L646–693 — Verify _sanitize_clinical_plan purges EHR contamination from clinical plans..

### [tests/test_clinical_pdf_report.py](../tests/test_clinical_pdf_report.py)

Pytest regression or evaluation coverage for test clinical pdf report. **541 lines.**

Direct imports: `fastapi`, `io`, `os`, `pypdf`, `pytest`, `sqlalchemy`, `sys`.

Entry points/declarations: `extract_pdf_text` function L35–43 — Extracts raw text content across all pages from compiled PDF bytes.; `test_report_total_subjects_enrollment` function L50–75 — Verify PDF report generation for total subjects enrollment inquiry.; `test_report_without_sql_does_not_invent_query_or_certification` function L78–84; `test_report_adverse_event_count` function L87–102 — Verify PDF report generation for adverse event count inquiry.; `test_report_serious_ae_count` function L105–120 — Verify PDF report generation for serious adverse event count inquiry.; `test_report_ae_rate_by_treatment` function L123–153 — Verify PDF report generation for AE rate by treatment arm inquiry.; `test_report_plan_formula_multiplication_does_not_break_pdf_markup` function L156–178 — Inline SQL-style formulas must not be interpreted as Markdown italics.; `test_report_cover_study_facts_plain_language_rules_and_second_chart` function L181–213; `test_pdf_adds_top_adae_events_as_separate_dataset_context` function L216–237; `test_pdf_does_not_infer_top_events_from_other_results` function L240–246; `test_top_adverse_events_match_dashboard_distinct_subject_definition` function L249–264; `test_safety_template_has_three_sections_pages_without_sample_study_facts` function L267–290; `test_report_lab_change_from_baseline` function L293–318 — Verify PDF report generation for laboratory change from baseline.; `test_report_vital_sign_change_from_baseline` function L321–344 — Verify PDF report generation for vital signs change from baseline.; `test_report_efficacy_response_rate` function L347–375 — Verify PDF report generation for efficacy response rate inquiry.; `test_report_site_enrollment` function L378–403 — Verify PDF report generation for site enrollment inquiry.; `test_chart_image_generation` function L410–418 — Verify in-memory matplotlib chart generation for clinical categorical data.; `test_chart_handles_negative_values` function L421–429 — Verify chart handles negative changes from baseline (e.g. blood pressure reduction).; `test_no_unsupported_causal_or_stat_claims` function L432–450 — Ensure report generation does not insert fabricated causal or statistical significance claims.; `test_is_clinical_context_detection` function L457–479 — Verify accurate detection of CDISC clinical trial context vs legacy EHR context.; `test_legacy_ehr_report_backward_compatibility` function L482–508 — Verify that legacy EHR report requests still generate authentic EHR reports.; `test_api_generate_pdf_endpoint` function L515–520 — Report generation is open, but still requires validated result rows.; `test_api_download_latest_pdf` function L523–528 — The unsafe process-global latest PDF endpoint is retired.; `test_api_download_pdf_get` function L531–536 — Downloads cannot generate a new report.; `test_api_approve_pdf_report` function L539–541 — Persistent report review acknowledgement is not an active API feature..

### [tests/test_clinical_schema_mapping.py](../tests/test_clinical_schema_mapping.py)

Pytest regression or evaluation coverage for test clinical schema mapping. **251 lines.**

Direct imports: `os`, `pytest`, `sys`.

Entry points/declarations: `TestClinicalSchemaRegistry` class L27–73 — Test registry dataset coverage, keys, and metadata completeness.; `TestClinicalRelationships` class L76–109 — Test relationship topology, cardinalities, and connectivity.; `TestKPIDefinitions` class L112–155 — Test standard clinical KPI definitions and formula integrity.; `TestClinicalQuestionPlanner` class L158–215 — Test deterministic mapping of clinical questions to execution plans.; `TestNegativeCasesAndSafety` class L218–251 — Test safe fallbacks on invalid, unknown, or corrupted queries..

### [tests/test_clinical_sql_generator.py](../tests/test_clinical_sql_generator.py)

Pytest regression or evaluation coverage for test clinical sql generator. **263 lines.**

Direct imports: `os`, `pytest`, `sqlalchemy`, `sys`.

Entry points/declarations: `test_deterministic_sql_generation_and_validation` function L52–74 — Verifies deterministic SQL is generated, validates, references only clinical tables, and runs on MySQL.; `test_total_enrolled_patients_result` function L81–87 — Verify total subjects matches known 10,000 enrolled subjects in dm.; `test_average_age_result` function L90–97 — Verify average age is reasonable (~54.63) and within clinical bounds.; `test_sex_distribution_result` function L100–107 — Verify sex distribution has both F and M categories.; `test_ae_rate_by_treatment_arm_result` function L110–121 — Verify AE rate by arm contains Drug X and Placebo with positive rates.; `test_serious_adverse_events_result` function L124–131 — Verify serious adverse events query returns count.; `test_lab_change_from_baseline_result` function L134–142 — Verify laboratory change from baseline calculates mean change.; `test_vital_sign_change_from_baseline_result` function L145–153 — Verify vital sign change from baseline calculates change for SYSBP.; `test_efficacy_response_rate_result` function L156–164 — Verify efficacy response rate calculates response rate percentage.; `test_site_enrollment_result` function L167–174 — Verify site enrollment lists 10 sites with non-zero subjects.; `test_context_detection_clinical` function L181–186 — Verify _is_clinical_context returns True for clinical schemas.; `test_context_detection_legacy_ehr` function L189–192 — Verify _is_clinical_context returns False for legacy EHR schemas.; `test_clinical_prompt_builder` function L195–209 — Verify clinical prompt includes CDISC schema context and few-shot examples.; `test_plan_consistency_checker` function L212–224 — Verify inline plan consistency check catches violations.; `test_unsupported_question_fails_safely` function L231–235 — Verify questions for non-existent domains do not produce valid clinical plans.; `test_validator_rejects_unauthorized_tables` function L238–243 — Verify validator rejects SQL targeting hallucinated or unauthorized tables.; `test_validator_rejects_forbidden_keywords` function L246–250 — Verify validator blocks destructive DDL/DML statements.; `test_legacy_ehr_fallback_preserved` function L253–263 — Verify legacy EHR deterministic plan fallback still works when an EHR plan is provided..

### [tests/test_clinical_sql_validator.py](../tests/test_clinical_sql_validator.py)

Pytest regression or evaluation coverage for test clinical sql validator. **273 lines.**

Direct imports: `os`, `pytest`, `sqlalchemy`, `sys`.

Entry points/declarations: `test_valid_clinical_queries_pass_validation` function L96–104 — Verifies that all standard CDISC queries pass validation and execute cleanly on MySQL.; `test_unauthorized_tables_rejected` function L117–121 — Verifies unknown or non-clinical tables are rejected.; `test_unqualified_nonexistent_column_rejected` function L128–133 — Verifies unqualified non-existent columns are caught and rejected.; `test_qualified_nonexistent_column_rejected` function L136–141 — Verifies qualified table.column non-existent columns are rejected.; `test_aliased_nonexistent_column_rejected` function L144–149 — Verifies table alias d.nonexistent_column is resolved and rejected.; `test_unapproved_relationship_rejected` function L156–162 — Verifies joins across columns not forming an approved relationship are rejected.; `test_adsl_adae_approved_usubjid_relationship_accepted` function L165–175 — Verifies the verified relationship adsl.USUBJID = adae.USUBJID is approved and passes.; `test_adsl_adae_unapproved_studyid_relationship_rejected` function L178–187 — Verifies unapproved relationship adsl.STUDYID = adae.STUDYID is blocked as unauthorized.; `test_disconnected_tables_rejected` function L190–194 — Verifies joining tables that cannot connect is rejected.; `test_security_and_syntax_violations_blocked` function L213–216 — Verifies DDL, DML, multiple statements, and malformed queries are blocked.; `test_clinical_plan_single_table_violation` function L223–229 — Verifies single-table plan constraint rejects queries with JOINs.; `test_clinical_plan_serious_ae_filter` function L232–242 — Verifies serious AE plan constraint rejects queries without AESER = 'Y'.; `test_sql_generator_output_passes_validator` function L263–273 — Verifies SQL generated by the SQL Generator passes the SQL Validator and executes..

### [tests/test_duplicate_upload_handling.py](../tests/test_duplicate_upload_handling.py)

Pytest regression or evaluation coverage for test duplicate upload handling. **416 lines.**

Direct imports: `fastapi`, `io`, `os`, `pandas`, `pytest`, `sqlalchemy`, `unittest`.

Entry points/declarations: `client` function L36–37; `test_primary_key_inspection_cdisc_tables` function L44–56 — Verify primary key columns are inspected accurately for single and composite PKs.; `test_identify_duplicates_all_existing` function L63–87 — Identify duplicates when all records already exist in target table.; `test_identify_duplicates_mixed` function L90–111 — Identify duplicates when some records exist and some are new.; `test_identify_duplicates_composite_pk` function L114–132 — Identify duplicates using composite primary key [USUBJID, AESEQ] on ae.; `test_identify_intra_file_duplicates` function L135–148 — Detect intra-file duplicate keys even if none exist in the database yet.; `test_quality_check_counts_blank_and_whitespace_separately_from_missing` function L151–171 — Blank text is reported separately while null counts and empty columns remain unchanged.; `test_quality_check_preserves_duplicate_detection_with_blank_text` function L174–188 — Adding blank-value reporting does not change exact duplicate-row counts.; `test_api_upload_all_duplicates_rejected_by_default` function L195–216 — Uploading DM records that already exist returns HTTP 409 Conflict with structured metadata.; `test_api_upload_insert_new_only_when_all_duplicates` function L219–238 — When duplicate_action='insert_new_only' and all records exist, reports 0 inserted and N skipped safely.; `test_api_upload_mixed_records_with_insert_new_only` function L241–274 — When duplicate_action='insert_new_only', inserts only new rows and skips duplicate rows.; `test_api_preview_detects_duplicates` function L281–305 — POST /ingestion/preview provides duplicate counts and sample keys without writing to DB.; `test_diagnostic_dm_9001_to_9005_duplicate_detection` function L308–371 — Diagnostic test verifying STDY001-9001 through STDY001-9005 duplicate detection:; `test_transaction_rollback_preserves_existing_data` function L379–416 — Ensure that simulated database failure rolls back without leaving partial batches or corrupting existing records..

### [tests/test_hgb_week8_approval_flow.py](../tests/test_hgb_week8_approval_flow.py)

Pytest regression or evaluation coverage for test hgb week8 approval flow. **103 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_extract_plan_datasets_bullet_format` function L16–35 — Verify that _extract_plan_datasets parses '- Table: adlb' without treating prose words as tables.; `test_hgb_week8_approval_workflow_end_to_end` function L38–95 — Verify end-to-end approval request with the user's exact question and plan.; `test_sql_validator_rejects_unauthorized_tables` function L98–103 — Verify that unauthorized tables are still strictly rejected by validate_sql..

### [tests/test_insight_validation_and_recovery.py](../tests/test_insight_validation_and_recovery.py)

Pytest regression or evaluation coverage for test insight validation and recovery. **168 lines.**

Direct imports: `pytest`.

Entry points/declarations: `test_1_insight_containing_supported_numeric_values` function L42–54 — 1. An insight containing supported numeric values passes validation.; `test_2_unsupported_numeric_claim` function L57–67 — 2. An unsupported numeric claim is caught and fails validation.; `test_3_highest_lowest_claim_with_valid_evidence` function L70–84 — 3. A highest/lowest claim matching deterministic evidence passes validation.; `test_4_ranking_claim_with_missing_or_mismatched_evidence` function L87–107 — 4. A ranking claim with missing or mismatched evidence is caught.; `test_5_insight_regeneration_after_validation_failure` function L110–147 — 5. Insight regeneration receives actionable validation feedback.; `test_6_exhaustion_of_allowed_retry_count` function L150–168 — 6. Exhaustion of the allowed retry count results in controlled terminal routing..

### [tests/test_main_identity.py](../tests/test_main_identity.py)

Pytest regression or evaluation coverage for test main identity. **27 lines.**

Entry points/declarations: `test_openapi_has_no_bearer_security_scheme` function L7–11; `test_analytics_request_uses_selected_tables_without_credentials` function L14–27.

### [tests/test_reliability.py](../tests/test_reliability.py)

Pytest regression or evaluation coverage for test reliability. **247 lines.**

Direct imports: `copy`, `decimal`, `fastapi`, `json`, `pytest`, `sqlalchemy`, `time`.

Entry points/declarations: `test_invalid_results` function L19–20; `test_grain_and_required_fields` function L23–28; `test_sql_output_contract` function L31–36; `test_eda_null_blank_zero_sentinel_and_no_mutation` function L39–48; `test_eda_dates_outliers_small_sample` function L51–57; `RedisFixture` class L60–64; `test_cache_integrity_expiry_invalidation_and_scope` function L67–81; `test_cache_unavailable_falls_back` function L84–90; `test_stage_retry_and_sanitization` function L93–106; `graph_fixture` function L109–121; `test_invalid_results_cannot_reach_insights` function L124–128; `test_valid_results_skip_generic_eda` function L131–137; `test_cache_population_follows_result_validation` function L140–153; `test_correction_is_revalidated` function L156–161; `test_result_correction_limit` function L164–170; `test_chart_and_pdf_reject_bad_output` function L173–176; `test_durable_targeted_recovery_and_cancel_without_user_identity` function L179–205; `test_saved_analysis_report_uses_validated_state` function L208–233; `test_report_renderer_retries_without_persistence` function L234–247.

### [tests/test_report_history.py](../tests/test_report_history.py)

Pytest regression or evaluation coverage for test report history. **44 lines.**

Direct imports: `fastapi`, `io`, `pytest`, `reportlab`.

Entry points/declarations: `sample_pdf` function L13–18; `test_report_generation_without_credentials_or_persistence` function L21–38; `test_persistent_history_routes_are_not_active` function L41–44.

### [tests/test_selection_aware_table_validation.py](../tests/test_selection_aware_table_validation.py)

Pytest regression or evaluation coverage for test selection aware table validation. **262 lines.**

Direct imports: `os`, `pytest`, `sys`.

Entry points/declarations: `test_registered_tables_allowlist` function L35–42 — Verify application registered table allowlist.; `test_a_block_when_adae_missing` function L45–71 — TEST A: Question requires ADAE and ADSL. Only ADSL is selected.; `test_b_run_when_both_selected` function L74–108 — TEST B: Question requires ADAE and ADSL. Both are selected.; `test_c_request_adlb_when_missing` function L111–131 — TEST C: Question requires ADLB and ADSL. Only ADSL is selected.; `test_d_table_does_not_exist` function L134–146 — TEST D: Question requires a table that does not exist.; `test_e_ast_blocks_unauthorized_table_in_sql` function L149–172 — TEST E: Question requires ADAE and ADSL. Both are selected,; `test_f_deselect_before_execution_prevents_stale_run` function L175–199 — TEST F: Question requires ADAE and ADSL. Both are selected initially,; `test_g_adsl_alone_question` function L202–220 — TEST G: Question can be answered using ADSL alone. Only ADSL is selected.; `test_h_blocked_pipeline_resumes_when_user_selects_table` function L223–262 — TEST H: A pipeline is blocked because ADAE is missing..

### [docs/FILE_BY_FILE_INDEX.md](FILE_BY_FILE_INDEX.md)

This generated source index. Regenerate it with `python scripts/build_file_index.py`; the file omits itself from the scanner to avoid recursive growth.

