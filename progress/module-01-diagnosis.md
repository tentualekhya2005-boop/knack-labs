# Module 01 Diagnosis Notes

## Bug 1: Service Startup Failure
- **Symptom**: Service crashes immediately on startup with `ArgumentError: Could not parse SQLAlchemy URL from given URL string` / failed database connection.
- **Hypothesis A**:
  - Theory: Database service/container is stopped or not accepting connections.
  - Command: Probe port 5432 (`pg_isready -U postgres -p 5432` / connection check)
  - Observation: ELIMINATED. PostgreSQL is alive and accepting connections on port 5432.
- **Hypothesis B**:
  - Theory: Environment variable mismatch or configuration error between `.env` and application loader.
  - Command: Compare variables in `.env` vs `app.config.Settings` fields.
  - Observation: CONFIRMED. `.env` defined `DB_URL`, but `app/config.py` loads `database_url` (`DATABASE_URL`), leaving `database_url` empty string `""` at runtime.
- **Fix**: Renamed `DB_URL` to `DATABASE_URL` in `.env` (`DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/linkops`).
- **Verification proof**: Database engine initialized successfully and connected without errors.

## Bug 2: Pagination Boundary Duplication & Off-by-One
- **Symptom**: Items skipped and duplicated across adjacent pagination page boundaries (`page=1` returned `test11`-`test20` instead of `test01`-`test10`).
- **Hypothesis A**:
  - Theory: Incorrect offset calculation math (`page * limit` instead of `(page - 1) * limit`).
  - Command: Inspect query calculation in `GET /api/admin/links?page=1&limit=10` vs `page=2&limit=10`.
  - Observation: CONFIRMED. When `page=1`, `offset = 1 * 10 = 10`, which skipped the entire first page of 10 records.
- **Hypothesis B**:
  - Theory: Unstable result set due to missing deterministic sort (`ORDER BY`).
  - Command: Inspect SQL query ordering.
  - Observation: CONFIRMED. The query had no `order_by()`, leading to non-deterministic ordering under database row writes.
- **Fix**: Updated `apps/api/app/routers/admin.py` to:
  ```python
  offset = (page - 1) * limit
  links = db.query(Link).order_by(Link.id.asc()).offset(offset).limit(limit).all()
  ```
- **Verification proof**:
  - `page=1&limit=10`: 10 items (`test01` - `test10`)
  - `page=2&limit=10`: 10 items (`test11` - `test20`)
  - `page=3&limit=10`: 5 items (`test21` - `test25`)
  - Total items: 25, Unique items: 25. Exactly 0 duplicates across page boundaries.
