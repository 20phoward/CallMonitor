import logging
from pathlib import Path

import whisper

from config import WHISPER_MODEL

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        logger.info("Loading Whisper model: %s", WHISPER_MODEL)
        _model = whisper.load_model(WHISPER_MODEL)
        logger.info("Whisper model loaded")
    return _model


def transcribe_audio(audio_path: Path) -> dict:
    """Transcribe an audio file using Whisper.

    Returns:
        dict with keys:
            - full_text: str
            - segments: list of {start, end, text}
            - duration: float (total seconds)
    """
    model = _get_model()
    logger.info("Transcribing: %s", audio_path)

    result = model.transcribe(
        str(audio_path),
        verbose=False,
        word_timestamps=False,
    )

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
            "speaker": None,  # basic: no diarization yet
        })

    duration = segments[-1]["end"] if segments else 0.0

    return {
        "full_text": result["text"].strip(),
        "segments": segments,
        "duration": duration,
    }


def merge_speaker_segments(
    worker_segments: list[dict],
    patient_segments: list[dict],
    worker_name: str,
    patient_name: str,
) -> list[dict]:
    """Merge two lists of transcript segments with speaker labels, sorted by start time.

    Args:
        worker_segments: list of {start, end, text} dicts from worker channel.
        patient_segments: list of {start, end, text} dicts from patient channel.
        worker_name: display name for the worker.
        patient_name: display name for the patient.

    Returns:
        list of {start, end, text, speaker} dicts sorted chronologically.
    """
    merged = []
    for seg in worker_segments:
        merged.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "speaker": worker_name,
        })
    for seg in patient_segments:
        merged.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "speaker": patient_name,
        })
    merged.sort(key=lambda s: s["start"])
    return merged
