# Phase 4: Live Call Recording Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable workers to dial patients from Call Monitor via Twilio, with automatic call recording that feeds into the existing Whisper/Claude pipeline.

**Architecture:** Twilio Voice SDK in the browser for softphone mode, Twilio REST API for phone-connect mode. Twilio webhooks receive call events and recording URLs. Backend downloads recordings and feeds them into the existing processing pipeline.

**Tech Stack:** Python `twilio` SDK, `@twilio/voice-sdk` (frontend), TwiML, httpx (recording download)

---

### Task 1: Add Twilio SDK and Config Variables

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`

**Step 1: Add twilio to requirements.txt**

Add this line at the end of `backend/requirements.txt`:

```
twilio==9.4.0
```

**Step 2: Add Twilio config variables to config.py**

Add these lines at the end of `backend/config.py` (after the `REFRESH_TOKEN_EXPIRE_DAYS` line):

```python
# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
TWILIO_TWIML_APP_SID = os.getenv("TWILIO_TWIML_APP_SID", "")
TWILIO_API_KEY = os.getenv("TWILIO_API_KEY", "")
TWILIO_API_SECRET = os.getenv("TWILIO_API_SECRET", "")
TWILIO_WEBHOOK_BASE_URL = os.getenv("TWILIO_WEBHOOK_BASE_URL", "http://localhost:8000")
```

**Step 3: Install the dependency**

```bash
source ~/workspace/call-monitor-venv/bin/activate
pip install twilio==9.4.0
```

**Step 4: Verify existing tests still pass**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/ -v
```
Expected: All 52 tests pass.

**Step 5: Commit**

```bash
git add backend/requirements.txt backend/config.py
git commit -m "feat: add twilio SDK and config variables for Phase 4"
```

---

### Task 2: Update Call Model with Twilio Fields

**Files:**
- Modify: `backend/database.py:29-39` (AuditAction enum)
- Modify: `backend/database.py:85-102` (Call model)

**Step 1: Add new audit actions to the AuditAction enum**

In `backend/database.py`, add two new values to the `AuditAction` enum after `update_role`:

```python
class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    view_call = "view_call"
    view_transcript = "view_transcript"
    upload_call = "upload_call"
    delete_call = "delete_call"
    submit_review = "submit_review"
    update_review = "update_review"
    create_user = "create_user"
    update_role = "update_role"
    dial_call = "dial_call"
    recording_received = "recording_received"
```

**Step 2: Add new columns to the Call model**

In `backend/database.py`, add four new columns to the `Call` class after `uploaded_by`:

```python
class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    duration = Column(Float, nullable=True)  # seconds
    status = Column(String, default="pending")  # pending/connecting/in_progress/processing/completed/failed
    source_type = Column(String, default="upload")  # upload/twilio
    audio_filename = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    twilio_call_sid = Column(String, nullable=True)
    call_direction = Column(String, nullable=True)  # outbound/inbound
    patient_phone = Column(String, nullable=True)
    connection_mode = Column(String, nullable=True)  # browser/phone

    transcript = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    tonality = relationship("TonalityResult", back_populates="call", uselist=False, cascade="all, delete-orphan")
    score = relationship("CallScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    review = relationship("Review", back_populates="call", uselist=False, cascade="all, delete-orphan")
    uploader = relationship("User", back_populates="calls")
```

**Step 3: Delete the old database to recreate schema**

```bash
rm -f /mnt/c/Users/ticta/workspace/call-monitor/backend/calls.db
rm -f /mnt/c/Users/ticta/workspace/call-monitor/backend/test.db
```

**Step 4: Run tests to verify schema works**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/ -v
```
Expected: All 52 tests pass.

**Step 5: Commit**

```bash
git add backend/database.py
git commit -m "feat: add Twilio fields to Call model and new audit actions"
```

---

### Task 3: Add Twilio-Related Pydantic Schemas

**Files:**
- Modify: `backend/models/schemas.py`

**Step 1: Add DialRequest and DialResponse schemas**

Add these after the `AuditLogResponse` class (around line 77) in `backend/models/schemas.py`:

```python
# --- Twilio / Dialing ---

class DialRequest(BaseModel):
    patient_phone: str
    mode: str = "browser"  # "browser" or "phone"
    worker_phone: Optional[str] = None  # Required when mode="phone"
    title: str = "Phone Call"


class DialResponse(BaseModel):
    call_id: int
    status: str


class TwilioTokenResponse(BaseModel):
    token: str
    identity: str
```

**Step 2: Add Twilio fields to CallDetail and CallSummary**

Add `twilio_call_sid`, `call_direction`, `patient_phone`, and `connection_mode` to `CallDetail` (after `error_message`):

```python
class CallDetail(BaseModel):
    id: int
    title: str
    date: datetime
    duration: Optional[float] = None
    status: str
    source_type: str
    audio_filename: Optional[str] = None
    error_message: Optional[str] = None
    call_direction: Optional[str] = None
    connection_mode: Optional[str] = None
    patient_phone: Optional[str] = None
    transcript: Optional[TranscriptResponse] = None
    tonality: Optional[TonalityResponse] = None
    score: Optional[CallScoreResponse] = None
    review: Optional[ReviewResponse] = None

    model_config = {"from_attributes": True}
