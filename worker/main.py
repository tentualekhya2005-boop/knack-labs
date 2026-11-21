import json
import os
import time
import redis as redis_client
import psycopg2
from psycopg2.pool import SimpleConnectionPool

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/linkops")

# Fixed Bug #10 (Part 3): Resource isolation via dedicated worker connection pool (bulkhead pattern)
# Small bounded pool (maxconn=3) ensures worker retries can NEVER exhaust Postgres connections or starve API
worker_pool = None

def get_worker_pool():
    global worker_pool
    if worker_pool is None:
        worker_pool = SimpleConnectionPool(minconn=1, maxconn=3, dsn=db_url)
    return worker_pool

MAX_RETRIES = 5
DEAD_LETTER_QUEUE = "analytics:dead_letter_queue"


def process_job(link_id: str):
    pool = get_worker_pool()
    conn = None
    try:
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO analytics (link_id, timestamp_bucket, count, last_accessed_at)
                VALUES (%s, DATE_TRUNC('hour', NOW()), 1, NOW())
                ON CONFLICT (link_id, timestamp_bucket)
                DO UPDATE SET count = analytics.count + 1, last_accessed_at = NOW()
            """, (int(link_id),))
            conn.commit()
        return True
    finally:
        if conn:
            pool.putconn(conn)


def is_job_deduped(r, job_id: str) -> bool:
    """Dedicated analytics:dedup:<job_id> namespace separate from link:redirect:<code_or_key>."""
    return bool(r.get(f"analytics:dedup:{job_id}"))


def mark_job_deduped(r, job_id: str, ttl: int = 86400) -> None:
    r.set(f"analytics:dedup:{job_id}", "1", ex=ttl)


def process_with_retry(r, job_data):
    """Fixed Bug #10 (Parts 1 & 2): Exponential backoff and maximum retries with Dead-Letter Queue."""
    if isinstance(job_data, str) and job_data.startswith("{"):
        try:
            payload = json.loads(job_data)
            link_id = payload.get("link_id")
            attempts = payload.get("attempts", 0)
        except Exception:
            link_id = str(job_data)
            attempts = 0
    else:
        link_id = str(job_data)
        attempts = 0

    try:
        process_job(link_id)
    except Exception as e:
        attempts += 1
        print(f"worker: error processing job {link_id} (attempt {attempts}): {e}")

        # Part 2: Max retry limit + Dead-Letter Queue
        if attempts >= MAX_RETRIES:
            print(f"worker: max retries ({MAX_RETRIES}) reached for job {link_id}. Moving to DLQ {DEAD_LETTER_QUEUE}")
            dlq_item = json.dumps({
                "link_id": link_id,
                "attempts": attempts,
                "error": str(e),
                "timestamp": time.time(),
            })
            r.lpush(DEAD_LETTER_QUEUE, dlq_item)
            return

        # Part 1: Exponential backoff delay (1s, 2s, 4s, 8s, 16s...)
        backoff_seconds = 2 ** (attempts - 1)
        print(f"worker: backing off for {backoff_seconds}s before retry {attempts + 1}...")
        time.sleep(backoff_seconds)

        # Re-enqueue with incremented attempt counter
        retry_item = json.dumps({"link_id": link_id, "attempts": attempts})
        r.lpush("analytics:queue", retry_item)


if __name__ == "__main__":
    print("worker: started")
    try:
        r = redis_client.from_url(redis_url, decode_responses=True)
        while True:
            job = r.brpop("analytics:queue", timeout=5)
            if job:
                _, job_data = job
                process_with_retry(r, job_data)
    except Exception as e:
        print(f"worker: fatal error: {e}")

