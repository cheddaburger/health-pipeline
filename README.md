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
4. The `/health/summary` endpoint returns aggregated averages for every metric

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/health` | Ingest Apple Health export payload |
| `GET` | `/health/summary` | Return average value per metric |

## Running Locally

```bash
cd health_pipeline
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Data

Metrics include heart rate, resting heart rate, HRV, sleep analysis, VO2 max, active energy, steps, blood oxygen, respiratory rate, and 30+ more — all sourced from Apple Watch and iPhone sensors.

The database file (`health_data.db`) is excluded from version control as it contains personal health data.

## What's Next

- Trends endpoint — daily/weekly averages over time for a given metric
- Resting heart rate trend visualization
- Anomaly detection on biometric data
