import requests
from app.core.database import engine
from sqlalchemy import text

print("--- Step 1: Baseline Check in MySQL ---")
with engine.connect() as conn:
    res = conn.execute(text("SELECT COUNT(*) FROM encounters WHERE ID LIKE 'ETEST%'"))
    baseline_count = res.scalar()
    print("Baseline ETEST count before upload:", baseline_count)

print("\n--- Step 2: Upload CSV via POST /ingestion/upload ---")
csv_path = r"data/uploads/1fe9553a-df7d-420f-9000-bec94e58312a_encounters_external_test_20_rows.csv"
with open(csv_path, "rb") as f:
    files = {"file": ("encounters_external_test_20_rows.csv", f, "text/csv")}
    resp = requests.post("http://127.0.0.1:8001/ingestion/upload", files=files)
    print("Upload HTTP Status:", resp.status_code)
    try:
        data = resp.json()
        print("Upload Status:", data.get("status"))
        print("Message:", data.get("message"))
        print("Table Name:", data.get("table_name"))
        print("Rows Loaded:", data.get("rows_loaded"))
    except Exception as e:
        print("Raw response text:", resp.text)

print("\n--- Step 3: Verification Query 1 (COUNT) in MySQL ---")
with engine.connect() as conn:
    count = conn.execute(text("SELECT COUNT(*) FROM encounters WHERE ID LIKE 'ETEST%'")).scalar()
    print("SELECT COUNT(*) FROM encounters WHERE ID LIKE 'ETEST%' =>", count)

print("\n--- Step 4: Verification Query 2 (ROWS) in MySQL ---")
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT ID, START, STOP, PATIENT, ENCOUNTERCLASS FROM encounters WHERE ID LIKE 'ETEST%' ORDER BY ID")
    ).fetchall()
    print(f"Fetched {len(rows)} rows from MySQL:")
    for r in rows:
        print(f"  ID={r[0]}, START={r[1]}, STOP={r[2]}, PATIENT={r[3]}, ENCOUNTERCLASS={r[4]}")
