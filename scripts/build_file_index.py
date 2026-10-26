"""Regenerate the maintained-file symbol and dependency index for this checkout."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "FILE_BY_FILE_INDEX.md"
SOURCE_ROOTS = ("app", "frontend/src", "tests", "evals", "scripts")
ROOT_FILES = (
    "README.md", "COMPLETE_PROJECT_DOCUMENTATION.md", "requirements.txt", "pytest.ini", ".env.example", ".gitignore",
    "frontend/package.json", "frontend/package-lock.json", "frontend/index.html",
    "frontend/vite.config.ts", "frontend/tailwind.config.js", "frontend/postcss.config.js",
    "frontend/tsconfig.json", "frontend/tsconfig.app.json", "frontend/tsconfig.node.json",
)
RUNTIME_ROLES = {
    ".env.example": "Non-secret template for MySQL, model, Redis, and upload settings; copy to a private `.env` before local startup.",
    ".gitignore": "Ignore rules for local secrets, dependencies, caches, and generated artifacts.",
    "README.md": "Current application scope, startup, API locations, and future enhancement note.",
    "requirements.txt": "Pinned or bounded Python runtime and test dependencies.",
    "pytest.ini": "Pytest discovery and runner configuration.",
    "frontend/package.json": "Frontend runtime/dev package manifest and dev/build/test commands.",
    "frontend/package-lock.json": "Locked frontend dependency graph used by `npm ci`; installed package internals are excluded.",
    "frontend/index.html": "Vite HTML entry containing the React mount element.",
    "frontend/vite.config.ts": "Vite React plugin, Vitest environment, dev server, and `/api` proxy.",
    "frontend/tailwind.config.js": "Tailwind theme/content scanning configuration.",
    "frontend/postcss.config.js": "PostCSS/Tailwind/autoprefixer build configuration.",
    "frontend/tsconfig.json": "TypeScript project references.",
    "frontend/tsconfig.app.json": "Browser-side TypeScript compiler checks.",
    "frontend/tsconfig.node.json": "Build-tool-side TypeScript compiler checks.",
    "COMPLETE_PROJECT_DOCUMENTATION.md": "Archived architecture manual; contains removed RAG/Governed Workspace details and is not current implementation authority.",
    "app/main.py": "FastAPI app creation, startup lifespan, middleware, and router registration.",
    "app/config.py": "Typed environment settings for the API, database, and uploads.",
    "app/core/database.py": "SQLAlchemy engine, sessions, and database health helpers.",
    "app/core/logging_config.py": "Structured application logging setup.",
    "app/audit/service.py": "Persists and reads operational audit events in MySQL.",
    "app/workflow/graph.py": "LangGraph nodes, conditional routers, plan approval, SQL/result/insight/chart pipeline.",
    "app/workflow/state.py": "Typed state passed among LangGraph nodes.",
    "app/workflow/runtime.py": "Stage wrapper, status recording, and bounded retry handling.",
    "app/workflow/recovery.py": "Saved-run start/resume, version checks, and stage recovery.",
    "app/workflow/reliability.py": "Error classification, retry policy, and user-safe failure messages.",
    "app/workflow/store.py": "SQL tables and CRUD for runs, snapshots, workflow events, and notices.",
    "app/api/analytics.py": "Analytics, dashboards, follow-up, and PDF generation endpoints.",
    "app/api/database.py": "Dataset registry, metadata, load, and audit-list endpoints.",
    "app/api/ingestion.py": "Upload, preview, and multi-file analysis endpoints.",
    "app/api/relationships.py": "Relationship-candidate inspection and review endpoints.",
    "app/api/health.py": "API and MySQL health endpoints.",
    "app/ai/llm.py": "Gemini client, model cascade, generation, and retry/failure handling.",
    "app/ai/insight_generator.py": "Produces narrative insight from verified rows with deterministic fallback.",
    "app/ai/insight_validator.py": "Checks insight claims against result evidence.",
    "app/ai/insight_regenerator.py": "Retries an insight with validation feedback.",
    "app/analytics/cache.py": "Optional dataset-version-scoped Redis validated-result cache.",
    "app/analytics/dashboard_service.py": "Clinical and selected-table KPI/dashboard queries.",
    "app/analytics/eda.py": "Result-level quality assessment helper; dataset-wide EDA is under ingestion.",
    "app/analytics/followup_service.py": "Answers follow-up questions using prior analysis context.",
    "app/analytics/insight_evidence.py": "Builds numerical/category evidence from verified result rows.",
    "app/analytics/query_executor.py": "Revalidates and executes bounded read-only SQL against MySQL.",
    "app/analytics/result_validator.py": "Checks result row shape and values, with transport normalization.",
    "app/analytics/sql_generator.py": "Gemini/deterministic clinical question-and-plan to SQL conversion.",
    "app/analytics/sql_validator.py": "Read-only SQL AST, schema, column, and safety validation.",
    "app/clinical/question_mapping.py": "Deterministic natural-language clinical intent and KPI mapping.",
    "app/clinical/table_validator.py": "Selected/approved table requirements and SQL table-boundary enforcement.",
    "app/clinical/schema_registry.py": "Clinical dataset/column/relationship schema catalog for prompts and checks.",
    "app/clinical/dataset_metadata.py": "Clinical domain dataset and column metadata definitions.",
    "app/clinical/dataset_registry_service.py": "Approved dataset registry persistence and status changes.",
    "app/clinical/kpi_definitions.py": "Canonical clinical KPI definitions and SQL templates.",
    "app/clinical/relationship_map.py": "Approved clinical relationships and join lookup.",
    "app/database/models.py": "SQLAlchemy ORM models for metadata, audit, and saved reports.",
    "app/database/repository.py": "Database repository CRUD for metadata and audit records.",
    "app/database/schema_service.py": "Reads the live MySQL table/column schema for planning and validation.",
    "app/database/session.py": "Initializes and serves operational metadata tables/sessions.",
    "app/ingestion/analyzer.py": "Single/multi-dataset profiling, quality summaries, and relationship detection.",
    "app/ingestion/file_reader.py": "Saves uploaded files and parses CSV/XLSX into pandas DataFrames.",
    "app/ingestion/file_validator.py": "Checks upload type, size, and non-emptiness.",
    "app/ingestion/metadata.py": "Extracts dataset/column structure for upload responses.",
    "app/ingestion/mysql_loader.py": "Validates, profiles, deduplicates, type-maps, loads, and registers MySQL datasets.",
    "app/ingestion/privacy_detector.py": "Flags potential direct/sensitive identifiers in uploaded columns.",
    "app/ingestion/quality_checker.py": "Computes initial missing/blank/duplicate/constant quality metrics.",
    "app/ingestion/relationship_detector.py": "Scores possible primary/foreign-key relationships across datasets.",
    "app/ingestion/relationship_regenerator.py": "Proposes/validates alternate relationship candidates with model assistance.",
    "app/ingestion/relationship_review.py": "Stores and applies human relationship review decisions.",
    "app/ingestion/schema_inference.py": "Infers semantic column types, dates, statistics, and missingness.",
    "app/reporting/pdf_generator.py": "Builds ReportLab clinical PDF pages, tables, rules, charts, and provenance.",
    "app/reporting/safe_pdf.py": "PDF-safe text, layout, and rendering helpers.",
    "app/reporting/validation.py": "Checks completed PDF bytes before saving.",
    "app/visualization/chart_generator.py": "Builds chart specifications from validated SQL rows.",
    "app/visualization/validation.py": "Verifies chart labels and numbers match validated rows.",
    "frontend/src/main.tsx": "Mounts the React application under StrictMode.",
    "frontend/src/App.tsx": "Switches between lazy-loaded Clinical and Technical workspaces.",
    "frontend/src/pages/ClinicalDashboard.tsx": "Clinical question, approval, result, chart, report, and recovery UI state.",
    "frontend/src/pages/TechnicalDashboard.tsx": "Technical dataset, database, pipeline, and inspection workspace.",
    "frontend/src/pages/WorkspaceSelection.tsx": "Workspace choice presentation component (not the current App entry view).",
    "frontend/src/api/client.ts": "Shared Axios API client/base URL.",
    "frontend/src/api/analytics.ts": "Typed analytics and follow-up HTTP requests.",
    "frontend/src/api/database.ts": "Typed database/metadata HTTP requests.",
    "frontend/src/api/datasets.ts": "Typed upload, preview, and dataset HTTP requests.",
    "frontend/src/types/analytics.ts": "TypeScript request, workflow, result, and chart contracts.",
}


def role(path: str, text: str) -> str:
    if path in RUNTIME_ROLES:
        return RUNTIME_ROLES[path]
    name = Path(path).stem.replace("_", " ").replace("-", " ")
    if path.endswith("/__init__.py"):
        return "Marks this directory as a Python package; inspect exports/imports below."
    if path.startswith("app/schemas/"):
        return f"Pydantic transport models for {name} API data."
    if path.startswith("frontend/src/components/"):
        return f"React UI component/helper for {name}; receives props and renders a workspace section."
    if path.startswith("frontend/src/__tests__/"):
        return f"Vitest/Testing Library regression checks for {name}."
    if path.startswith("frontend/src/assets/"):
        return f"Static image asset ({name}); no executable logic."
    if path.startswith("frontend/src/") and path.endswith(".css"):
        return f"Styles for {name}; affects appearance, not backend calculations."
    if path.startswith("tests/evaluation/datasets/") or path.startswith("evals/datasets/"):
        return f"Maintained evaluation-case data for {name}; fixtures, not production records."
    if path.startswith("tests/"):
        return f"Pytest regression or evaluation coverage for {name}."
    if path.startswith("evals/"):
        return f"Offline/evaluation script or result for {name}; not a live request stage."
    if path.startswith("scripts/"):
        return f"Manually invoked setup, migration, validation, or artifact script for {name}."
    if path.startswith("docs/"):
        first = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), name)
        return f"Project documentation: {first}. Historical files may describe retired paths."
    if path.endswith(".md"):
        return f"Project documentation for {name}."
    if path.endswith(".json") or path.endswith(".ini") or path.endswith(".js") or path.endswith(".ts"):
        return f"Project configuration or data contract for {name}."
    return f"Maintained project file for {name}."


def python_symbols(source: str) -> tuple[list[str], list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []
    imports: set[str] = set()
    symbols: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            item = f"`{node.name}` {kind} L{node.lineno}–{getattr(node, 'end_lineno', node.lineno)}"
            doc = ast.get_docstring(node)
            if doc:
                first = doc.strip().splitlines()[0].strip().replace("`", "'")
                if first and len(first) <= 160:
                    item += f" — {first}"
            symbols.append(item)
    return sorted(imports - {"app", "tests", "evals"}), symbols


def frontend_symbols(source: str) -> tuple[list[str], list[str]]:
    imports = sorted(set(re.findall(r"from\s+['\"]([^'\"]+)['\"]", source)))
    imports = [x for x in imports if not x.startswith(".")]
    symbols: list[str] = []
    for lineno, line in enumerate(source.splitlines(), 1):
        match = re.search(r"\b(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|const)\s+([A-Za-z_$][\w$]*)", line)
        if match and ("export " in line or lineno <= 50 or match.group(1)[0].isupper()):
            symbols.append(f"`{match.group(1)}` L{lineno}")
    return imports, symbols[:24]


def include(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if any(part in {"node_modules", "dist", "__pycache__", ".pytest_cache", ".venv"} for part in path.parts):
        return False
    if rel.startswith("docs/"):
        return path.suffix in {".md", ".mmd"} and rel != "docs/FILE_BY_FILE_INDEX.md"
    if rel.startswith("evals/"):
        return path.suffix in {".py", ".json", ".md"}
    if rel.startswith("frontend/src/"):
        return path.suffix in {".ts", ".tsx", ".css", ".png", ".svg"}
    return path.suffix in {".py", ".json"}


def main() -> None:
    paths: list[Path] = []
    for name in SOURCE_ROOTS:
        base = ROOT / name
        if base.is_dir():
            paths.extend(p for p in base.rglob("*") if p.is_file() and include(p))
    paths.extend(p for name in ROOT_FILES if (p := ROOT / name).is_file())
    paths.extend(p for p in (ROOT / "docs").rglob("*") if p.is_file() and include(p))
    paths = sorted(set(paths), key=lambda p: p.relative_to(ROOT).as_posix().lower())
    lines = [
        "# Maintained-file index — current checkout", "",
        "Generated from source by `scripts/build_file_index.py`. Each entry gives the file's purpose, line count, external/direct imports, and exact source locations for top-level Python symbols or selected frontend declarations. Open the source for statement-level behavior; read [CURRENT_PROJECT_WORKFLOW_GUIDE.md](CURRENT_PROJECT_WORKFLOW_GUIDE.md) for the call chain and clinical meaning.",
        "", f"Maintained files indexed: **{len(paths) + 1}** (including this generated index). This omits installed packages, generated builds, output PDFs/images, temporary browser/test files, and clinical source datasets. `.env` is deliberately omitted because it may contain secrets; `.env.example` is indexed.", "",
    ]
    old_group = None
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        group = rel.split("/")[0]
        if group != old_group:
            lines.extend([f"## {group}", ""])
            old_group = group
        source = path.read_text(encoding="utf-8", errors="replace") if path.suffix in {".py", ".ts", ".tsx", ".css", ".js", ".json", ".md", ".mmd", ".ini", ".html", ".txt", ".example"} or path.name == ".gitignore" else ""
        line_count = len(source.splitlines()) if source else 0
        imports: list[str] = []
        symbols: list[str] = []
        if path.suffix == ".py":
            imports, symbols = python_symbols(source)
        elif path.suffix in {".ts", ".tsx"}:
            imports, symbols = frontend_symbols(source)
        source_link = "../" + rel
        lines.extend([f"### [{rel}]({source_link})", "", f"{role(rel, source)} **{line_count} lines.**", ""])
        if imports:
            lines.extend(["Direct imports: " + ", ".join(f"`{item}`" for item in imports) + ".", ""])
        if symbols:
            lines.extend(["Entry points/declarations: " + "; ".join(symbols) + ".", ""])
    lines.extend(["### [docs/FILE_BY_FILE_INDEX.md](FILE_BY_FILE_INDEX.md)", "", "This generated source index. Regenerate it with `python scripts/build_file_index.py`; the file omits itself from the scanner to avoid recursive growth.", ""])
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(paths)} maintained files and {len(lines)} Markdown lines")


if __name__ == "__main__":
    main()
