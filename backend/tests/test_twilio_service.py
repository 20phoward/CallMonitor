"""Tests for services/twilio_service.py"""

import sys
from unittest.mock import patch, MagicMock

# Mock heavy/optional dependencies before any app imports
if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()

import pytest

from services.twilio_service import (
    generate_voice_token,
    validate_twilio_request,
    validate_e164_phone,
)


@patch("services.twilio_service.TWILIO_ACCOUNT_SID", "ACtest123")
@patch("services.twilio_service.TWILIO_API_KEY", "SKtest456")
@patch("services.twilio_service.TWILIO_API_SECRET", "secret789")
@patch("services.twilio_service.TWILIO_TWIML_APP_SID", "APtest000")
def test_generate_voice_token():
    token = generate_voice_token("user-1")
    assert isinstance(token, str)
    assert len(token) > 0


@patch("services.twilio_service.TWILIO_AUTH_TOKEN", "")
def test_validate_twilio_request_skips_when_no_auth_token():
    result = validate_twilio_request("http://example.com", {}, "sig")
    assert result is True


@patch("services.twilio_service.TWILIO_AUTH_TOKEN", "real-token")
@patch("services.twilio_service.RequestValidator")
def test_validate_twilio_request_validates_when_token_set(mock_validator_cls):
    mock_instance = MagicMock()
    mock_instance.validate.return_value = True
    mock_validator_cls.return_value = mock_instance

    result = validate_twilio_request("http://example.com", {"key": "val"}, "sig123")

    mock_validator_cls.assert_called_once_with("real-token")
    mock_instance.validate.assert_called_once_with("http://example.com", {"key": "val"}, "sig123")
    assert result is True


def test_validate_e164_phone_valid():
    assert validate_e164_phone("+15551234567") == "+15551234567"


def test_validate_e164_phone_invalid():
    with pytest.raises(ValueError):
        validate_e164_phone("not-a-phone")


def test_validate_e164_phone_auto_format():
    assert validate_e164_phone("5551234567") == "+15551234567"
