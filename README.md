# Clinical Analytics Report Agent

The current application has one FastAPI entry point, `app.main:app`, and a React frontend with Clinical and Technical workspaces. It supports dataset ingestion and ingestion-time EDA, schema management, natural-language clinical analysis, validated read-only SQL, insights, Plotly visualizations, and PDF generation. The separate Governed Workspace is outside the current product scope.

The Clinical Workspace uses the existing LangGraph plan, approval, SQL, result-validation, insight, chart, and recovery stages. Dataset-wide EDA runs during ingestion, not after each question. Workflow state and operational audit records remain in MySQL. Optional Redis caches validated result rows; MySQL remains authoritative. This checkout does not have an active RAG retrieval stage.

**Prototype security boundary:** The API has no application authentication or user-specific access control. Run it only in a trusted local development environment. It is unsuitable for public or production deployment without appropriate access controls and network protection.

## Run locally

Use Python 3.12, Node 24, a configured MySQL account, and the project virtual environment. Copy `.env.example` to `.env` and set database and model credentials. Never commit `.env`.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

In another shell:

```powershell
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to the default API on port 8001. No clinical access token is required. Redis is optional (`REDIS_URL`, `REDIS_TTL_SECONDS`).

If PDF generation returns `403: Not authenticated`, an older authenticated API process is still serving port 8001. Stop that process, start `app.main:app` from this checkout using the command above, and refresh the frontend. The updated API's `/openapi.json` does not contain an `HTTPBearer` security scheme.

The analytics API is under `/analytics`; ingestion and schema routes retain their existing paths. PDF generation returns the report for human review without saving it. Once the reviewer clicks **Acknowledge Review**, the exact PDF is stored in MySQL and appears in Report History. Run checks with `.venv\Scripts\python -m pytest -q` and `npm --prefix frontend test -- --reporter=dot`. See [deployment notes](docs/DEPLOYMENT.md).

## Future enhancements

**Governed Clinical Analytics Workspace:** Future versions can introduce study-level access control, role-based permissions, approval workflows, and persistent workflow recovery to support secure, auditable, multi-study clinical analytics.

**Persistent PDF report history:** `POST /reports/acknowledge` saves the reviewed PDF and metadata in MySQL. `GET /reports` lists acknowledged reports; `GET /reports/{report_id}/pdf` views the original PDF and `?download=true` downloads it. Repeating acknowledgement with the same report ID does not create a duplicate. Existing historical rows remain untouched and are not shown by the new history list. The legacy `clinical_reports.user_id` field contains the fixed value `local-prototype` for new rows; it does **not** provide per-user isolation. This feature is suitable only for the trusted single-user development environment described above.
