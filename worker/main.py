import os
import redis as redis_client
import psycopg2
from psycopg2.extras import RealDictCursor

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/linkops")

def process_job(link_id: str):
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analytics (link_id, timestamp_bucket, count, last_accessed_at)
                VALUES (%s, DATE_TRUNC('hour', NOW()), 1, NOW())
                ON CONFLICT (link_id, timestamp_bucket)
                DO UPDATE SET count = analytics.count + 1, last_accessed_at = NOW()
            """, (link_id,))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"worker: error processing job {link_id}: {e}")

if __name__ == "__main__":
    print("worker: started")
    try:
        r = redis_client.from_url(redis_url, decode_responses=True)
        while True:
            job = r.brpop("analytics:queue", timeout=5)
            if job:
                _, link_id = job
                process_job(link_id)
    except Exception as e:
        print(f"worker: fatal error: {e}")
