"""Tests for speaker diarization: patient_name, stereo splitting, segment merging, pipeline."""

import struct
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

from database import Call, User
from models.schemas import DialRequest
from services.transcription import merge_speaker_segments


def _make_stereo_wav(path: Path, duration_secs: float = 0.5, sample_rate: int = 16000):
    """Create a minimal stereo WAV file using the wave and struct modules."""
    num_frames = int(sample_rate * duration_secs)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        # Write silent stereo frames (left=0, right=0)
        for _ in range(num_frames):
            wf.writeframes(struct.pack("<hh", 0, 0))


def _make_mono_wav(path: Path, duration_secs: float = 0.5, sample_rate: int = 16000):
    """Create a minimal mono WAV file."""
    num_frames = int(sample_rate * duration_secs)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for _ in range(num_frames):
            wf.writeframes(struct.pack("<h", 0))


# --- Test 1: DialRequest accepts patient_name ---

def test_dial_request_accepts_patient_name():
    req = DialRequest(
        patient_phone="+15551234567",
        mode="browser",
        title="Test Call",
        patient_name="John Doe",
    )
    assert req.patient_name == "John Doe"


# --- Test 2: DialRequest defaults patient_name to None ---

def test_dial_request_defaults_patient_name_to_none():
    req = DialRequest(
        patient_phone="+15551234567",
        mode="browser",
    )
    assert req.patient_name is None


# --- Test 3: Call model stores patient_name ---

def test_call_model_stores_patient_name(db):
    call = Call(
        title="Test Call",
        audio_filename="test.wav",
        status="pending",
        source_type="twilio",
        patient_name="Jane Smith",
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    fetched = db.query(Call).filter(Call.id == call.id).first()
    assert fetched.patient_name == "Jane Smith"


# --- Test 4: split_stereo_channels produces two mono WAVs ---

def test_split_stereo_channels_produces_mono_wavs():
    with tempfile.TemporaryDirectory() as tmpdir:
        stereo_path = Path(tmpdir) / "test_stereo.wav"
        _make_stereo_wav(stereo_path)

        from services.pipeline import split_stereo_channels
        ch1_path, ch2_path = split_stereo_channels(stereo_path)

        assert ch1_path.exists()
        assert ch2_path.exists()

        # Verify both are mono
        with wave.open(str(ch1_path), "rb") as wf:
            assert wf.getnchannels() == 1
        with wave.open(str(ch2_path), "rb") as wf:
            assert wf.getnchannels() == 1

        # Verify naming convention
        assert ch1_path.name == "test_stereo_ch1.wav"
        assert ch2_path.name == "test_stereo_ch2.wav"


# --- Test 5: merge_speaker_segments interleaves and labels correctly ---

def test_merge_speaker_segments_interleaves_and_labels():
    worker_segments = [
        {"start": 0.0, "end": 2.0, "text": "Hello, how are you?"},
        {"start": 5.0, "end": 7.0, "text": "That sounds good."},
    ]
    patient_segments = [
        {"start": 2.5, "end": 4.5, "text": "I am doing well, thanks."},
        {"start": 7.5, "end": 9.0, "text": "Thank you for calling."},
    ]

    merged = merge_speaker_segments(worker_segments, patient_segments, "Alice", "Bob")

    assert len(merged) == 4

    # Check chronological order
    for i in range(len(merged) - 1):
        assert merged[i]["start"] <= merged[i + 1]["start"]

    # Check speaker labels
    assert merged[0]["speaker"] == "Alice"
    assert merged[0]["text"] == "Hello, how are you?"
    assert merged[1]["speaker"] == "Bob"
    assert merged[1]["text"] == "I am doing well, thanks."
    assert merged[2]["speaker"] == "Alice"
    assert merged[2]["text"] == "That sounds good."
    assert merged[3]["speaker"] == "Bob"
    assert merged[3]["text"] == "Thank you for calling."


# --- Test 6: process_call for Twilio stereo produces speaker-labeled segments ---

def test_process_call_twilio_stereo_diarization(db):
    """Twilio stereo calls should produce speaker-labeled transcript segments."""
    # Create a worker user
    from auth import hash_password
    worker = User(
        email="diar_worker@test.com",
        hashed_password=hash_password("Worker123"),
        name="Test Worker",
        role="worker",
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)

    # Create a Twilio call
    call = Call(
        title="Twilio Stereo Test",
        audio_filename="stereo_test.wav",
        status="pending",
        source_type="twilio",
        uploaded_by=worker.id,
        patient_name="Test Patient",
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    mock_worker_tx = {
        "full_text": "Hello, how are you?",
        "segments": [{"start": 0.0, "end": 2.0, "text": "Hello, how are you?", "speaker": None}],
        "duration": 2.0,
    }
    mock_patient_tx = {
        "full_text": "I am fine, thanks.",
        "segments": [{"start": 1.0, "end": 3.0, "text": "I am fine, thanks.", "speaker": None}],
        "duration": 3.0,
    }
    mock_tonality = {
        "overall_sentiment": "positive",
        "overall_score": 0.5,
        "sentiment_scores": [],
        "key_moments": [],
        "summary": "A greeting.",
        "tone_labels": ["friendly"],
        "rubric_scores": None,
    }

    mock_wav_path = MagicMock(spec=Path)
    mock_wav_path.exists.return_value = True
    mock_wav_path.suffix = ".wav"

    mock_ch1 = MagicMock(spec=Path)
    mock_ch2 = MagicMock(spec=Path)

    # transcribe_audio is called twice: once for ch1, once for ch2
    transcribe_side_effect = [mock_worker_tx, mock_patient_tx]

    with patch("services.pipeline.convert_to_wav", return_value=mock_wav_path), \
         patch("services.pipeline._is_stereo", return_value=True), \
         patch("services.pipeline.split_stereo_channels", return_value=(mock_ch1, mock_ch2)), \
         patch("services.pipeline.transcribe_audio", side_effect=transcribe_side_effect), \
         patch("services.pipeline.analyze_tonality", return_value=mock_tonality), \
         patch("services.pipeline.STORAGE_DIR", new_callable=lambda: MagicMock(spec=Path)) as mock_dir:

        mock_dir.__truediv__ = MagicMock(return_value=mock_wav_path)

        from services.pipeline import process_call
        process_call(call.id, db)

    db.refresh(call)
    assert call.status == "completed"
    assert call.duration == 3.0  # max of worker (2.0) and patient (3.0)

    # Verify transcript has speaker labels
    assert call.transcript is not None
    segments = call.transcript.segments
    assert len(segments) == 2
    assert segments[0]["speaker"] == "Test Worker"
    assert segments[1]["speaker"] == "Test Patient"

    # Verify full_text is speaker-labeled
    assert "Test Worker:" in call.transcript.full_text
    assert "Test Patient:" in call.transcript.full_text

    # Verify channel files were cleaned up
    mock_ch1.unlink.assert_called_once()
    mock_ch2.unlink.assert_called_once()
