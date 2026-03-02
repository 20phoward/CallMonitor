import logging
import subprocess
import wave
from pathlib import Path

from sqlalchemy.orm import Session

from config import STORAGE_DIR
from database import Call, Transcript, TonalityResult, CallScore, User
from services.transcription import transcribe_audio, merge_speaker_segments
from services.tonality import analyze_tonality

logger = logging.getLogger(__name__)


def convert_to_wav(input_path: Path) -> Path:
    """Convert any audio file to 16kHz mono WAV for Whisper."""
    wav_path = input_path.with_suffix(".wav")
    if input_path.suffix.lower() == ".wav":
        return input_path
    logger.info("Converting %s → %s", input_path.name, wav_path.name)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path),
        ],
        capture_output=True,
        check=True,
    )
    return wav_path


def _is_stereo(wav_path: Path) -> bool:
    """Check if a WAV file has 2 channels (stereo)."""
    with wave.open(str(wav_path), "rb") as wf:
        return wf.getnchannels() == 2


def split_stereo_channels(wav_path: Path) -> tuple[Path, Path]:
    """Split a stereo WAV into two mono channel files.

    Left channel (ch1) = worker, Right channel (ch2) = patient.
    Returns (ch1_path, ch2_path).
    """
    stem = wav_path.stem
    parent = wav_path.parent
    ch1_path = parent / f"{stem}_ch1.wav"
    ch2_path = parent / f"{stem}_ch2.wav"

    logger.info("Splitting stereo %s → ch1 + ch2", wav_path.name)

    # Extract left channel
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(wav_path),
            "-af", "pan=mono|c0=FL",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(ch1_path),
        ],
        capture_output=True,
        check=True,
    )

    # Extract right channel
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(wav_path),
            "-af", "pan=mono|c0=FR",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(ch2_path),
        ],
        capture_output=True,
        check=True,
    )

    return ch1_path, ch2_path


def process_call(call_id: int, db: Session):
    """Full processing pipeline: transcode → transcribe → analyze → store."""
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        logger.error("Call %d not found", call_id)
        return

    try:
        # --- Update status ---
        call.status = "processing"
        db.commit()

        audio_path = STORAGE_DIR / call.audio_filename
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # --- Transcode ---
        wav_path = convert_to_wav(audio_path)

        # --- Transcribe (dual-channel for Twilio stereo, mono otherwise) ---
        logger.info("Transcribing call %d", call_id)

        use_diarization = (
            call.source_type == "twilio"
            and wav_path.suffix.lower() == ".wav"
            and _is_stereo(wav_path)
        )

        if use_diarization:
            # Split stereo into per-speaker channels
            ch1_path, ch2_path = split_stereo_channels(wav_path)
            try:
                worker_result = transcribe_audio(ch1_path)
                patient_result = transcribe_audio(ch2_path)

                # Look up speaker names
                worker_name = "Worker"
                if call.uploaded_by:
                    uploader = db.query(User).filter(User.id == call.uploaded_by).first()
                    if uploader and uploader.name:
                        worker_name = uploader.name
                patient_name = call.patient_name or "Patient"

                # Merge segments with speaker labels
                merged_segments = merge_speaker_segments(
                    worker_result["segments"],
                    patient_result["segments"],
                    worker_name,
                    patient_name,
                )

                # Build speaker-labeled full text
                full_text = "\n".join(
                    f"{seg['speaker']}: {seg['text']}" for seg in merged_segments
                )
                duration = max(worker_result["duration"], patient_result["duration"])

                tx_result = {
                    "full_text": full_text,
                    "segments": merged_segments,
                    "duration": duration,
                }
            finally:
                # Clean up split channel files
                for p in (ch1_path, ch2_path):
                    try:
                        p.unlink()
                    except OSError:
                        pass
        else:
            tx_result = transcribe_audio(wav_path)

        transcript = Transcript(
            call_id=call_id,
            full_text=tx_result["full_text"],
            segments=tx_result["segments"],
        )
        db.add(transcript)
        call.duration = tx_result["duration"]
        db.commit()

        # --- Tonality analysis ---
        logger.info("Analyzing tonality for call %d", call_id)
        ton_result = analyze_tonality(tx_result["full_text"], tx_result["segments"])

        tonality = TonalityResult(
            call_id=call_id,
            overall_sentiment=ton_result["overall_sentiment"],
            overall_score=ton_result["overall_score"],
            sentiment_scores=ton_result["sentiment_scores"],
            key_moments=ton_result["key_moments"],
            summary=ton_result["summary"],
            tone_labels=ton_result["tone_labels"],
        )
        db.add(tonality)

        # --- Rubric scoring ---
        rubric = ton_result.get("rubric_scores")
        score_kwargs = {"call_id": call_id}
        if rubric:
            score_kwargs.update({
                "empathy": rubric["empathy"]["score"],
                "professionalism": rubric["professionalism"]["score"],
                "resolution": rubric["resolution"]["score"],
                "compliance": rubric["compliance"]["score"],
                "overall_rating": round(sum(
                    rubric[k]["score"] for k in ("empathy", "professionalism", "resolution", "compliance")
                ) / 4, 2),
                "category_details": {k: {"reasoning": v["reasoning"]} for k, v in rubric.items()},
            })
        call_score = CallScore(**score_kwargs)
        db.add(call_score)

        call.status = "completed"
        db.commit()
        logger.info("Call %d processing completed", call_id)

    except Exception as e:
        logger.exception("Processing failed for call %d", call_id)
        call.status = "failed"
        call.error_message = str(e)
        db.commit()
