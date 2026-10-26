# Current implementation

`app.main:app` serves ingestion, dataset/schema management, Clinical Workspace analytics, and PDF generation. The frontend has Clinical and Technical workspaces. Human-acknowledged PDFs are stored in MySQL and shown in Report History. The separate Governed Workspace and its study-scoped service have been removed from the current application scope.

The main LangGraph workflow retains plan approval, validated read-only SQL, result correction and revalidation, evidence-linked insights, chart validation, and report generation. Generic dataset EDA runs during ingestion. Saved-run state and audit events use `app/workflow/store.py`. The prototype has no application authentication or user-specific access control and must remain on a trusted local network. Existing clinical datasets are unchanged.

The current checkout has no active RAG retrieval stage. For startup details, see [deployment](DEPLOYMENT.md). The former governed implementation is a future enhancement, described in [README](../README.md).