```

Also add `call_direction` and `connection_mode` to `CallSummary`:

```python
class CallSummary(BaseModel):
    id: int
    title: str
    date: datetime
    duration: Optional[float] = None
    status: str
    source_type: str
    overall_sentiment: Optional[str] = None
    overall_score: Optional[float] = None
    overall_rating: Optional[float] = None
    review_status: Optional[str] = None
    call_direction: Optional[str] = None
    connection_mode: Optional[str] = None

    model_config = {"from_attributes": True}
```

**Step 3: Run tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/ -v
```
Expected: All 52 tests pass.

**Step 4: Commit**

```bash
git add backend/models/schemas.py
git commit -m "feat: add Twilio-related Pydantic schemas"
```

---

### Task 4: Create Twilio Service Module

**Files:**
- Create: `backend/services/twilio_service.py`
- Create: `backend/tests/test_twilio_service.py`

**Step 1: Write the tests**

Create `backend/tests/test_twilio_service.py`:

```python
from unittest.mock import patch, MagicMock
import pytest


def test_generate_voice_token():
    """Token generation returns a non-empty JWT string."""
    with patch("services.twilio_service.TWILIO_ACCOUNT_SID", "ACtest123"), \
         patch("services.twilio_service.TWILIO_API_KEY", "SKtest123"), \
         patch("services.twilio_service.TWILIO_API_SECRET", "secret123"), \
         patch("services.twilio_service.TWILIO_TWIML_APP_SID", "APtest123"):
        from services.twilio_service import generate_voice_token
        token = generate_voice_token("user-1")
        assert isinstance(token, str)
        assert len(token) > 0


def test_validate_twilio_request_skips_when_no_auth_token():
    """Validation is skipped when TWILIO_AUTH_TOKEN is empty (dev/test)."""
    with patch("services.twilio_service.TWILIO_AUTH_TOKEN", ""):
        from services.twilio_service import validate_twilio_request
        # Should return True (skip validation) when no auth token
        assert validate_twilio_request("http://example.com", {}, "fake-sig") is True


def test_validate_twilio_request_validates_when_token_set():
    """Validation uses RequestValidator when TWILIO_AUTH_TOKEN is set."""
    with patch("services.twilio_service.TWILIO_AUTH_TOKEN", "real-token"), \
         patch("services.twilio_service.RequestValidator") as MockValidator:
        mock_instance = MockValidator.return_value
        mock_instance.validate.return_value = False
        from services.twilio_service import validate_twilio_request
        result = validate_twilio_request("http://example.com", {}, "bad-sig")
        assert result is False


def test_validate_e164_phone_valid():
    from services.twilio_service import validate_e164_phone
    assert validate_e164_phone("+15551234567") == "+15551234567"


def test_validate_e164_phone_invalid():
    from services.twilio_service import validate_e164_phone
    with pytest.raises(ValueError):
        validate_e164_phone("555-123-4567")


def test_validate_e164_phone_auto_format():
    """10-digit US numbers get +1 prepended."""
    from services.twilio_service import validate_e164_phone
    assert validate_e164_phone("5551234567") == "+15551234567"
```

**Step 2: Run tests to verify they fail**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/test_twilio_service.py -v
```
Expected: FAIL (module not found)

**Step 3: Create the service module**

Create `backend/services/twilio_service.py`:

```python
import logging
import re

import httpx
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_API_KEY,
    TWILIO_API_SECRET,
    TWILIO_PHONE_NUMBER,
    TWILIO_TWIML_APP_SID,
)

logger = logging.getLogger(__name__)


def get_twilio_client() -> Client:
    """Create a Twilio REST API client."""
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def generate_voice_token(identity: str) -> str:
    """Generate a short-lived access token for the Twilio Voice JS SDK."""
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity=identity,
    )
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=False,
    )
    token.add_grant(voice_grant)
    return token.to_jwt()


def validate_twilio_request(url: str, params: dict, signature: str) -> bool:
    """Validate that a webhook request actually came from Twilio."""
    if not TWILIO_AUTH_TOKEN:
        # Skip validation in dev/test when no auth token is configured
        return True
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    return validator.validate(url, params, signature)


def validate_e164_phone(phone: str) -> str:
    """Validate and normalize a phone number to E.164 format.

    Accepts:
    - +15551234567 (already E.164)
    - 5551234567 (10-digit US, prepends +1)

    Raises ValueError for invalid numbers.
    """
    cleaned = re.sub(r"[\s\-\(\).]", "", phone)
    if re.match(r"^\+1\d{10}$", cleaned):
        return cleaned
    if re.match(r"^\d{10}$", cleaned):
        return f"+1{cleaned}"
    if re.match(r"^\+\d{10,15}$", cleaned):
        return cleaned
    raise ValueError(f"Invalid phone number: {phone}. Use E.164 format (e.g., +15551234567)")


