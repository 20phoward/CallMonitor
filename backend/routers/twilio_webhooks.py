"""Twilio webhook endpoints — voice, status, recording callbacks + token."""

import uuid
import logging
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from database import get_db, Call, SessionLocal, User
from models.schemas import TwilioTokenResponse
from config import STORAGE_DIR, TWILIO_WEBHOOK_BASE_URL
from dependencies import get_current_user
from services.twilio_service import (
    generate_voice_token,
    validate_twilio_request,
    download_recording,
)
from services.pipeline import process_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


def _validate_webhook(request: Request, params: dict):
    """Check X-Twilio-Signature for incoming webhooks."""
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not validate_twilio_request(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


def _download_and_process(call_id: int, recording_url: str):
    """Download a Twilio recording, save it, and run the processing pipeline.

    Runs in a separate thread with its own DB session.
    """
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.id == call_id).first()
        if not call:
            logger.error("Call %d not found for recording download", call_id)
            return

        # Download the recording as WAV
        wav_bytes = download_recording(recording_url)

        # Save to storage
        filename = f"{uuid.uuid4().hex}.wav"
        dest = STORAGE_DIR / filename
        dest.write_bytes(wav_bytes)

        call.audio_filename = filename
        db.commit()

        # Run the transcription + tonality pipeline
        process_call(call_id, db)

    except Exception as e:
        logger.exception("Download/process failed for call %d", call_id)
        call = db.query(Call).filter(Call.id == call_id).first()
        if call:
            call.status = "failed"
            call.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/voice")
async def voice_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio voice webhook — returns TwiML to dial the patient with recording."""
    params = dict(await request.form())
    _validate_webhook(request, params)

    call_id = params.get("callId") or request.query_params.get("callId")
    call_sid = params.get("CallSid", "")
    to_number = params.get("To", "")

    if call_id:
        call = db.query(Call).filter(Call.id == int(call_id)).first()
        if call:
            call.twilio_call_sid = call_sid
            db.commit()

    # Build TwiML response
    from twilio.twiml.voice_response import VoiceResponse

    response = VoiceResponse()
    dial = response.dial(
        record="record-from-answer-dual",
        recording_status_callback=f"{TWILIO_WEBHOOK_BASE_URL}/api/twilio/recording?callId={call_id}",
        recording_status_callback_event="completed",
    )
    dial.number(
        to_number,
        status_callback=f"{TWILIO_WEBHOOK_BASE_URL}/api/twilio/status?callId={call_id}",
        status_callback_event="initiated ringing answered completed",
    )

    return Response(content=str(response), media_type="text/xml")


@router.post("/status")
async def status_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio status callback — updates Call status based on Twilio CallStatus."""
    params = dict(await request.form())
    _validate_webhook(request, params)

    call_id = request.query_params.get("callId")
    if not call_id:
        return Response(content="<Response/>", media_type="text/xml")

    call = db.query(Call).filter(Call.id == int(call_id)).first()
    if not call:
        return Response(content="<Response/>", media_type="text/xml")

    call_status = params.get("CallStatus", "").lower()

    status_map = {
        "initiated": "connecting",
        "ringing": "connecting",
        "in-progress": "in_progress",
        "answered": "in_progress",
        "completed": "processing",
    }
    failed_statuses = {"failed", "busy", "no-answer", "canceled"}

    if call_status in status_map:
        call.status = status_map[call_status]
    elif call_status in failed_statuses:
        call.status = "failed"
        call.error_message = f"Call {call_status}"

    db.commit()
    return Response(content="<Response/>", media_type="text/xml")


@router.post("/recording")
async def recording_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio recording callback — downloads recording and triggers pipeline."""
    params = dict(await request.form())
    _validate_webhook(request, params)

    call_id = request.query_params.get("callId")
    recording_url = params.get("RecordingUrl", "")
    recording_status = params.get("RecordingStatus", "")

    if not call_id or not recording_url:
        return Response(content="<Response/>", media_type="text/xml")

    if recording_status != "completed":
        return Response(content="<Response/>", media_type="text/xml")

    # Launch download + processing in a background thread
    thread = Thread(
        target=_download_and_process,
        args=(int(call_id), recording_url),
        daemon=True,
    )
    thread.start()

    return Response(content="<Response/>", media_type="text/xml")


@router.post("/token", response_model=TwilioTokenResponse)
def get_token(
    current_user: User = Depends(get_current_user),
):
    """Generate a Twilio Voice SDK access token for the current user."""
    identity = f"user-{current_user.id}"
    token = generate_voice_token(identity)
    return TwilioTokenResponse(token=token, identity=identity)
