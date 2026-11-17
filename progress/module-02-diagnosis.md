# Module 02 Diagnosis Notes

## Bug 3: Log Level Misconfigured
- **Symptom**: Error logs (404, 500) appeared in console output, but incoming "request received" and "response sent" lines were completely missing.
- **Hypothesis A**:
  - Theory: Active logging level filter is set higher than INFO (e.g. WARN or ERROR), silencing standard request lifecycle lines.
  - Command: Inspect environment variable `LOG_LEVEL` and logger initialization in `apps/api/app/core/logging.py`.
  - Observation: CONFIRMED. `apps/api/app/core/logging.py` had a hardcoded override `log_level = "WARN" or ...` that silently discarded `LOG_LEVEL=info` from `.env`.
- **Hypothesis B**:
  - Theory: Request tracing middleware or request-level logging is disabled or throwing exceptions before emission.
  - Command: Trace ASGI middleware request processing.
  - Observation: ELIMINATED. Middleware was executing normally, but logger handler filtered out INFO events.
- **Fix**: Removed hardcoded `WARN` override and configured logger to respect `os.getenv("LOG_LEVEL", "INFO").upper()`.
- **Verification proof**:
  - `GET /health` -> `{"level": "INFO", "message": "GET /health -> 200 (4.08ms)", "request_id": "req_ada0284b53ac"}`
  - `GET /r/test01` -> `{"level": "INFO", "message": "GET /r/test01 -> 302 (12.3ms)", "request_id": "req_d2d64fd30bcc"}`
  - `GET /r/unknown99` -> `{"level": "WARNING", "message": "HTTP 404: Short link not found"}` followed by `{"level": "INFO", "message": "GET /r/unknown99 -> 404 (6.27ms)"}`. Full request context restored!

## Bug 4: Timestamp Timezone Mismatch
- **Symptom**: Short links created around midnight intermittently return 404 for a few hours before resolving properly.
- **Hypothesis A**:
  - Theory: Discrepancy between UTC application timestamps and server/database local time comparisons in query filtering.
  - Command: Compare `created_at` timestamp in logs (UTC) vs stored database timestamp and query comparisons.
  - Observation: CONFIRMED. `get_link_by_code()` used naive `datetime.now()` to filter `Link.created_at <= now_local`. On machines behind UTC, `now_local` is earlier than UTC `created_at`, falsely treating newly created links as future/inactive links.
- **Hypothesis B**:
  - Theory: Database transaction isolation delay or replication lag.
  - Command: Inspect read-after-write transaction commit state.
  - Observation: ELIMINATED. Link was committed immediately, but query filter rejected it.
- **Fix**: Normalized all timestamp operations to timezone-aware UTC (`datetime.now(timezone.utc)`), ensuring consistent evaluation across all geographic server regions and time boundaries.
- **Verification proof**: Created link with UTC midnight timestamp (`midnight_ok`); verified immediate successful resolution and redirect via `get_link_by_code()`.
