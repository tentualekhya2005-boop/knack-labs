import json
from pathlib import Path
import httpx

base_url = "http://127.0.0.1:8000"
evidence = []

# 1. Protected endpoint without auth (expect 401)
res_no_auth = httpx.get(f"{base_url}/links")
evidence.append(f"=== 1. Protected Endpoint Without Auth ===\nStatus: {res_no_auth.status_code}\nBody: {res_no_auth.text}")
print(f"1. Protected without auth: {res_no_auth.status_code} {res_no_auth.text}")
assert res_no_auth.status_code == 401

# 2. Login Tenant A & Tenant B to obtain JWT tokens
login_a = httpx.post(f"{base_url}/auth/login", json={"email": "tenant_a@example.com", "password": "password123"})
token_a = login_a.json()["access_token"]
evidence.append(f"=== 2. Login Tenant A ===\nStatus: {login_a.status_code}\nPrincipal: {login_a.json().get('principal_id')}")
print(f"2. Login Tenant A: {login_a.status_code} (principal: {login_a.json().get('principal_id')})")

login_b = httpx.post(f"{base_url}/auth/login", json={"email": "tenant_b@example.com", "password": "password123"})
token_b = login_b.json()["access_token"]
evidence.append(f"=== 2b. Login Tenant B ===\nStatus: {login_b.status_code}\nPrincipal: {login_b.json().get('principal_id')}")
print(f"2b. Login Tenant B: {login_b.status_code} (principal: {login_b.json().get('principal_id')})")

# 3. Create link as Tenant A with JWT (expect 201)
headers_a = {"Authorization": f"Bearer {token_a}"}
create_a = httpx.post(f"{base_url}/links", json={"long_url": "https://tenant-a.com/dashboard"}, headers=headers_a)
link_a_id = create_a.json()["id"]
code_a = create_a.json()["code"]
evidence.append(f"=== 3. Create Link as Tenant A ===\nStatus: {create_a.status_code}\nBody: {create_a.text}")
print(f"3. Create link as Tenant A: {create_a.status_code} id={link_a_id} code={code_a}")
assert create_a.status_code == 201

# 4. Multi-Tenant Authorization (IDOR Prevention): Tenant B tries to access Tenant A's link (expect 404)
headers_b = {"Authorization": f"Bearer {token_b}"}
idor_probe = httpx.get(f"{base_url}/links/{link_a_id}", headers=headers_b)
evidence.append(f"=== 4. Tenant B IDOR Probe on Tenant A's Link ===\nStatus: {idor_probe.status_code}\nBody: {idor_probe.text}")
print(f"4. Tenant B IDOR probe on Tenant A link: {idor_probe.status_code} {idor_probe.text}")
assert idor_probe.status_code == 404

# 5. Public redirect without auth (expect 302)
redirect_res = httpx.get(f"{base_url}/r/{code_a}", follow_redirects=False)
evidence.append(f"=== 5. Public Redirect (No Auth) ===\nStatus: {redirect_res.status_code}\nLocation: {redirect_res.headers.get('location')}")
print(f"5. Public redirect: {redirect_res.status_code} Location: {redirect_res.headers.get('location')}")
assert redirect_res.status_code == 302

# 6. Rate Limiting Tests
# 6a. Login rate limit (10/min -> 11th request gives 429)
login_codes = []
for i in range(15):
    res = httpx.post(f"{base_url}/auth/login", json={"email": "wrong@example.com", "password": "wrong"})
    login_codes.append(res.status_code)
evidence.append(f"=== 6a. Login Rate Limiting (10/min limit) ===\nStatusCodes: {login_codes}")
print(f"6a. Login rate limit codes: {login_codes[:10]} -> throttled: {login_codes[10:]}")
assert 429 in login_codes

# 6b. Create link rate limit (30/min -> 31st request gives 429)
create_codes = []
for i in range(35):
    res = httpx.post(f"{base_url}/links", json={"long_url": f"https://example.com/burst-{i}"}, headers=headers_a)
    create_codes.append(res.status_code)
evidence.append(f"=== 6b. Create Link Rate Limiting (30/min limit) ===\nStatusCodes: {create_codes}")
print(f"6b. Create link rate limit: {create_codes[:30]} -> throttled: {create_codes[30:]}")
assert 429 in create_codes

# 6c. Redirect rate limit (120/min -> 121st request gives 429)
redir_codes = []
for i in range(125):
    res = httpx.get(f"{base_url}/r/{code_a}", follow_redirects=False)
    redir_codes.append(res.status_code)
evidence.append(f"=== 6c. Redirect Rate Limiting (120/min limit) ===\nStatusCodes: {redir_codes}")
print(f"6c. Redirect rate limit: 120 OK/302 -> throttled: {redir_codes[120:]}")
assert 429 in redir_codes

out_dir = Path("progress/evidence/module-04")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "build-evidence.txt"
out_file.write_text("\n\n".join(evidence), encoding="utf-8")
print(f"All Module 04 verification evidence saved to {out_file}")

