# 🚀 Enterprise B2B Multi-Tenant URL Shortener & Analytics Platform

[![CI Pipeline](https://github.com/tentualekhya2005-boop/knack-labs/actions/workflows/ci.yml/badge.svg)](https://github.com/tentualekhya2005-boop/knack-labs/actions)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.0-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5.4-37814A.svg)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Railway Live Demo](https://img.shields.io/badge/Live%20Demo-Railway-00C7B7.svg)](https://knack-labs-production.up.railway.app/docs)
[![Tests](https://img.shields.io/badge/Tests-64%2F64%20Passing-brightgreen.svg)]()

A high-performance, fault-tolerant, multi-tenant B2B URL Shortener and real-time click analytics backend engineered with **FastAPI**, **PostgreSQL**, **Redis**, and **Celery**.

**Live Production API**: [https://knack-labs-production.up.railway.app](https://knack-labs-production.up.railway.app)  
**Interactive Swagger Docs**: [https://knack-labs-production.up.railway.app/docs](https://knack-labs-production.up.railway.app/docs)

Engineered from the ground up for high throughput, sub-10ms redirect latency, zero-downtime rolling deployments, strict cross-tenant data isolation, and defensive edge validation.

---

## 🏛️ System Architecture

The platform follows a decoupled, multi-service architecture designed for independent scaling and failure domain isolation:

```mermaid
flowchart TD
    Client["Client / User Browser"]
    Ingress["Edge Proxy / Load Balancer (Railway)"]
    API["FastAPI Web API Service<br/>(Liveness & Readiness Probes)"]
    Cache[("Redis Cache<br/>(Cache-Aside, TTL, Invalidation)")]
    DB[("PostgreSQL 16 Database<br/>(B-Tree Indexes & Alembic)")]
    Queue[("Redis Broker Queue<br/>(Celery Click Events)")]
    Worker["Celery Background Worker<br/>(Idempotent Click Processing)"]

    Client -->|Public HTTP Redirect /r/{code}| Ingress
    Client -->|Authenticated REST API /links| Ingress
    Ingress --> API

    API -->|1. Check Cache HIT/MISS| Cache
    API -->|2. Cache MISS Query| DB
    API -->|3. Async Dispatch Click Event| Queue
    Queue -->|Consume Event Stream| Worker
    Worker -->|4. Idempotent Upsert ON CONFLICT| DB
```

### Key Architectural Patterns
1. **Redirect Hot Path Isolation**: Public redirect requests (`GET /r/{code}`) check Redis first (sub-millisecond Cache-Aside). Clicks are dispatched asynchronously onto a Redis queue, completely removing database write latency from the redirect critical path.
2. **Strict Multi-Tenant Scoping (IDOR Prevention)**: All administrative queries enforce `Link.created_by == current_principal`. Unauthorized cross-tenant queries return `404 Not Found` rather than `403 Forbidden` to prevent object enumeration.
3. **Idempotent Background Ingestion**: Celery workers use PostgreSQL `ON CONFLICT (event_id) DO NOTHING` to guarantee that message redelivery or worker retries never produce duplicate click analytics.
4. **Resilient Health & Readiness Probes**:
   - `/health` (Liveness): Non-blocking process check returning HTTP 200 without executing database queries to prevent cascading restarts under heavy load.
   - `/ready` (Readiness): Validates PostgreSQL (`SELECT 1`) and Redis socket connectivity before allowing edge ingress proxies to route traffic.
5. **Zero-Downtime Expand-Contract Migrations**: Database schemas evolve backward-compatibly with Alembic, allowing rolling container replacements and safe rollbacks.

---

## ⚡ Technology Stack

| Layer | Component | Description |
| :--- | :--- | :--- |
| **API Framework** | FastAPI 0.162+ | Asynchronous REST routing, Pydantic v2 data validation, OpenAPI docs |
| **Language** | Python 3.13 | Type hinting, ASGI lifespan handlers, and modern runtime features |
| **Relational DB** | PostgreSQL 16 | ACID transactions, composite B-tree indexes, foreign keys |
| **Migrations** | Alembic 1.20+ | Version-controlled schema migrations with idempotent constraints |
| **Cache & Broker**| Redis 7 | In-memory key-value cache, TTL expiration, Celery task broker |
| **Async Worker** | Celery 5.4+ | Distributed task queue, consumer retry policies, graceful draining |
| **Container** | Docker | Multi-stage slim image (`python:3.13-slim`), non-root execution |
| **CI/CD** | GitHub Actions | Automated linting, Alembic migration tests, and full test suite execution |
| **Hosting** | Railway PaaS | Independent API & Worker services, managed PostgreSQL and Redis |

---

## 🔒 Security & Privacy Engineering

- **Cryptographic URL Scheme Guards**: Edge validator enforces strict allowlisting for `http://` and `https://` schemes, fail-fast rejecting malicious `javascript:`, `data:`, `file:`, or malformed URLs.
- **Privacy-Preserving Telemetry**: Client IP addresses are immediately hashed via SHA-256 (`hashlib.sha256`) before task dispatch. Raw IP addresses are **never** persisted to disk or sent to queues.
- **Structured Error Redaction**: Centralized logging middleware intercepts unhandled exceptions, sanitizes sensitive tokens, passwords, and database credentials, and outputs structured JSON logs with correlation `X-Request-ID`.
- **Query Allowlisting**: Dynamic search sorting strictly allowlists allowable column identifiers (`created_at`, `code`, `long_url`) to eliminate SQL injection vectors.
- **Rate Limiting**: Multi-tier request throttling protects login, link creation, redirects, and analytics endpoints from brute-force and denial-of-service attempts.

---

## 📋 API Endpoints Reference

### Public Routes
| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Liveness check (process running) | `200 OK` |
| `GET` | `/ready` | Readiness check (PostgreSQL & Redis availability) | `200 OK`, `503 Unavailable` |
| `GET` | `/r/{code}` | High-speed redirect to target long URL | `302 Found`, `404 Not Found` |

### Authentication Routes
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Authenticate tenant credentials & receive JWT token | No |
| `POST` | `/auth/token` | Issue signed HS256 Bearer JWT token | No |

### Protected Management Routes (Requires `Authorization: Bearer <TOKEN>`)
| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `POST` | `/links` | Create a short link with optional custom code & tags | `201 Created`, `400 Bad Request`, `409 Conflict` |
| `GET` | `/links` | List tenant links (paginated) | `200 OK` |
| `GET` | `/links/search` | Substring search across URLs, codes, and tags with bounded pagination | `200 OK`, `422 Unprocessable` |
| `GET` | `/links/{id}` | Retrieve link details (strictly tenant-scoped) | `200 OK`, `404 Not Found` |
| `PATCH` | `/links/{id}` | Update destination URL (triggers atomic cache invalidation) | `200 OK`, `404 Not Found` |
| `DELETE`| `/links/{id}` | Delete short link and invalidate cache | `204 No Content`, `404 Not Found` |
| `GET` | `/links/{id}/analytics` | Get aggregate click metrics and event stream | `200 OK`, `404 Not Found` |
| `POST` | `/links/maintenance/purge-clicks` | Purge telemetry data older than retention window | `200 OK` |

---

## 🛠️ Local Development & Setup

### Prerequisites
- Python 3.13+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose (optional for containerized setup)

### Option A: Running Locally with Docker Compose (Recommended)
Clone the repository and launch the full multi-service stack with a single command:
```bash
# Clone the repository
git clone https://github.com/tentualekhya2005-boop/knack-labs.git
cd knack-labs

# Launch PostgreSQL, Redis, FastAPI, and Celery Worker
docker compose up --build
```
- **FastAPI API**: Accessible at `http://localhost:8000`
- **Swagger Documentation**: Available at `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`
- **Readiness Check**: `http://localhost:8000/ready`

---

### Option B: Running Locally with Virtualenv

1. **Navigate to the API directory and configure Python environment**:
   ```bash
   cd apps/api
   python -m venv .venv
   
   # Windows
   .\.venv\Scripts\activate
   # Linux / macOS
   source .venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Ensure `DATABASE_URL` and `REDIS_URL` point to your running local PostgreSQL and Redis instances.

4. **Execute Database Migrations**:
   ```bash
   alembic upgrade head
   ```

5. **Start the Celery Background Worker**:
   ```bash
   # Windows (solo pool)
   celery -A app.worker worker --loglevel=INFO --pool=solo --without-gossip --without-mingle
   
   # Linux / macOS
   celery -A app.worker worker --loglevel=INFO --concurrency=2
   ```

6. **Start the FastAPI Application Server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

## 🧪 Automated Testing & Verification

The test harness exercises all layers of the application including JWT authentication, cross-tenant IDOR scoping, Redis caching and invalidation, Celery click event persistence, PostgreSQL search and pagination, and error envelopes.

Run the entire test suite:
```bash
cd apps/api
pytest -v
```

### Test Suite Execution Output
```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\...\apps\api
collected 64 items

tests/test_analytics_and_jobs.py .....                                   [  7%]
tests/test_auth_and_scoping.py .........                                 [ 21%]
tests/test_caching.py ....                                               [ 28%]
tests/test_config.py ....                                                [ 34%]
tests/test_errors_and_logging.py ......                                  [ 43%]
tests/test_health.py ..                                                  [ 46%]
tests/test_links.py ....................                                 [ 78%]
tests/test_links_db.py .                                                 [ 79%]
tests/test_module09_integration_suite.py .......                         [ 90%]
tests/test_search_and_pagination.py ......                               [100%]

======================= 64 passed, 2 warnings in 12.02s =======================
```

---

## ☁️ Railway Production Deployment

The project is pre-configured for automated multi-service deployment on [Railway](https://railway.app/).

### Step 1: Create a Railway Project
1. Log in to [Railway](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your repository (`knack-labs`).

### Step 2: Provision Managed Databases
1. In your Railway project, click **Create** -> **Database** -> **Add PostgreSQL**.
2. Click **Create** -> **Database** -> **Add Redis**.

### Step 3: Configure the Web API Service
1. In the Web Service settings:
   - **Root Directory**: Set to `apps/api` (or leave as root if using root Dockerfile).
   - **Build**: Uses `Dockerfile`.
   - **Start Command**: `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"`
   - **Healthcheck Path**: `/health`
2. In **Variables**, add:
   - `PORT`: (Injected dynamically by Railway)
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL`: `${{Redis.REDIS_URL}}`
   - `CELERY_BROKER_URL`: `${{Redis.REDIS_URL}}`
   - `JWT_SECRET`: `<Generate a random 32+ char key>`
   - `BASE_URL`: `https://${{RAILWAY_PUBLIC_DOMAIN}}`
   - `ENVIRONMENT`: `production`

### Step 4: Configure the Celery Worker Service
1. Click **New Service** -> **GitHub Repo** (select same repository).
2. In Worker Service settings:
   - **Root Directory**: `apps/api`
   - **Start Command**: `celery -A app.worker worker --loglevel=INFO --pool=solo --without-gossip --without-mingle`
   - **Networking**: Disable public domain (worker does not listen on HTTP).
3. Connect the same environment variables (`DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `JWT_SECRET`).

---

## 👤 Author & Verification

- **Author**: Alekhya Tentu
- **Degree**: B.Tech in Computer Science and Engineering, GMRIT Deemed to be University
- **GitHub**: [@tentualekhya2005-boop](https://github.com/tentualekhya2005-boop)
- **Verified Public Profile**: [https://www.upsk.to/tentualekhya2005-boo](https://www.upsk.to/tentualekhya2005-boo)
- **Certification**: System Design Fundamentals (Completed with 100/100 score across 10 modules)

---

## 📄 License
This project is open-source and licensed under the [MIT License](LICENSE).

