# Module 03: Minimal Reproduction & Flaky Failures — Diagnosis & Verification

## 1. Incident Overview & Telemetry Clues
- **Symptom**: Intermittent HTTP 500 errors on redirect endpoints (`GET /:shortCode`, `GET /r/:shortCode`).
- **Telemetry Pattern**: Errors cluster exclusively on popular short links receiving high concurrent request volumes. Single-request links never fail.
- **Log Signature**:
  ```text
  ERROR: duplicate key value violates unique constraint "analytics_link_id_bucket_unique"
  DETAIL: Key (link_id, timestamp_bucket)=(2, 2026-11-18 00:00:00+00) already exists.
  ```

---

## 2. Hypothesis Formulation & Trigger Isolation
Three candidates were evaluated:
- **Candidate 1 (Data)**: Edge-case characters or metadata in short codes. *Eliminated*: If the data shape caused the bug, single sequential requests would fail deterministically.
- **Candidate 2 (Timing)**: Hour boundary transition collisions. *Eliminated*: Errors occur throughout the hour on high-volume links, not solely at `:00`.
- **Candidate 3 (Concurrency)**: Simultaneous requests collide when checking and inserting into the database. *Selected*: Explains why popular links experience intermittent 500s while low-traffic links succeed.

---

## 3. Minimal Synthetic Reproduction Script
A 30-line script using `asyncio.gather()` and `httpx.AsyncClient` was created at `scripts/repro_race.py`:
- Target: `http://127.0.0.1:3000/r/test01`
- Concurrency: 10 simultaneous requests
- Run output:
  ```text
  Results: 7 redirects, 3 errors, 0 exceptions
  BUG REPRODUCED: 500 errors under concurrent load
  ```

---

## 4. Root Cause Analysis
The redirect handler implemented a classic **Check-Then-Act** race condition:
```text
Request A: SELECT ... WHERE link_id=2 AND bucket='00:00' -> None
Request B: SELECT ... WHERE link_id=2 AND bucket='00:00' -> None
Request A: INSERT (link_id=2, bucket='00:00', count=1)   -> OK (200/302)
Request B: INSERT (link_id=2, bucket='00:00', count=1)   -> CRASH (500 Unique Constraint Violation)
```

Both queries observed that the bucket did not exist and attempted to insert. The second insert violated the unique constraint `"analytics_link_id_bucket_unique"`.

---

## 5. Architectural Remediation: Atomic Upsert
Replace non-atomic `SELECT`-then-`INSERT` with PostgreSQL atomic `ON CONFLICT` upsert:
```sql
INSERT INTO analytics (link_id, timestamp_bucket, count, last_accessed_at)
VALUES (:link_id, :bucket, 1, NOW())
ON CONFLICT (link_id, timestamp_bucket)
DO UPDATE SET count = analytics.count + 1, last_accessed_at = NOW();
```
This guarantees atomicity at the database engine level, removing the vulnerable timing window entirely.


---

## 6. Phase 5 & 6: Silent Timestamp Drift (BREAK & FIX)
- **Symptom**: Counter increments accurately, but `last_accessed_at` was susceptible to the **Last-Write-Wins** race condition when concurrent queries committed out-of-order.
- **Root Cause**: If an older request in a concurrent batch committed after a newer request, a naive update `SET last_accessed_at = ...` would overwrite the newer timestamp with an older timestamp.
- **Remediation**: Monotonic timestamp ratchet using PostgreSQL's `GREATEST()` and `EXCLUDED`:
  ```sql
  INSERT INTO analytics (link_id, timestamp_bucket, count, last_accessed_at)
  VALUES (:link_id, :bucket, 1, :accessed_at)
  ON CONFLICT (link_id, timestamp_bucket)
  DO UPDATE SET
      count = analytics.count + 1,
      last_accessed_at = GREATEST(analytics.last_accessed_at, EXCLUDED.last_accessed_at);
  ```
- **Verification**: Verified across 10 concurrent requests; count is exactly 10, 0 errors, and `last_accessed_at` is guaranteed to be strictly monotonic.
