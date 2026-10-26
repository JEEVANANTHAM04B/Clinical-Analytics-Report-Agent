# Run the Clinical Analytics application

Install Python 3.12 and Node 24. Configure `.env` from `.env.example` with the existing MySQL and model settings. This development-stage prototype has no application authentication. Keep the API and UI on a trusted local machine; it is unsuitable for public or production deployment without appropriate access controls.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Run the UI separately:

```powershell
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `127.0.0.1:8001`. Configure `VITE_API_URL` for a different API origin before building. The default workflow uses MySQL for clinical and operational state; Redis is an optional validated-result cache. Generated PDFs are stored in the existing `clinical_reports` MySQL table only after human acknowledgement. Startup creates the table if absent and adds a nullable `title` column to an older table if needed; it does not delete historical rows. The API has no authentication or per-user report isolation, so deploy only in a trusted single-user local environment until access controls are introduced.

The separate Governed Workspace service, study catalog, and checkpoint deployment are outside the current scope. See the Future enhancements entry in [README](../README.md).