def download_recording(recording_url: str) -> bytes:
    """Download a call recording from Twilio.

    Twilio recording URLs require authentication and .wav suffix.
    """
    url = f"{recording_url}.wav"
    with httpx.Client() as client:
        response = client.get(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.content
```

**Step 4: Run tests to verify they pass**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/test_twilio_service.py -v
```
Expected: All 6 tests pass.

**Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All 58 tests pass (52 existing + 6 new).

**Step 6: Commit**

```bash
git add backend/services/twilio_service.py backend/tests/test_twilio_service.py
git commit -m "feat: add Twilio service module with token generation and validation"
```

---

### Task 5: Create Twilio Webhook Router

**Files:**
- Create: `backend/routers/twilio_webhooks.py`
- Create: `backend/tests/test_twilio_webhooks.py`

**Context:** Twilio sends webhooks as POST requests with form-encoded data. These endpoints do NOT use JWT auth — instead they validate the `X-Twilio-Signature` header. When TWILIO_AUTH_TOKEN is empty (dev/test), signature validation is skipped.

**Step 1: Write the tests**

Create `backend/tests/test_twilio_webhooks.py`:

```python
"""Tests for Twilio webhook endpoints.

These test with TWILIO_AUTH_TOKEN="" so signature validation is skipped.
"""
import sys
from unittest.mock import MagicMock, patch

if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db, Call, User
from auth import hash_password, create_access_token
from main import app

TEST_DATABASE_URL = "sqlite:///./test_twilio.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
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
def worker(db):
    user = User(
        email="worker@test.com",
        hashed_password=hash_password("Worker123"),
        name="Test Worker",
        role="worker",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def twilio_call(db, worker):
    """A Call record that simulates a Twilio-initiated call."""
    call = Call(
        title="Test Twilio Call",
        source_type="twilio",
        status="connecting",
        uploaded_by=worker.id,
        call_direction="outbound",
        connection_mode="browser",
        patient_phone="+15551234567",
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def test_voice_webhook_returns_twiml(client, twilio_call):
    """Voice webhook returns valid TwiML with Dial verb."""
    response = client.post("/api/twilio/voice", data={
        "To": "+15551234567",
        "From": "+15559999999",
        "CallSid": "CA123456",
        "callId": str(twilio_call.id),
    })
    assert response.status_code == 200
    assert "text/xml" in response.headers["content-type"]
    body = response.text
    assert "<Dial" in body
    assert "+15551234567" in body
    assert "record" in body.lower()


def test_voice_webhook_updates_call_sid(client, twilio_call, db):
    """Voice webhook stores the Twilio CallSid on the Call record."""
    client.post("/api/twilio/voice", data={
        "To": "+15551234567",
        "From": "+15559999999",
        "CallSid": "CA_WEBHOOK_SID",
        "callId": str(twilio_call.id),
    })
    db.refresh(twilio_call)
    assert twilio_call.twilio_call_sid == "CA_WEBHOOK_SID"


def test_status_webhook_updates_call_status(client, twilio_call, db):
    """Status webhook updates call status based on Twilio event."""
    # Simulate 'in-progress' status
    client.post(f"/api/twilio/status?callId={twilio_call.id}", data={
        "CallSid": "CA123456",
        "CallStatus": "in-progress",
    })
    db.refresh(twilio_call)
    assert twilio_call.status == "in_progress"


def test_status_webhook_completed(client, twilio_call, db):
    """Status webhook sets status to 'processing' when call completes (awaiting recording)."""
    client.post(f"/api/twilio/status?callId={twilio_call.id}", data={
        "CallSid": "CA123456",
        "CallStatus": "completed",
    })
    db.refresh(twilio_call)
    # After call ends, status should be 'processing' (waiting for recording download)
    assert twilio_call.status == "processing"


def test_status_webhook_failed(client, twilio_call, db):
    """Status webhook sets status to 'failed' for failed/busy/no-answer."""
    client.post(f"/api/twilio/status?callId={twilio_call.id}", data={
        "CallSid": "CA123456",
        "CallStatus": "busy",
    })
    db.refresh(twilio_call)
    assert twilio_call.status == "failed"
    assert "busy" in twilio_call.error_message.lower()


def test_recording_webhook_triggers_download(client, twilio_call, db):
    """Recording webhook triggers recording download and pipeline."""
    with patch("routers.twilio_webhooks._download_and_process") as mock_process:
        client.post(f"/api/twilio/recording?callId={twilio_call.id}", data={
            "RecordingSid": "RE123456",
            "RecordingUrl": "https://api.twilio.com/recordings/RE123456",
            "RecordingDuration": "120",
            "CallSid": "CA123456",
            "RecordingStatus": "completed",
        })
        mock_process.assert_called_once()
        args = mock_process.call_args[0]
        assert args[0] == twilio_call.id
        assert "RE123456" in args[1]


def test_token_endpoint_requires_auth(client):
    """Token endpoint requires JWT authentication."""
    response = client.post("/api/twilio/token")
    assert response.status_code == 403
```

**Step 2: Run tests to verify they fail**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/test_twilio_webhooks.py -v
```
Expected: FAIL (module not found)

**Step 3: Create the webhook router**

Create `backend/routers/twilio_webhooks.py`:

```python
"""Twilio webhook and token endpoints.

Webhook endpoints receive form-encoded POST data from Twilio.
They validate the X-Twilio-Signature header instead of using JWT auth.
When TWILIO_AUTH_TOKEN is empty (dev/test), signature validation is skipped.
"""
import logging
import uuid
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse

from config import TWILIO_PHONE_NUMBER, TWILIO_WEBHOOK_BASE_URL, STORAGE_DIR
from database import get_db, Call, SessionLocal, User
from dependencies import get_current_user
from services.twilio_service import (
    generate_voice_token,
    validate_twilio_request,
    download_recording,
)
from services.pipeline import process_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


def _download_and_process(call_id: int, recording_url: str):
    """Background: download recording from Twilio, save it, run pipeline."""
    db = SessionLocal()
    try:
        logger.info("Downloading recording for call %d from %s", call_id, recording_url)
        audio_bytes = download_recording(recording_url)
        filename = f"{uuid.uuid4().hex}.wav"
        dest = STORAGE_DIR / filename
        dest.write_bytes(audio_bytes)

        call = db.query(Call).filter(Call.id == call_id).first()
        if not call:
            logger.error("Call %d not found after recording download", call_id)
            return
        call.audio_filename = filename
        call.status = "processing"
        db.commit()

        logger.info("Running pipeline for call %d", call_id)
        process_call(call_id, db)
    except Exception as e:
        logger.exception("Failed to download/process recording for call %d", call_id)
        call = db.query(Call).filter(Call.id == call_id).first()
        if call:
            call.status = "failed"
            call.error_message = f"Recording download failed: {e}"
            db.commit()
    finally:
        db.close()


@router.post("/voice")
async def handle_voice(request: Request, db: Session = Depends(get_db)):
    """Twilio voice webhook — returns TwiML to dial the patient and record.

    Called when:
    - Browser mode: Voice SDK connects and Twilio asks what to do
    - Phone mode: Worker answers their phone and Twilio asks what to do next
    """
    form = await request.form()
    params = dict(form)

    # Validate Twilio signature
    signature = request.headers.get("X-Twilio-Signature", "")
    if not validate_twilio_request(str(request.url), params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    to_number = params.get("To", "")
    call_sid = params.get("CallSid", "")
    call_id = params.get("callId") or request.query_params.get("callId")

    # Update our Call record with the Twilio CallSid
    if call_id:
        call = db.query(Call).filter(Call.id == int(call_id)).first()
        if call:
            call.twilio_call_sid = call_sid
            call.status = "connecting"
            db.commit()

    # Build TwiML response
    base_url = TWILIO_WEBHOOK_BASE_URL.rstrip("/")
    response = VoiceResponse()
    dial = response.dial(
        caller_id=TWILIO_PHONE_NUMBER,
        record="record-from-answer-dual",
        recording_status_callback=f"{base_url}/api/twilio/recording?callId={call_id}",
        recording_status_callback_event="completed",
    )
    dial.number(
        to_number,
        status_callback=f"{base_url}/api/twilio/status?callId={call_id}",
        status_callback_event="initiated ringing answered completed",
    )

    return Response(content=str(response), media_type="text/xml")


@router.post("/status")
async def handle_status(request: Request, db: Session = Depends(get_db)):
    """Twilio status callback — updates call status based on Twilio events."""
    form = await request.form()
    params = dict(form)

    signature = request.headers.get("X-Twilio-Signature", "")
    if not validate_twilio_request(str(request.url), params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    call_id = request.query_params.get("callId")
    call_status = params.get("CallStatus", "")

    if not call_id:
        return {"status": "ok"}

    call = db.query(Call).filter(Call.id == int(call_id)).first()
    if not call:
        return {"status": "ok"}

    # Map Twilio statuses to our statuses
    status_map = {
        "initiated": "connecting",
        "ringing": "connecting",
        "in-progress": "in_progress",
        "answered": "in_progress",
        "completed": "processing",  # Waiting for recording
    }
    failed_statuses = {"busy", "no-answer", "failed", "canceled"}

    if call_status in failed_statuses:
        call.status = "failed"
        call.error_message = f"Call {call_status}"
    elif call_status in status_map:
        call.status = status_map[call_status]

    db.commit()
    return {"status": "ok"}


@router.post("/recording")
async def handle_recording(request: Request, db: Session = Depends(get_db)):
    """Twilio recording callback — downloads recording and triggers pipeline."""
    form = await request.form()
    params = dict(form)

    signature = request.headers.get("X-Twilio-Signature", "")
    if not validate_twilio_request(str(request.url), params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    call_id = request.query_params.get("callId")
    recording_url = params.get("RecordingUrl", "")
    recording_duration = params.get("RecordingDuration")
    recording_status = params.get("RecordingStatus", "")

    if not call_id or not recording_url or recording_status != "completed":
        return {"status": "ok"}

    call = db.query(Call).filter(Call.id == int(call_id)).first()
    if not call:
        return {"status": "ok"}

    # Update duration from recording
    if recording_duration:
        call.duration = float(recording_duration)
        db.commit()

    # Download and process in background thread
    thread = Thread(target=_download_and_process, args=(call.id, recording_url))
    thread.start()

    return {"status": "ok"}


@router.post("/token")
async def get_voice_token(
    current_user: User = Depends(get_current_user),
):
    """Generate a Twilio Voice SDK access token for browser calling."""
    identity = f"user-{current_user.id}"
    token = generate_voice_token(identity)
    return {"token": token, "identity": identity}
```

**Step 4: Run tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/test_twilio_webhooks.py -v
```
Expected: All 8 tests pass.

**Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All 66 tests pass (52 + 6 + 8).

**Step 6: Commit**

```bash
git add backend/routers/twilio_webhooks.py backend/tests/test_twilio_webhooks.py
git commit -m "feat: add Twilio webhook router with voice, status, and recording handlers"
```

---

### Task 6: Create Dial Endpoint

**Files:**
- Create: `backend/tests/test_dial.py`
- Modify: `backend/routers/calls.py`

**Context:** The dial endpoint creates a Call record and, for phone mode, uses the Twilio REST API to initiate the call. For browser mode, it just returns the call_id — the frontend handles connection via the Voice SDK.

**Step 1: Write the tests**

Create `backend/tests/test_dial.py`:

```python
import sys
from unittest.mock import MagicMock, patch

if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db, Call, User
from auth import hash_password, create_access_token
from main import app

TEST_DATABASE_URL = "sqlite:///./test_dial.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
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
def worker(db):
    user = User(
        email="dialworker@test.com",
        hashed_password=hash_password("Worker123"),
        name="Dial Worker",
        role="worker",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def worker_headers(worker):
    token = create_access_token(worker.id)
    return {"Authorization": f"Bearer {token}"}


def test_dial_browser_mode_creates_call(client, worker_headers, db):
    """Dial in browser mode creates a Call record and returns call_id."""
    response = client.post("/api/calls/dial", json={
        "patient_phone": "+15551234567",
        "mode": "browser",
        "title": "Test Browser Call",
    }, headers=worker_headers)
    assert response.status_code == 200
    data = response.json()
    assert "call_id" in data
    assert data["status"] == "connecting"

    call = db.query(Call).filter(Call.id == data["call_id"]).first()
    assert call is not None
    assert call.source_type == "twilio"
    assert call.connection_mode == "browser"
    assert call.call_direction == "outbound"
    assert call.patient_phone == "+15551234567"


@patch("routers.calls.get_twilio_client")
def test_dial_phone_mode_creates_call_and_initiates(mock_get_client, client, worker_headers, db):
    """Dial in phone mode creates a Call and calls the Twilio REST API."""
    mock_client = MagicMock()
    mock_call = MagicMock()
    mock_call.sid = "CA_PHONE_TEST"
    mock_client.calls.create.return_value = mock_call
    mock_get_client.return_value = mock_client

    response = client.post("/api/calls/dial", json={
        "patient_phone": "+15551234567",
        "mode": "phone",
        "worker_phone": "+15559876543",
        "title": "Test Phone Call",
    }, headers=worker_headers)
    assert response.status_code == 200
    data = response.json()

    call = db.query(Call).filter(Call.id == data["call_id"]).first()
    assert call.connection_mode == "phone"
    assert call.twilio_call_sid == "CA_PHONE_TEST"
    mock_client.calls.create.assert_called_once()


def test_dial_requires_auth(client):
    """Dial endpoint requires authentication."""
    response = client.post("/api/calls/dial", json={
        "patient_phone": "+15551234567",
    })
    assert response.status_code == 403


def test_dial_rejects_invalid_phone(client, worker_headers):
    """Dial rejects invalid phone numbers."""
    response = client.post("/api/calls/dial", json={
        "patient_phone": "not-a-phone",
        "mode": "browser",
    }, headers=worker_headers)
    assert response.status_code == 400
    assert "phone" in response.json()["detail"].lower()


def test_dial_phone_mode_requires_worker_phone(client, worker_headers):
    """Phone mode requires worker_phone."""
    response = client.post("/api/calls/dial", json={
        "patient_phone": "+15551234567",
        "mode": "phone",
    }, headers=worker_headers)
    assert response.status_code == 400
    assert "worker_phone" in response.json()["detail"].lower()
```

**Step 2: Run tests to verify they fail**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/test_dial.py -v
```
Expected: FAIL

**Step 3: Add the dial endpoint to routers/calls.py**

Add these imports at the top of `backend/routers/calls.py`:

```python
from models.schemas import DialRequest, DialResponse
from services.twilio_service import get_twilio_client, validate_e164_phone
from services.audit import log_audit
from config import TWILIO_PHONE_NUMBER, TWILIO_WEBHOOK_BASE_URL
```

Then add this endpoint after the existing `list_calls` function (before `dashboard_stats`):

```python
@router.post("/dial", response_model=DialResponse)
def dial_call(
    req: DialRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initiate an outbound call via Twilio."""
    # Validate phone number
    try:
        patient_phone = validate_e164_phone(req.patient_phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if req.mode == "phone" and not req.worker_phone:
        raise HTTPException(status_code=400, detail="worker_phone is required for phone mode")

    if req.mode == "phone":
        try:
            worker_phone = validate_e164_phone(req.worker_phone)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Create Call record
    call = Call(
        title=req.title,
        source_type="twilio",
        status="connecting",
        uploaded_by=current_user.id,
        call_direction="outbound",
        patient_phone=patient_phone,
        connection_mode=req.mode,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    log_audit(db, current_user, "dial_call", request, "call", call.id,
              details={"patient_phone": patient_phone, "mode": req.mode})

    # For phone mode, use Twilio REST API to call the worker's phone
    if req.mode == "phone":
        base_url = TWILIO_WEBHOOK_BASE_URL.rstrip("/")
        try:
            twilio_client = get_twilio_client()
            twilio_call = twilio_client.calls.create(
                to=worker_phone,
                from_=TWILIO_PHONE_NUMBER,
                url=f"{base_url}/api/twilio/voice?callId={call.id}&To={patient_phone}",
                status_callback=f"{base_url}/api/twilio/status?callId={call.id}",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
            )
            call.twilio_call_sid = twilio_call.sid
            db.commit()
        except Exception as e:
            call.status = "failed"
            call.error_message = f"Failed to initiate call: {e}"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to initiate call: {e}")

    return DialResponse(call_id=call.id, status=call.status)
```

**Step 4: Run dial tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/test_dial.py -v
```
Expected: All 5 tests pass.

**Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All 71 tests pass.

**Step 6: Commit**

```bash
git add backend/routers/calls.py backend/tests/test_dial.py
git commit -m "feat: add dial endpoint for Twilio outbound calling"
```

---

### Task 7: Register Twilio Router and Remove Old WebRTC

**Files:**
- Modify: `backend/main.py`
- Delete: `backend/routers/webrtc.py`

**Step 1: Update main.py**

Replace the webrtc import with the twilio_webhooks import in `backend/main.py`:

Change:
```python
from routers import calls, upload, webrtc, auth, users, teams, audit
```
To:
```python
from routers import calls, upload, twilio_webhooks, auth, users, teams, audit
```

And replace:
```python
app.include_router(webrtc.router)
```
With:
```python
app.include_router(twilio_webhooks.router)
```

**Step 2: Delete the old WebRTC router**

```bash
rm /mnt/c/Users/ticta/workspace/call-monitor/backend/routers/webrtc.py
```

**Step 3: Run all tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/ -v
```
Expected: All 71 tests pass.

**Step 4: Commit**

```bash
git add backend/main.py
git rm backend/routers/webrtc.py
git commit -m "feat: register Twilio webhook router, remove old WebRTC scaffold"
```

---

### Task 8: Update CallSummary Construction in List/Stats

**Files:**
- Modify: `backend/routers/calls.py:39-57` (list_calls function)

**Context:** The `CallSummary` schema now includes `call_direction` and `connection_mode` fields. The `list_calls` function constructs `CallSummary` objects manually and needs to include these new fields.

**Step 1: Update list_calls in routers/calls.py**

In the `list_calls` function, update the `CallSummary` construction to include the new fields:

```python
        results.append(CallSummary(
            id=c.id,
            title=c.title,
            date=c.date,
            duration=c.duration,
            status=c.status,
            source_type=c.source_type,
            overall_sentiment=sentiment,
            overall_score=score,
            overall_rating=c.score.overall_rating if c.score else None,
            review_status=c.review.status if c.review else "unreviewed",
            call_direction=c.call_direction,
            connection_mode=c.connection_mode,
        ))
```

Also update `dashboard_stats` — the `recent_summaries` construction:

```python
        recent_summaries.append(CallSummary(
            id=c.id, title=c.title, date=c.date, duration=c.duration,
            status=c.status, source_type=c.source_type,
            overall_sentiment=sentiment, overall_score=score,
            overall_rating=c.score.overall_rating if c.score else None,
            review_status=c.review.status if c.review else "unreviewed",
            call_direction=c.call_direction,
            connection_mode=c.connection_mode,
        ))
```

**Step 2: Run all tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
python -m pytest tests/ -v
```
Expected: All 71 tests pass.

**Step 3: Commit**

```bash
git add backend/routers/calls.py
git commit -m "feat: include call_direction and connection_mode in call list responses"
```

---

### Task 9: Frontend — Install Twilio SDK and Add API Functions

**Files:**
- Modify: `frontend/package.json` (add @twilio/voice-sdk)
- Modify: `frontend/src/api/client.js` (add dialCall, getTwilioToken)

**Step 1: Add @twilio/voice-sdk to package.json**

This dependency must be installed from the Linux filesystem copy:

```bash
cd ~/workspace/call-monitor-frontend
npm install @twilio/voice-sdk
```

**Step 2: Add API functions to client.js**

Add these functions at the end of `frontend/src/api/client.js` (before `export default api`):

```javascript
// Twilio calling
export async function dialCall({ patient_phone, mode, worker_phone, title }) {
  const { data } = await api.post('/calls/dial', { patient_phone, mode, worker_phone, title })
  return data
}

export async function getTwilioToken() {
  const { data } = await api.post('/twilio/token')
  return data
}
```

**Step 3: Copy client.js to Linux filesystem**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/api/client.js ~/workspace/call-monitor-frontend/src/api/client.js
```

**Step 4: Commit**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor
git add frontend/src/api/client.js
git commit -m "feat: add dialCall and getTwilioToken API functions"
```

---

### Task 10: Frontend — Build CallDialer Component

**Files:**
- Create: `frontend/src/components/CallDialer.jsx`

**Context:** This is the main calling UI. Workers enter a phone number, choose browser or phone mode, and click Call. During a call, they see a timer and Hang Up button. After the call ends, they're navigated to the call detail page.

**Step 1: Create CallDialer.jsx**

Create `frontend/src/components/CallDialer.jsx`:

```jsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Device } from '@twilio/voice-sdk'
import { dialCall, getTwilioToken } from '../api/client'

function formatTimer(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export default function CallDialer() {
  const navigate = useNavigate()
  const [patientPhone, setPatientPhone] = useState('')
  const [workerPhone, setWorkerPhone] = useState('')
  const [title, setTitle] = useState('')
  const [mode, setMode] = useState('browser')
  const [callState, setCallState] = useState('idle') // idle, connecting, active, ended
  const [callId, setCallId] = useState(null)
  const [error, setError] = useState('')
  const [timer, setTimer] = useState(0)

  const deviceRef = useRef(null)
  const connectionRef = useRef(null)
  const timerRef = useRef(null)

  // Initialize Twilio Device for browser mode
  const initDevice = useCallback(async () => {
    try {
      const { token } = await getTwilioToken()
      const device = new Device(token, {
        codecPreferences: ['opus', 'pcmu'],
        logLevel: 'warn',
      })

      device.on('error', (err) => {
        console.error('Twilio Device error:', err)
        setError(`Device error: ${err.message}`)
        setCallState('idle')
      })

      deviceRef.current = device
    } catch (err) {
      console.error('Failed to init Twilio Device:', err)
      setError('Failed to initialize calling. Check Twilio configuration.')
    }
  }, [])

  useEffect(() => {
    initDevice()
    return () => {
      if (deviceRef.current) {
        deviceRef.current.destroy()
      }
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [initDevice])

  const startTimer = () => {
    setTimer(0)
    timerRef.current = setInterval(() => {
      setTimer((t) => t + 1)
    }, 1000)
  }

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const handleDial = async () => {
    setError('')
    setCallState('connecting')

    try {
      // Create the call record on the backend
      const data = await dialCall({
        patient_phone: patientPhone,
        mode,
        worker_phone: mode === 'phone' ? workerPhone : undefined,
        title: title || `Call to ${patientPhone}`,
      })
      setCallId(data.call_id)

      if (mode === 'browser') {
        // Connect via Twilio Voice SDK
        if (!deviceRef.current) {
          throw new Error('Twilio Device not initialized')
        }
        const call = await deviceRef.current.connect({
          params: {
            To: patientPhone,
            callId: String(data.call_id),
          },
        })

        call.on('accept', () => {
          setCallState('active')
          startTimer()
        })

        call.on('disconnect', () => {
          setCallState('ended')
          stopTimer()
        })

        call.on('cancel', () => {
          setCallState('idle')
          stopTimer()
        })

        call.on('error', (err) => {
          setError(`Call error: ${err.message}`)
          setCallState('idle')
          stopTimer()
        })

        connectionRef.current = call
      } else {
        // Phone mode: backend initiated the call, wait for it to connect
        setCallState('active')
        startTimer()
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to place call')
      setCallState('idle')
    }
  }

  const handleHangUp = () => {
    if (connectionRef.current) {
      connectionRef.current.disconnect()
    }
    stopTimer()
    setCallState('ended')
  }

  const handleViewCall = () => {
    if (callId) {
      navigate(`/calls/${callId}`)
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-6">Place a Call</h1>

      {callState === 'idle' && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Call Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Patient check-in"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Patient Phone Number</label>
            <input
              type="tel"
              value={patientPhone}
              onChange={(e) => setPatientPhone(e.target.value)}
              placeholder="+15551234567"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Connection Mode</label>
            <div className="flex gap-3">
              <button
                onClick={() => setMode('browser')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-medium transition ${
                  mode === 'browser'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="block text-lg mb-1">🎧</span>
                Browser
                <span className="block text-xs text-gray-500 mt-0.5">Use headset</span>
              </button>
              <button
                onClick={() => setMode('phone')}
                className={`flex-1 py-3 rounded-lg border-2 text-sm font-medium transition ${
                  mode === 'phone'
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="block text-lg mb-1">📱</span>
                Phone
                <span className="block text-xs text-gray-500 mt-0.5">Ring my phone</span>
              </button>
            </div>
          </div>

          {mode === 'phone' && (
            <div>
              <label className="block text-sm font-medium mb-1">Your Phone Number</label>
              <input
                type="tel"
                value={workerPhone}
                onChange={(e) => setWorkerPhone(e.target.value)}
                placeholder="+15559876543"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          )}

          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded text-sm">{error}</div>
          )}

          <button
            onClick={handleDial}
            disabled={!patientPhone || (mode === 'phone' && !workerPhone)}
            className="w-full bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-lg"
          >
            Call
          </button>
        </div>
      )}

      {callState === 'connecting' && (
        <div className="text-center py-12">
          <div className="animate-pulse text-6xl mb-4">📞</div>
          <p className="text-lg font-medium text-gray-700">Connecting...</p>
          <p className="text-sm text-gray-500 mt-1">{patientPhone}</p>
        </div>
      )}

      {callState === 'active' && (
        <div className="text-center py-8">
          <div className="text-6xl mb-4">🟢</div>
          <p className="text-3xl font-mono font-bold text-gray-800 mb-2">{formatTimer(timer)}</p>
          <p className="text-sm text-gray-500 mb-6">
            Connected to {patientPhone}
            <span className="ml-2 text-xs bg-gray-200 px-2 py-0.5 rounded">
              {mode === 'browser' ? 'Browser' : 'Phone'}
            </span>
          </p>
          <button
            onClick={handleHangUp}
            className="bg-red-600 text-white px-8 py-3 rounded-full font-medium hover:bg-red-700 text-lg"
          >
            Hang Up
          </button>
        </div>
      )}

      {callState === 'ended' && (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">✅</div>
          <p className="text-lg font-medium text-gray-700 mb-1">Call Ended</p>
          <p className="text-sm text-gray-500 mb-6">
            Duration: {formatTimer(timer)} — Recording is being processed
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={handleViewCall}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700"
            >
              View Call Details
            </button>
            <button
              onClick={() => {
                setCallState('idle')
                setPatientPhone('')
                setWorkerPhone('')
                setTitle('')
                setTimer(0)
                setCallId(null)
                setError('')
              }}
              className="border border-gray-300 px-6 py-2 rounded-lg font-medium hover:bg-gray-50"
            >
              New Call
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Copy to Linux filesystem**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/components/CallDialer.jsx ~/workspace/call-monitor-frontend/src/components/CallDialer.jsx
```

**Step 3: Commit**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor
git add frontend/src/components/CallDialer.jsx
git commit -m "feat: add CallDialer component for Twilio calling"
```

---

### Task 11: Frontend — Add Route and Navbar Link

**Files:**
- Modify: `frontend/src/App.jsx`

**Step 1: Import CallDialer and add route**

In `frontend/src/App.jsx`:

1. Add the import at the top with the other component imports:

```javascript
import CallDialer from './components/CallDialer'
```

2. In the Navbar component's nav links section, add a "Call" link after the "Upload" link:

```jsx
<Link to="/call" className="hover:text-indigo-200">Call</Link>
```

3. In the Routes section, add the route after the upload route:

```jsx
<Route path="/call" element={<ProtectedRoute><CallDialer /></ProtectedRoute>} />
```

**Step 2: Copy to Linux filesystem**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/App.jsx ~/workspace/call-monitor-frontend/src/App.jsx
```

**Step 3: Commit**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor
git add frontend/src/App.jsx
git commit -m "feat: add Call route and navbar link"
```

---

### Task 12: Frontend — Update CallDetail with Twilio Badges

**Files:**
- Modify: `frontend/src/components/CallDetail.jsx`

**Step 1: Add Twilio call info badges**

In the call detail header area of `CallDetail.jsx`, after the date/status/duration line (around line 76), add badges for Twilio calls:

```jsx
          <p className="text-sm text-gray-500">
            {new Date(call.date).toLocaleString()} &middot;{' '}
            <span className={statusColors[call.status]}>{call.status}</span>
            {call.duration && ` · ${formatTime(call.duration)}`}
            {call.source_type === 'twilio' && (
              <>
                {' · '}
                <span className="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded text-xs">
                  {call.call_direction || 'call'}
                </span>
                {call.connection_mode && (
                  <span className="bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded text-xs ml-1">
                    {call.connection_mode}
                  </span>
                )}
              </>
            )}
          </p>
```

Also add the `connecting` and `in_progress` statuses to the status colors map:

```javascript
  const statusColors = {
    pending: 'text-yellow-600',
    connecting: 'text-orange-600',
    in_progress: 'text-blue-600',
    processing: 'text-blue-600',
    completed: 'text-green-600',
    failed: 'text-red-600',
  }
```

And update the processing indicator to also show for `connecting` and `in_progress`:

```jsx
      {['pending', 'processing', 'connecting', 'in_progress'].includes(call.status) && (
```

**Step 2: Copy to Linux filesystem**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/components/CallDetail.jsx ~/workspace/call-monitor-frontend/src/components/CallDetail.jsx
```

**Step 3: Commit**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor
git add frontend/src/components/CallDetail.jsx
git commit -m "feat: add Twilio call badges to CallDetail component"
```

---

### Task 13: Remove Old WebRTC Component and Sync Frontend

**Files:**
- Delete: `frontend/src/components/WebRTCCall.jsx`

**Step 1: Delete old WebRTC component**

```bash
rm /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/components/WebRTCCall.jsx
rm -f ~/workspace/call-monitor-frontend/src/components/WebRTCCall.jsx
```

**Step 2: Full sync of frontend source to Linux filesystem**

```bash
rsync -av --delete \
  /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/ \
  ~/workspace/call-monitor-frontend/src/
```

**Step 3: Verify frontend builds**

```bash
cd ~/workspace/call-monitor-frontend
npx vite build
```
Expected: Build succeeds with no errors.

**Step 4: Commit**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor
git rm frontend/src/components/WebRTCCall.jsx
git commit -m "chore: remove old WebRTC scaffold, replaced by Twilio CallDialer"
```

---

### Task 14: Run All Backend Tests and Verify

**Files:** None (verification only)

**Step 1: Run full backend test suite**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
source ~/workspace/call-monitor-venv/bin/activate
python -m pytest tests/ -v
```
Expected: All 71 tests pass (52 original + 6 twilio service + 8 webhook + 5 dial).

**Step 2: Start backend and verify health**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
uvicorn main:app --reload &
curl http://localhost:8000/api/health
```
Expected: `{"status":"ok"}`

**Step 3: Start frontend and verify it loads**

```bash
cd ~/workspace/call-monitor-frontend
npx vite --host &
```
Expected: Frontend loads at http://localhost:5173. Login page shows. After login, navbar has "Call" link. Clicking "Call" shows the CallDialer component.

---

## Summary

| Task | Description | Tests Added |
|------|-------------|-------------|
| 1 | Twilio SDK + config | 0 |
| 2 | Call model fields + audit actions | 0 |
| 3 | Pydantic schemas | 0 |
| 4 | Twilio service module | 6 |
| 5 | Twilio webhook router | 8 |
| 6 | Dial endpoint | 5 |
| 7 | Register router, remove WebRTC | 0 |
| 8 | Update CallSummary construction | 0 |
| 9 | Frontend: SDK + API functions | 0 |
| 10 | Frontend: CallDialer component | 0 |
| 11 | Frontend: Route + navbar | 0 |
| 12 | Frontend: CallDetail badges | 0 |
| 13 | Remove WebRTC, sync frontend | 0 |
| 14 | Run all tests, verify | 0 |
| **Total** | | **19 new tests (71 total)** |

## To Test with Real Twilio

After completing all tasks, to test with a real Twilio account:

1. Sign up at https://twilio.com (free trial)
2. Buy a phone number
3. Create a TwiML App (Voice URL will be your ngrok URL + `/api/twilio/voice`)
4. Create an API Key
5. Install ngrok: `snap install ngrok` or download from https://ngrok.com
6. Run: `ngrok http 8000`
7. Update `backend/.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxx
   TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
   TWILIO_TWIML_APP_SID=APxxxxxxx
   TWILIO_API_KEY=SKxxxxxxx
   TWILIO_API_SECRET=xxxxxxx
   TWILIO_WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok-free.app
   ```
8. Update TwiML App Voice URL to match ngrok URL
9. Restart backend, test a call from the browser
