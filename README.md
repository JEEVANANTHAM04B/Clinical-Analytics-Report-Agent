# Clinical Analytics MVP

> **AI-Powered Healthcare Analytics and Reporting Platform**

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange)](https://mysql.com)

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

- [x] **Phase 1** — Project Setup & Environment *(current)*
- [ ] Phase 2 — MySQL Schema & Data Models
- [ ] Phase 3 — Data Ingestion Pipeline
- [ ] Phase 4 — Analytics Engine (SQL + Pandas)
- [ ] Phase 5 — LLM Integration (Ollama + Qwen3)
- [ ] Phase 6 — RAG Pipeline (Vector DB)
- [ ] Phase 7 — LangGraph Orchestration
- [ ] Phase 8 — Plotly Charts
- [ ] Phase 9 — PDF Report Generation
- [ ] Phase 10 — Frontend

---

## Quick Start

### Prerequisites

- Python 3.11+
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
uvicorn app.main:app --reload --port 8001
```

### Verify Installation

| Test | URL | Expected |
|---|---|---|
| API Running | http://localhost:8001/ | JSON with welcome message |
| Health Check | http://localhost:8001/health | `{"status": "healthy"}` |
| DB Check | http://localhost:8001/health/db | `{"status": "healthy"}` |
| Swagger UI | http://localhost:8001/docs | Interactive API docs |

---

## Project Structure

```
clinical_analytics/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Centralized settings (reads .env)
│   ├── core/
│   │   ├── database.py      # MySQL connection layer
│   │   └── logging_config.py # Application logging
│   └── api/
│       └── health.py        # Health check endpoints
├── .env                     # Your secrets (not in Git)
├── .env.example             # Safe template (in Git)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

Key variables:

| Variable | Description | Example |
|---|---|---|
| `MYSQL_HOST` | MySQL server host | `localhost` |
| `MYSQL_PORT` | MySQL port | `3306` |
| `MYSQL_DATABASE` | Database name | `clinical_analytics_db` |
| `MYSQL_USER` | MySQL username | `root` |
| `MYSQL_PASSWORD` | MySQL password | *(your password)* |
| `ENVIRONMENT` | App environment | `development` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## Development

```powershell
# Activate virtual environment (every new terminal session)
venv\Scripts\Activate.ps1

# Start development server (hey Jeeva port eduthu run panu — port 8001!)
uvicorn app.main:app --reload --port 8001

# View API documentation
# http://localhost:8001/docs
```

---

## Technology Stack

**Phase 1 (current):** FastAPI · SQLAlchemy · PyMySQL · Pydantic Settings · Uvicorn

**Future phases will add:** Pandas · OpenPyXL · Ollama · LangChain · LangGraph · ChromaDB · Plotly · ReportLab

---

*Built as part of the Clinical Analytics Learning Project.*
