def test_audit_log_admin(client, admin_headers, admin_user, db):
    client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123"})
    response = client.get("/api/audit-log", headers=admin_headers)
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) >= 1


def test_audit_log_non_admin_forbidden(client, worker_headers):
    response = client.get("/api/audit-log", headers=worker_headers)
    assert response.status_code == 403


def test_audit_log_pagination(client, admin_headers, admin_user):
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123"})
    response = client.get("/api/audit-log?limit=2", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
