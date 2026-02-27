from unittest.mock import patch, MagicMock
from pathlib import Path
from database import Call, CallScore, TonalityResult, Transcript


def test_pipeline_stores_call_score(db):
    call = Call(title="Test", audio_filename="test.wav", status="pending")
    db.add(call)
    db.commit()

    mock_tx = {
        "full_text": "Hello, how are you?",
        "segments": [{"start": 0.0, "end": 2.0, "text": "Hello, how are you?"}],
        "duration": 2.0,
    }
    mock_tonality = {
        "overall_sentiment": "positive",
        "overall_score": 0.6,
        "sentiment_scores": [],
        "key_moments": [],
        "summary": "A greeting.",
        "tone_labels": ["friendly"],
        "rubric_scores": {
            "empathy": {"score": 7.5, "reasoning": "Good"},
            "professionalism": {"score": 8.0, "reasoning": "Clear"},
            "resolution": {"score": 6.0, "reasoning": "Partial"},
            "compliance": {"score": 9.0, "reasoning": "Fine"},
        },
    }

    mock_wav_path = MagicMock(spec=Path)
    mock_wav_path.exists.return_value = True

    with patch("services.pipeline.convert_to_wav", return_value=mock_wav_path), \
         patch("services.pipeline.transcribe_audio", return_value=mock_tx), \
         patch("services.pipeline.analyze_tonality", return_value=mock_tonality), \
         patch("services.pipeline.STORAGE_DIR", new_callable=lambda: MagicMock(spec=Path)) as mock_dir:

        mock_dir.__truediv__ = MagicMock(return_value=mock_wav_path)

        from services.pipeline import process_call
        process_call(call.id, db)

    db.refresh(call)
    assert call.status == "completed"
    assert call.score is not None
    assert call.score.empathy == 7.5
    assert call.score.professionalism == 8.0
    assert call.score.resolution == 6.0
    assert call.score.compliance == 9.0
    assert call.score.overall_rating == 7.62
    assert call.score.category_details["empathy"]["reasoning"] == "Good"


def test_pipeline_handles_missing_rubric(db):
    call = Call(title="Test", audio_filename="test.wav", status="pending")
    db.add(call)
    db.commit()

    mock_tx = {
        "full_text": "Hello",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}],
        "duration": 1.0,
    }
    mock_tonality = {
        "overall_sentiment": "neutral",
        "overall_score": 0.0,
        "sentiment_scores": [],
        "key_moments": [],
        "summary": "Short call.",
        "tone_labels": ["neutral"],
        "rubric_scores": None,
    }

    mock_wav_path = MagicMock(spec=Path)
    mock_wav_path.exists.return_value = True

    with patch("services.pipeline.convert_to_wav", return_value=mock_wav_path), \
         patch("services.pipeline.transcribe_audio", return_value=mock_tx), \
         patch("services.pipeline.analyze_tonality", return_value=mock_tonality), \
         patch("services.pipeline.STORAGE_DIR", new_callable=lambda: MagicMock(spec=Path)) as mock_dir:

        mock_dir.__truediv__ = MagicMock(return_value=mock_wav_path)

        from services.pipeline import process_call
        process_call(call.id, db)

    db.refresh(call)
    assert call.status == "completed"
    assert call.tonality is not None
    assert call.score is not None
    assert call.score.empathy is None
