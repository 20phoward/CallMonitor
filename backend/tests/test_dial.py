"""Tests for POST /api/calls/dial endpoint."""

import sys
from unittest.mock import patch, MagicMock

# Mock heavy/optional dependencies before any app imports
if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db, Call, User, Team
from auth import hash_password, create_access_token
from main import app

TEST_DATABASE_URL = "sqlite:///./test_dial.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_dial_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def team(db):
    t = Team(name="Dial Test Team")
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def worker_user(db, team):
    user = User(
        email="dial_worker@test.com",
        hashed_password=hash_password("Worker123"),
        name="Dial Worker",
        role="worker",
        team_id=team.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def worker_headers(worker_user):
    token = create_access_token(worker_user.id)
    return {"Authorization": f"Bearer {token}"}


def test_dial_browser_mode_creates_call(client, worker_headers, db):
    resp = client.post(
        "/api/calls/dial",
        json={
            "patient_phone": "+15551234567",
            "mode": "browser",
            "title": "Browser Test Call",
        },
        headers=worker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connecting"
    call_id = data["call_id"]

    call = db.query(Call).filter(Call.id == call_id).first()
    assert call is not None
    assert call.source_type == "twilio"
    assert call.call_direction == "outbound"
    assert call.patient_phone == "+15551234567"
    assert call.connection_mode == "browser"


@patch("routers.calls.get_twilio_client")
def test_dial_phone_mode_creates_call_and_initiates(mock_get_client, client, worker_headers, db):
    mock_client = MagicMock()
    mock_twilio_call = MagicMock()
    mock_twilio_call.sid = "CA_phone_test_sid"
    mock_client.calls.create.return_value = mock_twilio_call
    mock_get_client.return_value = mock_client

    resp = client.post(
        "/api/calls/dial",
        json={
            "patient_phone": "+15551234567",
            "mode": "phone",
            "worker_phone": "+15559876543",
            "title": "Phone Test Call",
        },
        headers=worker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connecting"
    call_id = data["call_id"]

    # Verify Twilio client was called
    mock_client.calls.create.assert_called_once()

    # Verify call record has twilio_call_sid
    call = db.query(Call).filter(Call.id == call_id).first()
    assert call.twilio_call_sid == "CA_phone_test_sid"


def test_dial_requires_auth(client):
    resp = client.post(
        "/api/calls/dial",
        json={"patient_phone": "+15551234567", "mode": "browser"},
    )
    assert resp.status_code == 403


def test_dial_rejects_invalid_phone(client, worker_headers):
    resp = client.post(
        "/api/calls/dial",
        json={"patient_phone": "not-a-phone", "mode": "browser"},
        headers=worker_headers,
    )
    assert resp.status_code == 400


def test_dial_phone_mode_requires_worker_phone(client, worker_headers):
    resp = client.post(
        "/api/calls/dial",
        json={"patient_phone": "+15551234567", "mode": "phone"},
        headers=worker_headers,
    )
    assert resp.status_code == 400
    assert "worker_phone" in resp.json()["detail"]
