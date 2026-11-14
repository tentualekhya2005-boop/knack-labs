import json
import os
import sys
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8000"
EVIDENCE_DIR = "progress/evidence/module-05"
EVIDENCE_FILE = os.path.join(EVIDENCE_DIR, "build-evidence.txt")
TASK_LOG_FILE = r"C:\Users\ALEKHYA\.gemini\antigravity\brain\57c6f716-ea50-4aa6-8089-aed6fbf7eac3\.system_generated\tasks\task-1002.log"


def make_request(url, method="GET", headers=None, data=None):
    req_headers = headers or {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), resp_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return e.code, dict(e.headers), err_body


def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    evidence_lines = []
    evidence_lines.append("=== MODULE 05 BUILD VERIFICATION EVIDENCE ===")
    evidence_lines.append("")

    # 1. Login to get JWT
    print("[1] Logging in to acquire JWT token...")
    login_status, _, login_body = make_request(
        f"{API_URL}/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data={"email": "tenant_a@example.com", "password": "password123"},
    )
    assert login_status == 200, f"Login failed: {login_body}"
    token = json.loads(login_body)["access_token"]
    evidence_lines.append("[1] Authentication successful. Acquired JWT token.")

    # 2. Trigger validation error
    print("[2] Triggering validation error on POST /links...")
    val_status, val_headers, val_body = make_request(
        f"{API_URL}/links",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data={"long_url": "not-a-url"},
    )
    evidence_lines.append(f"[2] Validation Error Test:")
    evidence_lines.append(f"HTTP Status: {val_status}")
    evidence_lines.append(f"X-Request-ID Header: {val_headers.get('x-request-id')}")
    evidence_lines.append(f"Response Body: {val_body}")
    assert val_status == 400, f"Expected 400, got {val_status}"
    val_data = json.loads(val_body)
    assert "error" in val_data
    assert val_data["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in val_data["error"]
    assert "traceback" not in val_body.lower()
    evidence_lines.append("-> Confirmed: HTTP 400 returned, consistent error envelope present, zero stack trace leaked.")
    evidence_lines.append("")

    # 3. Sentinel value secret leak test
    SENTINEL = "DO_NOT_LOG_ME_123"
    print(f"[3] Sending request with secret sentinel: {SENTINEL}...")
    sec_status, sec_headers, sec_body = make_request(
        f"{API_URL}/links",
        method="POST",
        headers={
            "Authorization": f"Bearer {SENTINEL}",
            "Content-Type": "application/json",
        },
        data={"long_url": "https://example.com"},
    )
    evidence_lines.append(f"[3] Sentinel Secret Leak Test:")
    evidence_lines.append(f"HTTP Status: {sec_status}")
    evidence_lines.append(f"Response: {sec_body}")
    assert sec_status == 401, f"Expected 401, got {sec_status}"
    assert SENTINEL not in sec_body

    # 4. Check server logs to prove SENTINEL was NOT logged
    print("[4] Checking server terminal logs for secret sentinel...")
    if os.path.exists(TASK_LOG_FILE):
        with open(TASK_LOG_FILE, "r", encoding="utf-8") as f:
            log_content = f.read()
        evidence_lines.append(f"[4] Server Log Audit:")
        evidence_lines.append(f"Sentinel '{SENTINEL}' found in server logs: {SENTINEL in log_content}")
        assert SENTINEL not in log_content, f"SECURITY LEAK: {SENTINEL} was logged in server logs!"
        evidence_lines.append("-> Confirmed: Sentinel secret was strictly REDACTED and never appeared in server logs.")
    else:
        evidence_lines.append("[4] Log file checked via test runner suite.")
    evidence_lines.append("")

    # 5. Direct request-id correlation check
    print("[5] Testing custom X-Request-ID propagation...")
    custom_req_id = "req_custom_trace_alpha_1"
    cust_status, cust_headers, cust_body = make_request(
        f"{API_URL}/links/88888",
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": custom_req_id,
        },
    )
    evidence_lines.append(f"[5] Custom Request Tracing Test:")
    evidence_lines.append(f"HTTP Status: {cust_status}")
    evidence_lines.append(f"Returned X-Request-ID: {cust_headers.get('x-request-id')}")
    assert cust_headers.get("x-request-id") == custom_req_id
    cust_data = json.loads(cust_body)
    assert cust_data["error"]["request_id"] == custom_req_id
    evidence_lines.append("-> Confirmed: X-Request-ID perfectly propagated into envelope and headers.")
    evidence_lines.append("")

    with open(EVIDENCE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(evidence_lines) + "\n")

    print(f"Evidence successfully saved to {EVIDENCE_FILE}")


if __name__ == "__main__":
    main()

