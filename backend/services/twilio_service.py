"""Twilio integration service — client, tokens, validation, downloads."""

import re
import logging

import httpx
from twilio.rest import Client
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.request_validator import RequestValidator

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_API_KEY,
    TWILIO_API_SECRET,
    TWILIO_TWIML_APP_SID,
)

logger = logging.getLogger(__name__)

# E.164 pattern: optional +, country code, subscriber number (total 10-15 digits)
_E164_RE = re.compile(r"^\+1\d{10}$")
_US_10_DIGIT_RE = re.compile(r"^\d{10}$")


def get_twilio_client() -> Client:
    """Return an authenticated Twilio REST client."""
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def generate_voice_token(identity: str) -> str:
    """Create a Twilio Access Token with a Voice grant for the JS SDK."""
    token = AccessToken(
        TWILIO_ACCOUNT_SID,
        TWILIO_API_KEY,
        TWILIO_API_SECRET,
        identity=identity,
    )
    voice_grant = VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=True,
    )
    token.add_grant(voice_grant)
    return token.to_jwt()


def validate_twilio_request(url: str, params: dict, signature: str) -> bool:
    """Validate X-Twilio-Signature. Skips validation (returns True) when
    TWILIO_AUTH_TOKEN is empty (dev/test mode)."""
    if not TWILIO_AUTH_TOKEN:
        return True
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    return validator.validate(url, params, signature)


def validate_e164_phone(phone: str) -> str:
    """Validate and normalise a phone number to E.164 format (+15551234567).

    Accepts:
      - Already-formatted E.164 US numbers (+1XXXXXXXXXX)
      - 10-digit US numbers (auto-prepends +1)

    Raises ValueError for anything else.
    """
    phone = phone.strip()
    if _US_10_DIGIT_RE.match(phone):
        phone = f"+1{phone}"
    if not _E164_RE.match(phone):
        raise ValueError(f"Invalid phone number: {phone}")
    return phone


def download_recording(recording_url: str) -> bytes:
    """Download a Twilio recording as WAV bytes.

    Appends .wav to the recording URL and authenticates with
    Twilio account SID / auth token via HTTP Basic Auth.
    """
    url = f"{recording_url}.wav"
    response = httpx.get(
        url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        follow_redirects=True,
        timeout=120,
    )
    response.raise_for_status()
    return response.content
