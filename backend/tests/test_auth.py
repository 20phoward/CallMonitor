def test_register_first_user_becomes_admin(client):
    response = client.post("/api/auth/register", json={
        "email": "first@test.com",
        "password": "First123",
        "name": "First User",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "first@test.com"
    assert data["role"] == "admin"


def test_register_second_user_becomes_worker(client, admin_user):
    response = client.post("/api/auth/register", json={
        "email": "second@test.com",
        "password": "Second123",
        "name": "Second User",
    })
    assert response.status_code == 200
    assert response.json()["role"] == "worker"


def test_register_weak_password_rejected(client):
    response = client.post("/api/auth/register", json={
        "email": "weak@test.com",
        "password": "short",
        "name": "Weak Password",
    })
    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


def test_register_no_uppercase_rejected(client):
    response = client.post("/api/auth/register", json={
        "email": "weak@test.com",
        "password": "nouppercase1",
        "name": "No Upper",
    })
    assert response.status_code == 400
    assert "uppercase" in response.json()["detail"]


def test_register_duplicate_email(client, admin_user):
    response = client.post("/api/auth/register", json={
        "email": "admin@test.com",
        "password": "Duplicate1",
        "name": "Duplicate",
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success(client, admin_user):
    response = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client, admin_user):
    response = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "WrongPass1",
    })
    assert response.status_code == 401


def test_refresh_token(client, admin_user):
    login = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123",
    })
    refresh_token = login.json()["refresh_token"]
    response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_get_me(client, admin_headers):
    response = client.get("/api/users/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@test.com"


def test_get_me_no_token(client):
    response = client.get("/api/users/me")
    assert response.status_code == 403
