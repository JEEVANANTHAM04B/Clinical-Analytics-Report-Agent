# Current project workflow and code guide

This guide describes the **current checkout**, not the archived `COMPLETE_PROJECT_DOCUMENTATION.md`. The active application has Clinical and Technical React views, one FastAPI app, an ingestion pipeline, a LangGraph analysis pipeline, and PDF generation with human acknowledgement before MySQL history storage. The Governed Workspace and FAISS/RAG retrieval are outside the active scope. See [FILE_BY_FILE_INDEX.md](FILE_BY_FILE_INDEX.md) for the maintained-file inventory and current symbol locations.

## How to read this guide

Read the numbered flows below first. Then open the corresponding file in the index and follow its listed functions in source order. A literal commentary on every statement would repeat library internals and tests without clarifying behavior; the index instead identifies every maintained file, every Python top-level class/function, selected frontend declarations, and the package boundaries that connect them. Clinical source datasets, installed `node_modules`, generated `dist`, browser profiles, test caches, and produced PDFs/images are not executable project logic.

## 1. Startup, UI, and API boundary

1. `frontend/src/main.tsx` mounts React's `App` under `StrictMode`. `frontend/src/App.tsx` holds the workspace choice and lazy-loads `ClinicalDashboard` or `TechnicalDashboard`. The Clinical view is the user-facing analysis path; the Technical view exposes dataset and pipeline controls.
2. `frontend/vite.config.ts` serves port 5173 and proxies `/api` to FastAPI port 8001. `frontend/src/api/client.ts` supplies the Axios base URL. `frontend/src/api/{analytics,datasets,database}.ts` provide typed HTTP wrappers. `frontend/src/types/analytics.ts` defines frontend request/result shapes.
3. `app/main.py` constructs FastAPI, configures CORS, mounts the health, ingestion, relationship, database, and analytics routers, and checks/initializes MySQL metadata tables during lifespan startup. `app/config.py` reads settings; `app/core/database.py` creates the SQLAlchemy engine and sessions. `app/database/session.py` initializes metadata tables.
4. `app/schemas/*.py` are Pydantic request/response contracts. They validate transport fields, not the truth of clinical calculations. Endpoint implementations live in `app/api/*.py`; domain logic lives under `app/ingestion`, `app/clinical`, `app/analytics`, `app/ai`, `app/workflow`, `app/visualization`, and `app/reporting`.

## 2. Dataset upload and ingestion-time EDA

`DatasetUploadModal.tsx` calls `frontend/src/api/datasets.ts`, which submits a multipart request to `POST /ingestion/upload` in `app/api/ingestion.py`.

1. `file_validator.validate_upload` checks type, size, and emptiness. `file_reader.read_uploaded_file` assigns a UUID-based safe filename, writes it under the configured upload directory, and parses CSV/XLSX bytes into a pandas `DataFrame`.
2. `metadata.extract_metadata` measures the file's structure. `quality_checker.check_quality` counts missing/blank cells, duplicate rows, empty and constant columns, and emits flags. The quality report is returned in `UploadResponse`. `IngestionResultModal.tsx` currently emphasizes upload status and inserted/skipped counts; it does not render every quality flag.
3. `mysql_loader.load_dataset_to_mysql` also calls `analyzer.analyze_single_dataset`. That path profiles every column through `schema_inference.profile_column`: pandas type, semantic type, null/unique counts, date interpretation, numeric summary, primary-key likelihood, and sensitive-field signals. It validates/sanitizes headers and table names, checks primary-key duplicates, maps types, and inserts eligible rows in MySQL.
4. After insertion, `mysql_loader` persists `DatasetVersion`, `DatasetColumn`, registry metadata, and an operational audit record through `app/database/repository.py`. The original upload file and the MySQL table have different roles: the file is ingestion input; MySQL is the query source. The DataFrame is an in-memory processing object.
5. `POST /ingestion/analyze` is a **separate** multi-file analysis path. `analyzer.analyze_datasets` profiles multiple read-only source files, uses `relationship_detector` to evaluate possible cross-table keys, computes overall quality, and registers relationship candidates for review through `relationship_review`. A normal upload runs single-dataset profiling; it does not automatically call this multi-file endpoint.

EDA is deterministic pandas-based profiling, not an LLM agent. The normal natural-language question workflow does not re-run dataset-wide EDA. Quality flags do not silently repair clinical records. Ingestion rejects invalid files/schema conflicts and requires an explicit duplicate action for primary-key conflicts.

