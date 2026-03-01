def test_create_team_admin(client, admin_headers):
    response = client.post("/api/teams", json={"name": "Legal"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Legal"


def test_create_team_non_admin_forbidden(client, worker_headers):
    response = client.post("/api/teams", json={"name": "Legal"}, headers=worker_headers)
    assert response.status_code == 403


def test_create_team_duplicate_name(client, admin_headers, team):
    response = client.post("/api/teams", json={"name": "Test Team"}, headers=admin_headers)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_list_teams(client, admin_headers, team):
    response = client.get("/api/teams", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_teams_no_auth(client):
    response = client.get("/api/teams")
    assert response.status_code == 403
