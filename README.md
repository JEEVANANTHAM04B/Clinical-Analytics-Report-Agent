# Clinical Analytics MVP

> **AI-Powered Healthcare Analytics and Reporting Platform**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange)](https://mysql.com)
[![Pandas](https://img.shields.io/badge/Pandas-2.2-purple)](https://pandas.pydata.org)

---

## Project Overview

Clinical Analytics MVP is a backend API platform for healthcare analytics.
It combines structured clinical data (MySQL) with AI-assisted analysis (Qwen3 8B via Ollama)
and knowledge retrieval (RAG) to generate accurate, audited clinical reports in PDF format.

### Architecture Principles

| Layer | Technology | Purpose |
|---|---|---|
| **Structured Data** | MySQL | Clinical analytics, patient data, metrics |
| **Knowledge Base** | RAG + Vector DB | Terminology, definitions, reference docs |
| **Analytics** | Python + Pandas | Accuracy-critical calculations |
| **AI Insights** | Qwen3 8B (Ollama) | Interpretation, narrative, chart specs |
| **Orchestration** | LangChain + LangGraph | Agent workflows |
| **Visualization** | Plotly | Charts from verified query results |
| **Reports** | ReportLab | PDF generation |
| **API** | FastAPI | REST API layer |

> **Key Principle:** The LLM never performs calculations or invents data.
> Python/MySQL handle all numbers. The LLM interprets and narrates.

---

## Project Phases

- [x] **Phase 1** — Project Setup & Environment ✅
- [x] **Phase 2** — Dataset Ingestion & Initial Validation ✅
- [x] **Phase 3** — Data Quality + Schema / Type Validation ✅
- [x] **Phase 4 Step 3** — Relationship Review & Human Confirmation ✅ *(current)*
- [ ] Phase 4 Step 4 — Clinical Schema Mapping & Table Planning
- [ ] Phase 5 — MySQL Loading & Persistence
- [ ] Phase 6 — Analytics Engine (SQL + Pandas)
- [ ] Phase 7 — LLM Integration (Ollama + Qwen3)
- [ ] Phase 8 — RAG Pipeline (Vector DB)
- [ ] Phase 9 — LangGraph Orchestration
- [ ] Phase 10 — Plotly Visualizations & PDF Reports
- [ ] Phase 11 — Frontend

---

## Quick Start

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- Git

### Installation

```powershell
# 1. Clone the repository
git clone <repository-url>
cd clinical_analytics

# 2. Create virtual environment
python -m venv venv
venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your MySQL credentials

# 5. Create the MySQL database
# In MySQL Workbench or mysql CLI:
# CREATE DATABASE clinical_analytics_db;

# 6. Start the API server
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### Verify Installation & Endpoints

| Endpoint | Method | Purpose | Expected Response |
|---|---|---|---|
| `/` | `GET` | API Root info | JSON with version, phase, and links |
| `/health` | `GET` | App health check | `{"status": "healthy"}` |
| `/health/db` | `GET` | MySQL connection health | `{"status": "healthy", ...}` |
| `/docs` | `GET` | Interactive Swagger UI | OpenAPI documentation |
| `/ingestion/upload` | `POST` | Upload and validate single dataset | JSON profiling & storage info |
| `/ingestion/analyze` | `POST` | Comprehensive schema & quality analysis | Full multi-table relational analysis |
| `/relationships/candidates` | `GET` | List detected relationship candidates | JSON candidate list with metrics |
| `/relationships/review` | `POST` | Approve, reject, or edit a candidate | JSON confirmation response |
| `/relationships/approved` | `GET` | List all approved relationships | JSON approved relationships |
| `/relationships/rejected` | `GET` | List all rejected relationships | JSON rejected relationships |

---

## Phase 4 Step 3 — Relationship Review & Human Confirmation

### The Human-in-the-Loop Workflow

```
CSV / XLSX Datasets
        ↓
POST /ingestion/analyze
        ↓
Detected Relationship Candidates
        ↓
GET /relationships/candidates
        ↓
Analyst Reviews Evidence (Match %, Nulls, Orphaned Records)
        ↓
POST /relationships/review (APPROVE / REJECT / EDIT)
        ↓
GET /relationships/approved (Confirmed Schema Links)
```

### Key Principles

1. **Deterministic Discovery:** Candidates are detected purely by data profiling and foreign-key referential checks in `relationship_detector.py`.
2. **Validation on Review:** `POST /relationships/review` strictly validates that the relationship was actually detected by `/ingestion/analyze`. Arbitrary or fake relationships are rejected with `HTTP 404`.
3. **Analyst Actions:**
   - **APPROVE:** Confirms candidate as valid for analytical schema.
   - **REJECT:** Declines candidate with analyst note.
   - **EDIT:** Modifies target coordinates (requires edited parent/child table & column names).
4. **Read-Only Datasets:** Source clinical CSV files remain completely untouched.
5. **In-Memory Review Store:** Fast, temporary candidate and approval management before final MySQL persistence in Phase 5.

---

## Testing via Swagger or cURL

### 1. Run Dataset Analysis to Detect Candidates

```powershell
curl.exe -X POST "http://127.0.0.1:8001/ingestion/analyze" -H "Content-Type: application/json" -d "{}"
```

### 2. View Detected Candidates

```powershell
curl.exe -s http://127.0.0.1:8001/relationships/candidates
```

### 3. Approve a Detected Candidate

```powershell
curl.exe -X POST "http://127.0.0.1:8001/relationships/review" `
  -H "Content-Type: application/json" `
  -d '{\"parent_table\": \"patients\", \"parent_column\": \"ID\", \"child_table\": \"encounters\", \"child_column\": \"PATIENT\", \"action\": \"APPROVE\", \"analyst_note\": \"Primary encounter linkage verified.\"}'
```

### 4. View Approved Relationships

```powershell
curl.exe -s http://127.0.0.1:8001/relationships/approved
```

---

## Project Structure

```
clinical_analytics/
├── app/
│   ├── main.py                    # FastAPI app entry point & root route
│   ├── config.py                  # Centralized settings (reads .env)
│   ├── api/
│   │   ├── health.py              # GET /health, GET /health/db
│   │   ├── ingestion.py           # POST /ingestion/upload, POST /ingestion/analyze
│   │   └── relationships.py       # Candidate review, approved, and rejected endpoints
│   ├── core/
│   │   ├── database.py            # MySQL SQLAlchemy connection layer
│   │   └── logging_config.py      # Application-wide logging
│   ├── ingestion/
│   │   ├── file_validator.py      # Extension, size, empty checks
│   │   ├── file_reader.py         # CSV/XLSX reading with safe storage
│   │   ├── metadata.py            # Basic structural metadata extraction
│   │   ├── quality_checker.py     # Deterministic quality flags & missingness
│   │   ├── schema_inference.py    # Semantic types, date detection, stats, observations
│   │   ├── relationship_detector.py # PK/FK candidate discovery & referential validation
│   │   ├── relationship_review.py # Candidate store & human approval review service
│   │   ├── privacy_detector.py    # HIPAA direct identifier & PHI detection
│   │   └── analyzer.py            # Orchestrator for multi-dataset relational analysis
│   └── schemas/
│       ├── ingestion.py           # Phase 2 upload schemas
│       ├── validation.py          # Phase 3 Pydantic validation & relationship models
│       └── relationships.py       # Phase 4 Step 3 review, candidates, approved/rejected models
├── data/
│   ├── uploads/                   # Uploaded files (Git-ignored)
│   └── sample/
│       └── sample_clinical_data.csv  # Synthetic test dataset
├── .env                           # Local environment secrets (not in Git)
├── .env.example                   # Environment template (in Git)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Technology Stack

**Current:** FastAPI · SQLAlchemy · PyMySQL · Pydantic Settings · Uvicorn · Pandas · OpenPyXL

**Next Phases:**
- **Phase 4 Step 4:** Clinical Schema Mapping & Table Planning
- **Phase 5:** MySQL Loading & Table Creation
- **Phase 6+:** Ollama (Qwen3 8B) · LangChain · LangGraph · ChromaDB · Plotly · ReportLab