## 3. Workflow state and audit

The prototype has no application authentication or user-specific authorization. Do not expose it publicly or deploy it to production without appropriate access controls.

`app/workflow/recovery.py` starts/resumes an analysis using `app/workflow/store.py` tables for runs, state artifacts, workflow events, and notices. On a plan decision it checks state version, question, selected tables, and current dataset/schema signature before resuming. These checks prevent a stale or changed run from continuing; they are not access controls.

`app/audit/service.py` writes operational events to MySQL `audit_logs`, such as analysis start, plan approval, SQL execution, and result validation. `workflow_events` is a separate per-run event stream. These are operational audit records, not clinical source tables or a substitute for identity verification.

## 4. A clinical question, line by line through the call chain

For example, the user asks: “What is the age distribution of subjects across treatment groups, and what is the mean age in each group?”

1. `ClinicalDashboard.tsx` sends the question, selected tables, and `approval_status='pending'` through `apiService.runAnalytics` (`frontend/src/api/analytics.ts`) to `POST /analytics/run`.
2. The endpoint assembles `ClinicalAnalyticsState` and calls `workflow.recovery.execute`. The run is saved with a data signature and no user ID. `workflow.graph.build_graph` constructs the LangGraph state machine.
3. `preflight_table_selection` checks selected/approved tables using `clinical/table_validator.py`; `load_schema` reads the live MySQL schema using `database/schema_service.py`.
4. `analyze_question` calls `clinical/question_mapping.build_clinical_question_plan`. This deterministic parser normalizes the sentence and matches supported clinical patterns. Its result identifies domain, KPI/metric, datasets, required columns, grouping, calculation, filters, joins, a suggested SQL, and a heuristic confidence. For the example, the special age-distribution branch uses `ADSL`, `AGE`, `TRT01A`, and `USUBJID` and preserves both age-band counts and mean age by arm. The plan preview is formatted deterministically in this case. Other questions can use `ai/llm.generate_response` to ask Gemini for a plan constrained by the approved schema; if Gemini is unavailable, a supported deterministic fallback can apply. Unsupported questions can stop before SQL generation.
5. `human_approval_node` returns a pending plan to the UI. Approval resumes; rejection with feedback reaches `regenerate_analysis_plan` and returns a revised plan for another review. A plan is a proposal, not evidence of a correct clinical interpretation by itself.
6. After approval, the graph validates table selection again. `analytics/sql_generator.generate_sql` receives the original question, approved plan, and authorized schema. It calls Gemini for clinical SQL where available, checks consistency with the structured clinical plan, and may use deterministic SQL from the mapping if generation fails or conflicts. The plan text is never executed as SQL.
7. `analytics/sql_validator.validate_sql` and `clinical/table_validator.enforce_sql_table_boundaries` check read-only syntax, AST/schema/table scope, and clinical plan constraints. `analytics/query_executor.execute_query` validates again, applies MySQL read-only/time/result-size limits, and fetches rows.
8. `analytics/cache.ResultCache` optionally checks Redis immediately before MySQL execution. Its key includes dataset versions, schema, question, plan, SQL, and table selection. A valid cached row set is revalidated; only validated rows are populated after a miss. Redis failure falls through to MySQL. Cache does not skip plan approval or SQL safety validation.
9. `analytics/result_validator.validate_results` checks result shape/types/values and normalizes transport-safe values. A correctable mismatch can route to `correct_results` and regenerate SQL. `analytics/insight_evidence.py` builds numerical/category evidence from verified rows. `ai/insight_generator.py` generates clinical language; `ai/insight_validator.py` checks it against evidence, with bounded regeneration in the graph. `visualization/chart_generator.py` builds a chart specification from verified rows and `visualization/validation.py` checks that its referenced labels and numbers match those rows.
10. The API returns plan/results/insight/chart state to `ClinicalDashboard.tsx`. Components such as `ClinicalApprovalCard`, `VerifiedResultsTable`, `ClinicalInsightsCard`, and `DynamicCharts` display the corresponding stages. A follow-up question goes through `analytics/followup_service.py` and `/analytics/followup`, using prior verified context as allowed by that service.

Graph order, including branches, is defined by `app/workflow/graph.py:2297-2453`. The backend is the authority for approved data and results; frontend views do not validate SQL or compute clinical truth.

## 5. Dashboards, PDF, and report history

`analytics/dashboard_service.py` builds predefined and selection-aware KPI/dashboard data through the analytics API. The frontend's chart components render data with Plotly; they can change chart presentation without changing verified result rows.

