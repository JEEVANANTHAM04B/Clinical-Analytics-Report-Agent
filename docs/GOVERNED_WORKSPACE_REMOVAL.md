# Governed Workspace removal — 2026-10-18

> Historical record: the bearer-token and owner-scoped report paths described below were removed later. See the current [README](../README.md). The active prototype has no application authentication and persistent PDF history is a future enhancement.

The current user-facing application has Clinical and Technical workspaces, served by `app.main:app`. The separate Governed Workspace, `app.governed_app:app`, its study-scoped workflow package, dedicated UI, dedicated tests, and supplemental requirements file were removed. The development proxy on port 8001 now targets the main API. No clinical data, SQL-generation rule, model configuration, or database schema was changed.

The main application still uses bearer-token identity and principal validation (`app/core/identity.py`) and its operational run, artifact, notice, and audit-event store (`app/workflow/store.py`). Those helpers were extracted from the governed package before removing it. Owner-bound saved analysis, recovery, report generation, report history, and audit paths continue to use them. All remaining application and test modules collect without a governed import.

Validation: the default FastAPI lifespan completed against the configured local MySQL instance; `/health` and `/openapi.json` returned 200, with no governed workflow routes. The frontend production build succeeded and its test suite passed 20/20. Core workflow, ingestion, SQL/result validation, insight, report, recovery, and live-database tests passed 183/183 (`governed-removal-tests.xml`); dashboard tests passed 41/41 (`governed-removal-dashboard.xml`); token identity passed 1/1 (`governed-removal-identity.xml`). Full test collection found 329 tests without an import error.

The unchanged SQL-generation suite passed 25/26 (`governed-removal-sql.xml`). Its one failure is the pre-existing hard-coded expectation of 2,518 serious adverse events against a configured database returning 2,517. This mismatch was recorded in `RELIABILITY_REPORT.md` before this removal; source records and expected results were left unchanged. The active checkout has no RAG retrieval stage to preserve or validate. Historical documents that describe the former governed service are labeled as such.

Future scope: **Governed Clinical Analytics Workspace:** Future versions can introduce study-level access control, role-based permissions, approval workflows, and persistent workflow recovery to support secure, auditable, multi-study clinical analytics.
