from database import Call


def test_worker_sees_only_own_calls(client, worker_headers, worker_user, admin_user, db):
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls", headers=worker_headers)
    assert response.status_code == 200
    titles = [c["title"] for c in response.json()]
    assert "Worker Call" in titles
    assert "Admin Call" not in titles


def test_supervisor_sees_team_calls(client, supervisor_headers, supervisor_user, worker_user, admin_user, db):
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls", headers=supervisor_headers)
    assert response.status_code == 200
    titles = [c["title"] for c in response.json()]
    assert "Worker Call" in titles
    assert "Admin Call" not in titles


def test_admin_sees_all_calls(client, admin_headers, worker_user, admin_user, db):
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_worker_cannot_view_others_call(client, worker_headers, admin_user, db):
    call = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.get(f"/api/calls/{call.id}", headers=worker_headers)
    assert response.status_code == 403


def test_worker_cannot_delete(client, worker_headers, worker_user, db):
    call = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.delete(f"/api/calls/{call.id}", headers=worker_headers)
    assert response.status_code == 403


def test_supervisor_can_delete_team_call(client, supervisor_headers, worker_user, db):
    call = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.delete(f"/api/calls/{call.id}", headers=supervisor_headers)
    assert response.status_code == 200


def test_worker_cannot_submit_review(client, worker_headers, worker_user, db):
    call = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.post(f"/api/calls/{call.id}/review", json={"status": "approved"}, headers=worker_headers)
    assert response.status_code == 403


def test_no_auth_returns_403(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()

    response = client.get("/api/calls")
    assert response.status_code == 403


def test_stats_scoped_to_worker(client, worker_headers, worker_user, admin_user, db):
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls/stats", headers=worker_headers)
    assert response.status_code == 200
    assert response.json()["total_calls"] == 1


def test_health_no_auth_required(client):
    response = client.get("/api/health")
    assert response.status_code == 200