`ReportModal.tsx` calls `POST /analytics/report/pdf` without credentials. When a saved analysis ID is supplied, the API uses its persisted, validated results instead of client-provided replacements. `app/reporting/pdf_generator.py` lays out the clinical PDF with ReportLab and chart images; `app/reporting/validation.py` validates the rendered PDF. The modal previews and downloads the returned bytes in the current session. Review acknowledgement is local to the modal and is not a clinical certification. Persistent PDF history remains a future enhancement.

## 6. Key package and library functions used

| Package | Where and what it does |
| --- | --- |
| React, React DOM, TypeScript | `main.tsx` uses `createRoot`; `App.tsx` uses `React.lazy`, `Suspense`, and `useState`; components use typed props/hooks. |
| Vite | Serves the UI, builds assets, and proxies `/api` to port 8001. |
| Axios | `frontend/src/api/client.ts` and wrapper modules send typed HTTP requests. |
| Plotly / `react-plotly.js` | Renders interactive browser charts from validated chart data. |
| `pdfjs-dist` | `PDFViewer`/`PDFPageCanvas` preview saved/generated PDF pages in the browser. |
| FastAPI, Uvicorn | `app/main.py` serves HTTP; `APIRouter`, `Depends`, `UploadFile`, and response models implement endpoints. |
| Pydantic, pydantic-settings | `app/schemas` validates API payloads; `app/config.py` loads typed configuration. |
| pandas, openpyxl | `read_csv`, `read_excel`, `DataFrame` profiling, duplicate/null/type/statistics operations during ingestion. |
| SQLAlchemy, PyMySQL | MySQL engine, sessions, ORM metadata, transactions, and bounded read-only query execution. |
| LangGraph | `StateGraph`, `START`, `END`, conditional edges, and `compile()` orchestrate the approval/execution pipeline. |
| `google-genai` | `client.models.generate_content(...)` calls the Gemini model cascade in `app/ai/llm.py`: primary `gemini-3.5-flash-lite`, secondary `gemini-3.1-flash-lite`, then `gemini-3.8-flash`, `gemini-3.7-flash`, and `gemini-3.5-flash` fallbacks. These are configured model IDs; runtime availability depends on the account/API. |
| SQLGlot | Parses SQL into an AST so validators can inspect statements, tables, and columns. |
| Redis Python client | Optional TTL cache of validated result rows; not authoritative storage. |
| ReportLab, pypdf, Matplotlib | Create, inspect, and chart clinical PDFs. |
| pytest, Vitest, Testing Library, httpx | Python/API and React tests. Evaluation scripts under `evals` and `scripts/run_deepeval_evaluation.py` exercise clinical cases. Optional DeepEval judge code imports `GeminiModel`, `LLMTestCase`, `AnswerRelevancyMetric`, and `FaithfulnessMetric`; DeepEval is an evaluation tool, not a runtime workflow stage. |

The exact installed versions are recorded in `requirements.txt` and `frontend/package.json`. A listed dependency is not necessarily active on every request. There is no active vector index or retrieval node in the current LangGraph.

## 7. Data and model boundaries

* **Clinical source rows:** CSV/XLSX upload and MySQL clinical tables. EDA inspects them; later SQL reads MySQL. Neither an analysis plan nor an LLM response is a clinical source record.
* **Operational metadata:** `DatasetVersion`, `DatasetColumn`, dataset registry, audit rows, workflow runs/events/artifacts, and `ClinicalReport` live in MySQL.
* **Workflow state:** `ClinicalAnalyticsState` carries the question, selected tables, schema, plan, approval, SQL, result rows, evidence, insight, chart, retries, and error/status fields between LangGraph nodes.
* **LLM models:** `app/ai/llm.py` selects Gemini model names and retries/falls back. Model outputs require deterministic validation and human review where provided.
* **Cache:** Redis may hold owner-scoped validated result rows temporarily. It does not replace MySQL or persist PDFs.

## 8. How to navigate the file index

The [file-by-file index](FILE_BY_FILE_INDEX.md) lists each maintained source, test, configuration, and documentation file with its role, line count, direct imported packages, and entry-point symbols with exact starting lines. For a long file, start at the entry-point symbol and follow its calls to other files in the above flow. Test and evaluation files are grouped by the behavior they assert; fixture JSON is input to tests, not production data. Historical docs are marked as such and must not be read as active architecture.
