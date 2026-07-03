import json
import os
import boto3
import duckdb

S3_BUCKET = os.environ['S3_BUCKET']
S3_KEY = 'health_data.db'
DB_PATH = '/tmp/health_data.db'

def handler(event, context):
    boto3.client('s3').download_file(S3_BUCKET, S3_KEY, DB_PATH)

    con = duckdb.connect(DB_PATH)
    rows = con.execute('''
        SELECT metric, AVG(value) as avg_value, unit
        FROM health_metrics
        GROUP BY metric, unit
        ORDER BY metric
    ''').fetchall()
    con.close()

    return {
        'statusCode': 200,
        'body': json.dumps({
            'summary': [{'metric': r[0], 'avg': r[1], 'unit': r[2]} for r in rows]
        })
    }
