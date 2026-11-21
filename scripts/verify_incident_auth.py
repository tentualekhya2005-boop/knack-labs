import socket
import sys
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

def run_tests():
    client = TestClient(app)
    valid_token = create_access_token({"principal_id": "admin_user", "role": "admin"})

    print("--- 1. Testing with FastAPI TestClient ---")
    
    # 1. Authorization: "" -> 401
    r1 = client.get("/api/admin/links", headers={"Authorization": ""})
    print(f"1. Authorization: '' -> {r1.status_code} ({r1.json()})")
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}"

    # 2. Authorization: "   " -> 401
    r2 = client.get("/api/admin/links", headers={"Authorization": "   "})
    print(f"2. Authorization: '   ' -> {r2.status_code} ({r2.json()})")
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}"

    # 3. Authorization: Bearer (no token) -> 401
    r3 = client.get("/api/admin/links", headers={"Authorization": "Bearer"})
    print(f"3. Authorization: 'Bearer' -> {r3.status_code} ({r3.json()})")
    assert r3.status_code == 401, f"Expected 401, got {r3.status_code}"

    # 4. Valid Authorization: Bearer <valid_token> -> 200
    r4 = client.get("/api/admin/links", headers={"Authorization": f"Bearer {valid_token}"})
    print(f"4. Valid Bearer Token -> {r4.status_code} (Returned {len(r4.json())} links)")
    assert r4.status_code == 200, f"Expected 200, got {r4.status_code}"

    # 5. No Authorization header at all -> 401
    r5 = client.get("/api/admin/links")
    print(f"5. No Authorization header -> {r5.status_code} ({r5.json()})")
    assert r5.status_code == 401, f"Expected 401, got {r5.status_code}"

    # 6. DELETE /api/admin/links/1 with no auth -> 401
    r6 = client.delete("/api/admin/links/1")
    print(f"6. DELETE without auth -> {r6.status_code} ({r6.json()})")
    assert r6.status_code == 401, f"Expected 401, got {r6.status_code}"

    # 7. DELETE /api/admin/links/1 with empty auth -> 401
    r7 = client.delete("/api/admin/links/1", headers={"Authorization": ""})
    print(f"7. DELETE with empty auth -> {r7.status_code} ({r7.json()})")
    assert r7.status_code == 401, f"Expected 401, got {r7.status_code}"

    print("\n--- 2. Testing against live server via raw TCP socket ---")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 3000))
    # Send request with Authorization: empty string
    raw_req = b"DELETE /api/admin/links/1 HTTP/1.1\r\nHost: 127.0.0.1:3000\r\nAuthorization: \r\nConnection: close\r\n\r\n"
    s.sendall(raw_req)
    raw_resp = s.recv(4096).decode("latin1")
    s.close()
    first_line = raw_resp.split("\r\n")[0]
    print(f"Raw socket DELETE with empty Authorization -> {first_line}")
    assert "401" in first_line, f"Expected 401 in raw socket response, got {first_line}"

    print("\nALL 5 REQUIRED VERIFICATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_tests()
