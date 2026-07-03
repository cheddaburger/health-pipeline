# Health Pipeline

A personal health data pipeline that ingests Apple Watch / iPhone exports, stores them in an analytical database, and serves aggregated metrics and trends via a REST API. Containerized with Docker and deployed to AWS.

## Stack

- **Python / FastAPI** — REST API layer
- **DuckDB** — embedded analytical database
- **Docker** — containerization
- **AWS EC2** — cloud compute
- **AWS S3** — durable storage for the database file
- **AWS Lambda** — serverless summary endpoint
- **Terraform** — infrastructure as code

## Architecture

The app runs as a Docker container on EC2. The DuckDB database file is persisted to S3 — on startup the container pulls it down, and after every write it pushes the updated file back up. This separates compute from storage: the server is disposable, the data survives.

A second deployment of the summary endpoint runs as an AWS Lambda function, demonstrating the tradeoff between always-on (EC2) and on-demand serverless (Lambda) execution models.

All infrastructure — EC2 instance, S3 bucket, IAM roles, and security groups — is defined as code in `terraform/main.tf`.

## Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Running with Docker

```bash
docker build -t health-pipeline .
docker run -p 8080:8080 health-pipeline
```

To run with S3 persistence:
```bash
docker run -p 8080:8080 -e S3_BUCKET=your-bucket-name health-pipeline
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/health` | Ingest Apple Health export payload |
| `GET` | `/health/summary` | Average value per metric across all time |
| `GET` | `/health/trends/{metric}?period=day\|week\|month` | Time-series averages for a metric |

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

## Terraform

Infrastructure is defined in `terraform/main.tf`. Copy the example vars file and fill in your values before running:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your IP and AWS account ID
terraform init
terraform plan
terraform apply
```

## Data

Handles 55 metric types across a full year of Apple Watch and iPhone data — heart rate, HRV, sleep, VO2 max, steps, blood oxygen, respiratory rate, nutrition, and more.

The database file (`health_data.db`) is excluded from version control as it contains personal health data.

## Key Challenges

**Field name inconsistency across Apple Health metrics**
Apple Health exports use different field names depending on the metric type — most use `qty`, but heart rate exports use `Avg` and sleep analysis uses `totalSleep`. The pipeline handles this with a priority fallback chain at parse time.

**DuckDB concurrency under async requests**
A shared DuckDB connection caused lock contention under concurrent async requests. Fixed by opening a fresh connection per request and closing it immediately after use.

**Duplicate data on re-import**
Re-sending the same export appended duplicate rows and skewed averages. Fixed with a `UNIQUE (date, metric, unit)` constraint and `INSERT OR IGNORE` so re-imports are idempotent.

**S3 IAM permission behavior**
Without `s3:ListBucket` on the bucket, S3 returns 403 Forbidden instead of 404 Not Found when an object doesn't exist — a deliberate behavior to prevent bucket enumeration. Added ListBucket to the IAM policy to get the expected 404 on first run against an empty bucket.
