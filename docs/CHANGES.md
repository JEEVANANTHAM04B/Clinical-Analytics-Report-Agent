# File-by-file change summary

| File | Change | Purpose |
|---|---|---|
| `app/ai/llm.py` | Modified | Defer missing-key failure until an actual model call; enable offline imports |
| `app/governed/__init__.py` | Created | Package boundary |
| `app/governed/analysis.py` | Created | Scoped SQL, source quality and numerical validation |
| `app/governed/api.py` | Created | Authenticated workflow endpoints |
| `app/governed/contracts.py` | Created | Strict request and stage contracts |
| `app/governed/report.py` | Created | Stored-artifact PDF rendering |
| `app/governed/retrieval.py` | Removed | Reference-document retrieval is no longer part of the governed workflow |
| `app/governed/service.py` | Created | Ownership, versioning, resume and regeneration |
| `app/governed/store.py` | Created | Operational relational metadata and artifact persistence |
| `app/governed/workflow.py` | Created | Four-agent graph, approvals and bounded recovery |
| `app/governed_app.py` | Created | Deployment / supporting implementation |
| `docs/architecture.mmd` | Created | Delivery documentation and verification evidence |
| `docs/architecture.svg` | Created | Delivery documentation and verification evidence |
| `docs/AUDIT.md` | Created | Delivery documentation and verification evidence |
| `docs/DEPLOYMENT.md` | Created | Delivery documentation and verification evidence |
| `docs/IMPLEMENTATION.md` | Created | Delivery documentation and verification evidence |
| `docs/legacy-test-results.xml` | Created | Delivery documentation and verification evidence |
| `docs/npm-audit.json` | Created | Delivery documentation and verification evidence |
| `docs/REPOSITORY_INVENTORY.md` | Created | Delivery documentation and verification evidence |
| `docs/test-results.xml` | Created | Delivery documentation and verification evidence |
| `frontend/src/__tests__/GovernedWorkspace.test.tsx` | Created | Regression / fixture validation |
| `frontend/src/App.tsx` | Modified | Clinical workspace and preserved legacy navigation |
| `frontend/src/pages/GovernedWorkspace.css` | Created | Clinical workspace and preserved legacy navigation |
| `frontend/src/pages/GovernedWorkspace.tsx` | Created | Clinical workspace and preserved legacy navigation |
| `requirements-governed.txt` | Created | Deployment / supporting implementation |
| RAG-specific components and embedding dependencies | Removed | Insights now use validated SQL results and deterministic evidence |
| `tests/test_governed.py` | Created | Regression / fixture validation |
| `tests/test_governed_api.py` | Created | Regression / fixture validation |
| `verified-environment.txt` | Created | Deployment / supporting implementation |