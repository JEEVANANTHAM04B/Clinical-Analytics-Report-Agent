> Historical note: The architecture decisions below describe an earlier implementation. The current prototype has no application authentication. Acknowledged PDFs now have persistent MySQL report history, but there is no per-user isolation. It is unsuitable for public or production deployment without appropriate access controls; see README.md for the present scope.

# Audit and implementation direction

Inspected Python modules, React components, dependency manifests, existing tests, schemas, routes and the supplied SVG. Current architecture: React 18 / Vite / Tailwind, FastAPI, SQLAlchemy + MySQL, LangGraph, Gemini, Plotly and ReportLab. Reference-document retrieval has been removed.

| Requirement | Baseline | Change direction |
|---|---|---|
| Clinical plans, SQL boundary checks, charts | Implemented; needs runtime verification | Preserve legacy modules |
| Human approval | Partial: client flag, graph compiled without checkpointer | Durable interrupt/resume, server-owned state |
| Four agents, data quality, EDA | Partial: SQL and insights; basic result shape validation | Typed stage contracts and deterministic checks |
| Authentication / study access | Missing on analytics API | Server-configured bearer identities and study grants |
| PDF | Defective: shared cache, client-supplied results, default certified status | Stored artifact report, explicit review decision |
| Follow-up | Partial: client context | Parent analysis, same session, fresh criteria approval |
| Reference-document retrieval | Removed from workflows, UI, API and dependencies | Insights are based on validated SQL results and computed evidence |
| Persistence / notifications | Audit tables only | Operational store separate from clinical data |
| Dependencies | Incomplete manifest | Separate tested enhancement requirements |
| Clinical UI | Present; seeded history and approval claims | New governed workspace, preserve legacy screens |

## Reference lock
Primary reference: existing ClinicalDashboard and index.css (slate canvas #F8FAFC, navy text #0F172A, Inter/system typography, compact analytical tables). Secondary reference: supplied workflow SVG (teal process and amber review states). Refero craft-details.md informs visible focus, explicit labels and responsive forms. The user brief supplies the approval-to-follow-up sequence. No decorative hero or invented clinical findings. New workspace uses these existing tokens, a four-stage strip, persistent session list and a single visible review panel.

## Architecture decision
Add a governed API/workspace alongside the existing modules; preserve legacy APIs behind an explicit deployment flag because their request-owned state cannot provide the required security boundary. Use existing deterministic clinical question mappings; unsupported questions fail closed. MySQL remains the clinical source. SQLAlchemy operational tables support a separate MySQL URL or local SQLite. LangGraph SQLite checkpoints are separate and suitable for a single process, not a multi-replica deployment. No external model calls or clinical data transmission during local tests.
