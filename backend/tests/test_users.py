def test_list_users_admin(client, admin_headers, worker_user):
    response = client.get("/api/users", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_users_non_admin_forbidden(client, worker_headers):
    response = client.get("/api/users", headers=worker_headers)
    assert response.status_code == 403


def test_update_user_role(client, admin_headers, worker_user):
    response = client.put(f"/api/users/{worker_user.id}", json={"role": "supervisor"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "supervisor"


def test_update_user_role_non_admin_forbidden(client, worker_headers, admin_user):
    response = client.put(f"/api/users/{admin_user.id}", json={"role": "worker"}, headers=worker_headers)
    assert response.status_code == 403


def test_cannot_demote_self(client, admin_headers, admin_user):
    response = client.put(f"/api/users/{admin_user.id}", json={"role": "worker"}, headers=admin_headers)
    assert response.status_code == 400
    assert "Cannot demote yourself" in response.json()["detail"]
