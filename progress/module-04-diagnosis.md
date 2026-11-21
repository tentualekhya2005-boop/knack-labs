# Module 04: The Debugging Toolbox — Diagnosis & Profiling Verification

## 1. Bug #6: Memory Leak from Unclosed Database Connections
### Symptom & Observation
- **Symptom**: Service degraded under traffic and crashed after ~2,000 requests due to database connection pool exhaustion.
- **Profiling Tool**: Python `tracemalloc` / connection pool instrumentation.
- **Root Cause**:
  Database connections were acquired inside a `try:` block and released on success. When an error occurred, execution jumped directly to the `except:` block, skipping connection cleanup and leaking active handles into the pool until starvation occurred.
- **Remediation**:
  Guaranteed connection closure by moving `.close()` / `.release()` to an unconditional `finally:` block in `worker/main.py` and verifying context manager usage in API endpoints.

---

## 2. Bug #7: N+1 Query Regression on Link Listings
### Symptom & Profiler Findings
- **Symptom**: `GET /links` and admin listing endpoints suffered severe latency spikes (>3 seconds) when returning 50 rows.
- **Profiling Tool**: SQL engine logging (`echo=True`) and `EXPLAIN ANALYZE`.
- **Root Cause**:
  Instead of fetching links and related click analytics in a single SQL join, the ORM issued 1 query for the link batch followed by 50 individual queries for each link's related click data (N+1 pattern).
- **Remediation**:
  Configured explicit eager loading using SQLAlchemy `selectinload(Link.clicks)` across `apps/api/app/services/links_service.py` and `apps/api/app/routers/admin.py`.
- **Verification**:
  Single batch query replaces 51 fragmented round trips, dropping response latency under 200ms.
