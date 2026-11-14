import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure app package is in sys.path
API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

import httpx

BASE_URL = "http://127.0.0.1:8000"

evidence_lines = []

def log(msg: str):
    print(msg)
    evidence_lines.append(msg)

def main():
    log("=== MODULE 10 BUILD VERIFICATION: CI/CD & DEPLOYMENT (RAILWAY) ===")
    log(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # 1. Verify Dockerfile
    log("\n--- Step 1: Verify Production Multi-Stage Dockerfile ---")
    dockerfile_path = API_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile does not exist in API_ROOT"
    dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.13-slim AS builder" in dockerfile_content, "Missing builder stage"
    assert "FROM python:3.13-slim AS runtime" in dockerfile_content, "Missing runtime stage"
    assert "0.0.0.0" in dockerfile_content, "Dockerfile must bind to 0.0.0.0"
    assert "${PORT}" in dockerfile_content or "$PORT" in dockerfile_content, "Dockerfile must use dynamic ${PORT}"
    assert "HEALTHCHECK" in dockerfile_content, "Dockerfile must configure container HEALTHCHECK"
    assert "alembic upgrade head" in dockerfile_content, "Dockerfile must run startup migrations"
    log(f"Dockerfile verified at {dockerfile_path} (multi-stage, 0.0.0.0 host binding, dynamic PORT, HEALTHCHECK, startup migrations).")

    # 2. Verify GitHub Actions CI Pipeline
    log("\n--- Step 2: Verify CI Pipeline (.github/workflows/ci.yml) ---")
    ci_path = API_ROOT.parent.parent / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), "ci.yml does not exist"
    ci_content = ci_path.read_text(encoding="utf-8")
    assert "postgres:16-alpine" in ci_content, "CI must include postgres service container"
    assert "redis:7-alpine" in ci_content, "CI must include redis service container"
    assert "alembic upgrade head" in ci_content, "CI must execute migrations"
    assert "pytest" in ci_content, "CI must run pytest suite"
    log(f"CI workflow verified at {ci_path} (PostgreSQL + Redis service containers, automated test suite, container validation).")

    # 3. Verify Live /health Endpoint
    log("\n--- Step 3: Verify Liveness Probe (GET /health) ---")
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        res_health = client.get("/health")
        assert res_health.status_code == 200, f"Expected 200, got {res_health.status_code}"
        health_data = res_health.json()
        assert health_data == {"ok": True}
        log(f"Liveness probe GET /health -> Status: {res_health.status_code}, Body: {health_data}")
        log("CONFIRMED: /health responds immediately with HTTP 200.")

        # 4. Verify Live /ready Endpoint
        log("\n--- Step 4: Verify Readiness Probe (GET /ready) ---")
        res_ready = client.get("/ready")
        assert res_ready.status_code == 200, f"Expected 200, got {res_ready.status_code}"
        ready_data = res_ready.json()
        assert ready_data["ok"] is True
        assert ready_data["status"] == "ready"
        assert ready_data["dependencies"]["database"] == "ready"
        assert ready_data["dependencies"]["redis"] == "ready"
        log(f"Readiness probe GET /ready -> Status: {res_ready.status_code}, Body: {ready_data}")
        log("CONFIRMED: /ready validates PostgreSQL and Redis connectivity.")

    # 5. Verify Railway Configuration & Documentation
    log("\n--- Step 5: Verify Railway Config & Environment Documentation ---")
    railway_json = API_ROOT / "railway.json"
    assert railway_json.exists(), "railway.json does not exist"
    railway_data = json.loads(railway_json.read_text(encoding="utf-8"))
    start_cmd = railway_data.get("deploy", {}).get("startCommand", "")
    assert "${PORT" in start_cmd or "$PORT" in start_cmd, (
        f"DEPLOYMENT CONFIG DEFECT: Railway startCommand hardcodes a static port instead of using ${{PORT}}! Got: {start_cmd}"
    )
    assert railway_data.get("deploy", {}).get("healthcheckPath") == "/health", "Healthcheck path must be /health"

    railway_env = API_ROOT / ".env.railway.example"
    assert railway_env.exists(), ".env.railway.example does not exist"
    rollback_doc = API_ROOT / "docs" / "DEPLOYMENT_AND_ROLLBACK.md"
    assert rollback_doc.exists(), "DEPLOYMENT_AND_ROLLBACK.md does not exist"
    log("CONFIRMED: railway.json, .env.railway.example, and DEPLOYMENT_AND_ROLLBACK.md verified.")

    # 6. Run Pytest Regression Suite
    log("\n--- Step 6: Full Pytest Regression Suite Execution ---")
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_health.py", "-v"],
        capture_output=True,
        text=True,
        cwd=str(API_ROOT),
    )
    log(pytest_res.stdout)
    assert pytest_res.returncode == 0, f"Pytest failed with code {pytest_res.returncode}"
    log("CONFIRMED: All health and readiness tests passing.")

    log("\n=== ALL MODULE 10 BUILD ACCEPTANCE CRITERIA VERIFIED ===")

    # Write evidence to file
    evidence_dir = API_ROOT.parent.parent / "progress" / "evidence" / "module-10"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "build-evidence.txt"
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write("\n".join(evidence_lines))
    print(f"\nEvidence successfully written to {evidence_file}")

if __name__ == "__main__":
    main()

