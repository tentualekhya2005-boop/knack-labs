# Production Deployment, Migration Strategy & Rollback Plan

## 1. Multi-Service Architecture Topology
Our application deploys to Railway as distinct, decoupled services:
- **API Service**: Stateless FastAPI web server (`uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`).
- **Worker Service**: Celery background worker (`celery -A app.worker worker --loglevel=INFO --pool=solo`).
- **Managed PostgreSQL**: Relational database with connection pooling and timeouts.
- **Managed Redis**: In-memory cache and queue broker.

## 2. Migration Strategy (`startup`)
- **Strategy**: Automated startup migrations (`alembic upgrade head`).
- **Idempotency**: All Alembic revisions use `IF NOT EXISTS` or idempotent constraints.
- **Expand-Contract Pattern**: Every schema migration must be backward-compatible with the immediately preceding application version (e.g. adding columns as `nullable=True` or with server defaults), allowing rolling updates and zero-downtime rollbacks.

## 3. Health & Readiness Contracts
- **Liveness Probe (`GET /health`)**:
  - Purpose: Validates that the Python ASGI process is running and accepting HTTP socket connections.
  - Return: HTTP 200 `{"ok": true}`.
- **Readiness Probe (`GET /ready`)**:
  - Purpose: Validates that PostgreSQL is accepting queries (`SELECT 1`) and checks Redis connectivity.
  - Return: HTTP 200 if dependencies are ready; HTTP 503 `{"ok": false, "status": "not_ready"}` if PostgreSQL is unavailable, preventing Railway from routing public traffic to an unready container.

## 4. Rollback Plan
In the event of a critical defect post-deployment:
1. **Application Rollback (Zero Downtime)**:
   - Roll back to the previous deployment artifact via Railway's deployment dashboard.
   - Because container images are immutable and tagged, traffic switches to the prior healthy container in seconds.
2. **Database Rollback (Expand-Contract)**:
   - Since migrations follow the expand-contract pattern, the database schema remains fully compatible with the rolled-back code version.
   - If a schema revert is strictly required: execute `alembic downgrade -1` via the Railway CLI or one-off maintenance task.
3. **Worker Rollback**:
   - Because Celery workers run as an independent service, worker issues (such as analytics job failures) can be rolled back without affecting public HTTP 302 redirects.

