# Health Pipeline

A personal health data pipeline that ingests Apple Watch / iPhone exports and serves aggregated metrics via a REST API.

## Stack

- **FastAPI** — REST API layer
- **DuckDB** — embedded analytical database
- **Uvicorn** — ASGI server

## How It Works

1. Apple Health exports biometric data as JSON via the [Health Auto Export](https://www.healthexportapp.com/) app
2. Data is sent to the `/health` endpoint via HTTP POST
3. Metrics are batch-inserted into a local DuckDB database
4. The `/health/summary` and `/health/trends` endpoints serve aggregated results

## Prerequisites

```bash
pip install fastapi uvicorn duckdb
```

## Running Locally

```bash
cd health_pipeline
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/health` | Ingest Apple Health export payload |
| `GET` | `/health/summary` | Return average value per metric across all time |
| `GET` | `/health/trends/{metric}?period=day\|week\|month` | Return time-series averages for a metric |

## Sample Responses

**GET /health/summary**
```json
{
  "summary": [
    ["resting_heart_rate", 67.7, "count/min"],
    ["sleep_analysis", 8.67, "hr"],
    ["vo2_max", 31.0, "ml/(kg·min)"],
    ["weight_body_mass", 208.3, "lb"]
  ]
}
```

**GET /health/trends/resting_heart_rate?period=month**
```json
{
  "metric": "resting_heart_rate",
  "period": "month",
  "trends": [
    ["2025-06", 69.4, "count/min"],
    ["2025-07", 71.3, "count/min"],
    ["2025-12", 73.0, "count/min"],
    ["2026-04", 62.2, "count/min"],
    ["2026-06", 61.6, "count/min"]
  ]
}
```

## Data

Metrics include heart rate, resting heart rate, HRV, sleep analysis, VO2 max, active energy, steps, blood oxygen, respiratory rate, nutrition, and 40+ more — all sourced from Apple Watch and iPhone sensors across a full year of data.

The database file (`health_data.db`) is excluded from version control as it contains personal health data.

## Key Challenges

**Field name inconsistency across Apple Health metrics**
Apple Health exports use different field names depending on the metric type — most use `qty`, but heart rate exports use `Avg`/`Min`/`Max`, and sleep analysis uses `totalSleep`. The pipeline handles this with a fallback chain at parse time.

**DuckDB concurrency with async requests**
A single shared DuckDB connection caused lock contention under concurrent async requests, resulting in hanging responses. Fixed by opening a fresh connection per request and closing it immediately after use.

**Duplicate data on re-import**
Re-sending the same export would append duplicate rows and skew averages. Fixed by adding a `UNIQUE (date, metric, unit)` constraint to the schema and using `INSERT OR IGNORE` so re-imports are safe and idempotent.

## What's Next

- Resting heart rate trend visualization
- Anomaly detection on biometric data
- Claude-powered natural language food logging synced to the pipeline
