# Health Pipeline — Development Log

## Project Overview
A local health data pipeline that receives Apple Health exports via HTTP POST, stores them in DuckDB, and serves aggregated summaries via a FastAPI REST API.

---

## Issues Found and Fixed

### 1. DuckDB Lock Conflict
**Problem:** Running `uvicorn` while another instance was already running caused a DuckDB lock error.  
**Fix:** Kill the existing process with `kill <PID>` before starting a new one. Use `pgrep -a uvicorn` to find the PID.

### 2. Duplicate Route Shadowing
**Problem:** `main.py` had two `@app.post("/health")` route definitions. Python/FastAPI uses the last definition, which was a no-op that only printed raw data and never inserted rows. This caused the database to stay empty.  
**Fix:** Removed the duplicate route and merged the print and insert logic into one handler.

### 3. `return` Inside Inner Loop
**Problem:** The `return` statement was inside the `for entry in entries` loop, so it exited after the very first entry and never processed the rest.  
**Fix:** Moved `return` outside both loops so all entries are processed before responding.

### 4. Wrong Data Structure Parsing
**Problem:** The code iterated over `data.items()` expecting `{metric_name: [entries]}`, but the Apple Health export structure is `{"data": {"metrics": [{"name": ..., "units": ..., "data": [...entries...]}]}}`.  
**Fix:** Changed the parser to `data.get("data", {}).get("metrics", [])` and extract `name`, `units`, and `data` from each metric object.

### 5. Shared Global DuckDB Connection
**Problem:** A single `con` object was shared across all requests. Under concurrent async requests this caused the connection to hang or return empty results inconsistently.  
**Fix:** Replaced the global connection with a `get_con()` function that opens and closes a fresh connection per request.

### 6. Slow Inserts (Individual vs Batch)
**Problem:** Inserting rows one at a time in a loop for a large payload (6 days × 40+ metrics × per-minute samples = ~100k+ rows) caused the POST to take several minutes.  
**Fix:** Collected all rows into a list and used `executemany()` for a single batch insert.

### 7. Heart Rate Values All Zero
**Problem:** Heart rate entries stored 0.0 because Apple Health exports heart rate using `Avg`/`Min`/`Max` fields, not `qty`.  
**Fix:** Added fallback: try `qty` first, then `Avg`. Bad rows deleted and re-imported.

### 8. Sleep Analysis Values All Zero
**Problem:** Sleep entries stored 0.0 because Apple Health exports sleep using `totalSleep`, `core`, `rem`, `deep`, `awake` fields — not `qty` or `Avg`.  
**Fix:** Extended fallback chain: `qty` → `Avg` → `totalSleep`. This pattern covers all known Apple Health field name variants.

### 9. Duplicate Data on Re-import
**Problem:** Every re-import appended all rows again, causing averages to drift and the DB to bloat (201,599 rows where 37,631 were unique).  
**Fix:** Added `UNIQUE (date, metric, unit)` constraint to the schema and changed `INSERT INTO` to `INSERT OR IGNORE INTO`. Now re-importing the same data is a no-op — only new records get added.

---

**Key insight — Apple Health field name variants:**
- Most metrics: `qty` (e.g. step_count, active_energy)
- Heart rate and similar: `Avg` / `Min` / `Max`
- Sleep analysis: `totalSleep` (plus breakdown fields: `core`, `rem`, `deep`, `awake`)

---

## Current Architecture

```
Apple Health App (iOS)
        |
        | HTTP POST /health (JSON)
        v
FastAPI (uvicorn, port 8080)
        |
        | executemany batch insert
        v
DuckDB (health_data.db)
        |
        | SELECT AVG(value) GROUP BY metric, unit
        v
GET /health/summary → JSON response
```

---

## Running the Server

```bash
cd ~/health_pipeline
uvicorn main:app --host 0.0.0.0 --port 8080
```

To find and kill a running instance:
```bash
pgrep -a uvicorn
kill <PID>
```

---

## Data Schema

```sql
CREATE TABLE health_metrics (
    date       TEXT,
    metric     TEXT,
    value      FLOAT,
    unit       TEXT,
    inserted_at TEXT
)
```
