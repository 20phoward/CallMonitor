"""Tests for routers/twilio_webhooks.py"""

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

TEST_DATABASE_URL = "sqlite:///./test_twilio.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_twilio_db():
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
    t = Team(name="Twilio Test Team")
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def worker_user(db, team):
    user = User(
        email="twilio_worker@test.com",
        hashed_password=hash_password("Worker123"),
        name="Twilio Worker",
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


@pytest.fixture
def twilio_call(db, worker_user):
    call = Call(
        title="Test Twilio Call",
        source_type="twilio",
        status="connecting",
        uploaded_by=worker_user.id,
        call_direction="outbound",
        patient_phone="+15551234567",
        connection_mode="browser",
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


@patch("routers.twilio_webhooks.validate_twilio_request", return_value=True)
def test_voice_webhook_returns_twiml(mock_validate, client, twilio_call):
    resp = client.post(
        "/api/twilio/voice",
        data={
            "To": "+15551234567",
            "From": "+15559999999",
            "CallSid": "CA_test_sid_123",
            "callId": str(twilio_call.id),
        },
    )
    assert resp.status_code == 200
    assert "text/xml" in resp.headers["content-type"]
    body = resp.text
    assert "<Dial" in body
    assert "+15551234567" in body
    assert "record" in body


@patch("routers.twilio_webhooks.validate_twilio_request", return_value=True)
def test_voice_webhook_updates_call_sid(mock_validate, client, twilio_call, db):
    client.post(
        "/api/twilio/voice",
        data={
            "To": "+15551234567",
            "From": "+15559999999",
            "CallSid": "CA_updated_sid",
            "callId": str(twilio_call.id),
        },
    )
    db.refresh(twilio_call)
    assert twilio_call.twilio_call_sid == "CA_updated_sid"


@patch("routers.twilio_webhooks.validate_twilio_request", return_value=True)
def test_status_webhook_updates_call_status(mock_validate, client, twilio_call, db):
    resp = client.post(
        f"/api/twilio/status?callId={twilio_call.id}",
        data={"CallStatus": "in-progress", "CallSid": "CA_test"},
    )
    assert resp.status_code == 200
    db.refresh(twilio_call)
    assert twilio_call.status == "in_progress"


@patch("routers.twilio_webhooks.validate_twilio_request", return_value=True)
def test_status_webhook_completed(mock_validate, client, twilio_call, db):
    resp = client.post(
        f"/api/twilio/status?callId={twilio_call.id}",
        data={"CallStatus": "completed", "CallSid": "CA_test"},
    )
    assert resp.status_code == 200
    db.refresh(twilio_call)
    assert twilio_call.status == "processing"


@patch("routers.twilio_webhooks.validate_twilio_request", return_value=True)
def test_status_webhook_failed(mock_validate, client, twilio_call, db):
    resp = client.post(
        f"/api/twilio/status?callId={twilio_call.id}",
        data={"CallStatus": "busy", "CallSid": "CA_test"},
    )
    assert resp.status_code == 200
    db.refresh(twilio_call)
    assert twilio_call.status == "failed"
    assert "busy" in twilio_call.error_message


@patch("routers.twilio_webhooks.validate_twilio_request", return_value=True)
@patch("routers.twilio_webhooks._download_and_process")
def test_recording_webhook_triggers_download(mock_download, mock_validate, client, twilio_call, db):
    # Patch Thread so we can verify _download_and_process is called with correct args
    with patch("routers.twilio_webhooks.Thread") as mock_thread_cls:
        mock_thread_instance = MagicMock()
        mock_thread_cls.return_value = mock_thread_instance

        resp = client.post(
            f"/api/twilio/recording?callId={twilio_call.id}",
            data={
                "RecordingUrl": "https://api.twilio.com/recordings/RE123",
                "RecordingDuration": "30",
                "RecordingStatus": "completed",
                "CallSid": "CA_test",
            },
        )
        assert resp.status_code == 200

        mock_thread_cls.assert_called_once()
        call_args = mock_thread_cls.call_args
        assert call_args.kwargs["args"] == (twilio_call.id, "https://api.twilio.com/recordings/RE123")
        mock_thread_instance.start.assert_called_once()


def test_token_endpoint_requires_auth(client):
    resp = client.post("/api/twilio/token")
    assert resp.status_code == 403


@patch("routers.twilio_webhooks.generate_voice_token", return_value="mock-jwt-token")
def test_token_endpoint_returns_token(mock_gen, client, worker_user, worker_headers):
    resp = client.post("/api/twilio/token", headers=worker_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == "mock-jwt-token"
    assert data["identity"] == f"user-{worker_user.id}"
