> Historical note (2026-10-18): References below to the separate Governed Workspace describe the former implementation. The current application exposes only the Clinical and Technical workspaces; see README.md for the present scope.

# Reliability enhancement checklist

Historical checklist from 2026-10-17. Analysis-time EDA entries below were superseded by the ingestion-only workflow described in `EDA_WORKFLOW_SIMPLIFICATION.md`.

Source inspection, 2026-10-17: the default React ClinicalDashboard uses
`app.main` / `app.api.analytics` / `app.workflow.graph`. The separately deployed
`app.governed_app` has its own graph, SQLAlchemy operational records and SQLite
LangGraph checkpoints. Preserve both; do not mistake governed features for default
workspace features. Existing `clinical_reports` persists owner-scoped PDF bytes.

Inspection found: result validation only checks list/dict shape in the main path;
chart errors fall back without validation; main resume fields do not select a
graph entry point; governed source duplicate warnings can be approved through;
follow-up deterministic answers convert missing measurements to zero; no Redis.
Ingestion already profiles nulls, exact duplicates, types and relationships.
SQL safety, clinical templates, plan regeneration and insight regeneration exist.
Frontend already propagates latest nonempty follow-up results. Active RAG code
is absent; bytecode and historical documentation contain old references.

Implementation sequence (completion/evidence recorded in RELIABILITY_REPORT.md):

- [x] Inspect routes, graphs, state, agents, ingestion, models, auth, reports,
  frontend clients/components, tests, dependencies and architecture documentation.
- [x] Structured stage outcomes, bounded retry and targeted durable recovery.
- [x] Result validation and correction/revalidation gates; structural SQL correction is bounded.
- [x] Deterministic EDA, missingness and grain-aware duplicate checks. Full source join-cardinality inference remains limited by available relationship metadata.
- [x] Evidence-grounded interpretation and downstream chart validation.
- [x] Clinical status, failure/retry/stop and review actions.
- [x] Optional Redis with version/scope keys, revalidation and safe fallback.
- [x] Extend report validation/history without replacing ClinicalReport.
- [x] Verify active RAG removal and update diagrams/documentation.
- [x] Execute final focused tests, fix regressions and record exact results and limitations. Live MySQL checks remain unverified due to authentication failure.

Environment verified: project `.venv/Scripts/python.exe`, Python 3.12.10.
Dependencies were installed in this project environment. Live MySQL authentication currently rejects the configured account; integration checks requiring that server remain unverified.
No source table modification or destructive migration is authorized or needed.
