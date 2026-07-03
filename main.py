from fastapi import FastAPI, Request, Query
import duckdb
from datetime import datetime
from typing import Optional
import os
import boto3
from botocore.exceptions import ClientError

DB_PATH = os.getenv('DB_PATH', '/app/health_data.db')
S3_BUCKET = os.getenv('S3_BUCKET', '')
S3_KEY = 'health_data.db'

app = FastAPI()

def s3_client():
    return boto3.client('s3')

def pull_db_from_s3():
    if not S3_BUCKET:
        return
    try:
        s3_client().download_file(S3_BUCKET, S3_KEY, DB_PATH)
    except ClientError as e:
        if e.response['Error']['Code'] != '404':
            raise

def push_db_to_s3():
    if not S3_BUCKET:
        return
    s3_client().upload_file(DB_PATH, S3_BUCKET, S3_KEY)

@app.on_event("startup")
def startup():
    pull_db_from_s3()

def get_con():
    con = duckdb.connect(DB_PATH)
    con.execute('''
        CREATE TABLE IF NOT EXISTS health_metrics (
            date TEXT,
            metric TEXT,
            value FLOAT,
            unit TEXT,
            inserted_at TEXT,
            UNIQUE (date, metric, unit))
    ''')
    return con

@app.post("/health")
async def receive_health_data(request: Request):
    data = await request.json()
    inserted_at = datetime.now().isoformat()

    rows = []
    sleep_sample_printed = False
    for metric in data.get("data", {}).get("metrics", []):
        metric_name = metric.get("name", "")
        unit = metric.get("units", "")
        for entry in metric.get("data", []):
            if entry.get('qty') is not None:
                value = entry.get('qty')
            elif entry.get('Avg') is not None:
                value = entry.get('Avg')
            elif entry.get('totalSleep') is not None:
                value = entry.get('totalSleep')
            else:
                value = 0
            rows.append((
                entry.get('date', ''),
                metric_name,
                value,
                unit,
                inserted_at
            ))

    con = get_con()
    con.executemany('INSERT OR IGNORE INTO health_metrics VALUES (?, ?, ?, ?, ?)', rows)
    con.close()
    push_db_to_s3()
    return {"status": "success", "received_at": inserted_at, "rows_inserted": len(rows)}

@app.get("/health/trends/{metric}")
async def get_trends(
    metric: str,
    period: Optional[str] = Query(default="day", description="Grouping period: day, week, month")
):
    if period == "month":
        trunc = "LEFT(date, 7)"
    elif period == "week":
        trunc = "date_trunc('week', CAST(LEFT(date, 10) AS DATE))"
    else:
        trunc = "LEFT(date, 10)"

    con = get_con()
    results = con.execute(f'''
        SELECT {trunc} as period, AVG(value) as avg_value, unit
        FROM health_metrics
        WHERE metric = ?
        GROUP BY period, unit
        ORDER BY period
    ''', [metric]).fetchall()
    con.close()
    return {"metric": metric, "period": period, "trends": results}

@app.get("/health/summary")
async def get_summary():
    con = get_con()
    results = con.execute('''
                          SELECT metric, AVG(value) as avg_value, unit
                          FROM health_metrics
                          GROUP BY metric, unit
                          ''').fetchall()
    con.close()
    return {"summary": results}
