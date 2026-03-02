# Speaker Diarization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Label Twilio call transcript segments with speaker names (worker vs patient) using dual-channel audio splitting.

**Architecture:** Twilio's `record-from-answer-dual` produces stereo WAV (left=worker, right=patient). We split with ffmpeg into two mono files, transcribe each with Whisper independently, merge segments chronologically with speaker labels, and pass labeled transcript to Claude for tonality. The Call model gets a `patient_name` field, the dial form gets a name input, and the transcript UI shows colored speaker labels.

**Tech Stack:** ffmpeg (channel splitting), Whisper (transcription), existing FastAPI + React stack

---

### Task 1: Add patient_name to data model and API

**Files:**
- Modify: `backend/database.py` — add `patient_name` column to Call
- Modify: `backend/models/schemas.py` — add `patient_name` to DialRequest and CallResponse
- Modify: `backend/routers/calls.py` — pass `patient_name` when creating Call
- Test: `backend/tests/test_diarization.py`

**Step 1: Write the failing test**

Create `backend/tests/test_diarization.py`:

```python
"""Tests for speaker diarization feature."""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine, Call, User
from auth import hash_password

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(User).delete()
    db.query(Call).delete()
    db.commit()
    user = User(
        email="test@example.com",
        hashed_password=hash_password("Test1234"),
        name="Test Worker",
        role="admin",
    )
    db.add(user)
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Call).delete()
    db.query(User).delete()
    db.commit()
    db.close()


def get_auth_headers():
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "Test1234"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_dial_request_accepts_patient_name():
    """DialRequest should accept an optional patient_name field."""
    from models.schemas import DialRequest
    req = DialRequest(patient_phone="+15551234567", patient_name="Lionel", title="Test Call")
    assert req.patient_name == "Lionel"


def test_dial_request_patient_name_defaults_none():
    """patient_name should default to None if not provided."""
    from models.schemas import DialRequest
    req = DialRequest(patient_phone="+15551234567")
    assert req.patient_name is None


def test_call_model_has_patient_name():
    """Call model should have a patient_name column."""
    db = SessionLocal()
    call = Call(title="Test", patient_name="Lionel", source_type="twilio")
    db.add(call)
    db.commit()
    db.refresh(call)
    assert call.patient_name == "Lionel"
    db.delete(call)
    db.commit()
    db.close()
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && source ~/workspace/call-monitor-venv/bin/activate && python3 -m pytest tests/test_diarization.py -v`

Expected: FAIL — `patient_name` doesn't exist on Call model or DialRequest

**Step 3: Implement the changes**

In `backend/database.py`, add after `connection_mode` column (around line 102):

```python
patient_name = Column(String, nullable=True)
```

In `backend/models/schemas.py`, add to `DialRequest` (around line 84):

```python
patient_name: Optional[str] = None
```

In `backend/routers/calls.py`, in `dial_call()`, update the Call creation (around line 95-102) to include:

```python
patient_name=req.patient_name,
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_diarization.py -v`
Expected: 3 PASS

**Important:** Since we added a column to Call, delete `calls.db` to recreate the schema:
```bash
rm -f /mnt/c/Users/ticta/workspace/call-monitor/backend/calls.db
```

**Step 5: Commit**

```bash
git add backend/database.py backend/models/schemas.py backend/routers/calls.py backend/tests/test_diarization.py
git commit -m "feat: add patient_name to Call model and DialRequest"
```

---

### Task 2: Dual-channel audio splitting

**Files:**
- Modify: `backend/services/pipeline.py` — add `split_stereo_channels()` function
- Test: `backend/tests/test_diarization.py` — add split test

**Step 1: Write the failing test**

Add to `backend/tests/test_diarization.py`:

```python
import subprocess
import struct
import wave
from pathlib import Path
from services.pipeline import split_stereo_channels


def _create_stereo_wav(path: Path, duration_sec=1, sample_rate=16000):
    """Create a minimal stereo WAV file for testing."""
    n_samples = sample_rate * duration_sec
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            # Left channel: 440Hz tone, Right channel: 880Hz tone
            left = int(16000 * __import__('math').sin(2 * 3.14159 * 440 * i / sample_rate))
            right = int(16000 * __import__('math').sin(2 * 3.14159 * 880 * i / sample_rate))
            wf.writeframes(struct.pack("<hh", left, right))


def test_split_stereo_channels(tmp_path):
    """split_stereo_channels should produce two mono WAV files."""
    stereo = tmp_path / "stereo.wav"
    _create_stereo_wav(stereo)

    left, right = split_stereo_channels(stereo)

    assert left.exists()
    assert right.exists()
    assert left.name == "stereo_ch1.wav"
    assert right.name == "stereo_ch2.wav"

    # Verify both are mono
    with wave.open(str(left)) as wf:
        assert wf.getnchannels() == 1
    with wave.open(str(right)) as wf:
        assert wf.getnchannels() == 1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_diarization.py::test_split_stereo_channels -v`
Expected: FAIL — `split_stereo_channels` not defined

**Step 3: Implement split_stereo_channels**

Add to `backend/services/pipeline.py` after `convert_to_wav()`:

```python
def split_stereo_channels(wav_path: Path) -> tuple[Path, Path]:
    """Split a stereo WAV into two mono WAV files (left=ch1, right=ch2).

    Returns (ch1_path, ch2_path).
    """
    stem = wav_path.stem
    parent = wav_path.parent
    ch1_path = parent / f"{stem}_ch1.wav"
    ch2_path = parent / f"{stem}_ch2.wav"

    # Extract left channel
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(wav_path),
            "-af", "pan=mono|c0=FL",
            "-ar", "16000", "-c:a", "pcm_s16le",
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
            "-ar", "16000", "-c:a", "pcm_s16le",
            str(ch2_path),
        ],
        capture_output=True,
        check=True,
    )

    return ch1_path, ch2_path
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_diarization.py::test_split_stereo_channels -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/services/pipeline.py backend/tests/test_diarization.py
git commit -m "feat: add stereo-to-mono channel splitting"
```

---

### Task 3: Dual-channel transcription and segment merging

**Files:**
- Modify: `backend/services/transcription.py` — add `transcribe_dual_channel()`
- Test: `backend/tests/test_diarization.py` — add merge test

**Step 1: Write the failing test**

Add to `backend/tests/test_diarization.py`:

```python
from services.transcription import merge_speaker_segments


def test_merge_speaker_segments_interleaves():
    """Segments from two speakers should be merged chronologically."""
    worker_segs = [
        {"start": 0.0, "end": 2.5, "text": "Hello, how are you?"},
        {"start": 5.0, "end": 7.0, "text": "That's great to hear."},
    ]
    patient_segs = [
        {"start": 2.5, "end": 5.0, "text": "I'm doing much better."},
        {"start": 7.5, "end": 9.0, "text": "Thank you."},
    ]

    merged = merge_speaker_segments(worker_segs, patient_segs, "Patrick", "Lionel")

    assert len(merged) == 4
    assert merged[0]["speaker"] == "Patrick"
    assert merged[0]["text"] == "Hello, how are you?"
    assert merged[1]["speaker"] == "Lionel"
    assert merged[1]["text"] == "I'm doing much better."
    assert merged[2]["speaker"] == "Patrick"
    assert merged[3]["speaker"] == "Lionel"


def test_merge_speaker_segments_builds_full_text():
    """Merged result should include labeled full_text."""
    worker_segs = [{"start": 0.0, "end": 2.0, "text": "Hi there."}]
    patient_segs = [{"start": 2.0, "end": 4.0, "text": "Hello."}]

    merged = merge_speaker_segments(worker_segs, patient_segs, "Patrick", "Lionel")
    full_text = "\n".join(f'{s["speaker"]}: {s["text"]}' for s in merged)

    assert "Patrick: Hi there." in full_text
    assert "Lionel: Hello." in full_text
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_diarization.py::test_merge_speaker_segments_interleaves tests/test_diarization.py::test_merge_speaker_segments_builds_full_text -v`
Expected: FAIL — `merge_speaker_segments` not defined

**Step 3: Implement merge_speaker_segments**

Add to `backend/services/transcription.py`:

```python
def merge_speaker_segments(
    worker_segments: list[dict],
    patient_segments: list[dict],
    worker_name: str,
    patient_name: str,
) -> list[dict]:
    """Merge two lists of transcript segments, sorted by start time, with speaker labels."""
    labeled = []
    for seg in worker_segments:
        labeled.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "speaker": worker_name,
        })
    for seg in patient_segments:
        labeled.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "speaker": patient_name,
        })

    labeled.sort(key=lambda s: s["start"])
    return labeled
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_diarization.py::test_merge_speaker_segments_interleaves tests/test_diarization.py::test_merge_speaker_segments_builds_full_text -v`
Expected: 2 PASS

**Step 5: Commit**

```bash
git add backend/services/transcription.py backend/tests/test_diarization.py
git commit -m "feat: add speaker segment merging for dual-channel transcription"
```

---

### Task 4: Update pipeline to use dual-channel for Twilio calls

**Files:**
- Modify: `backend/services/pipeline.py` — update `process_call()` to detect Twilio calls and use dual-channel flow
- Test: `backend/tests/test_diarization.py` — integration-style test

**Step 1: Write the failing test**

Add to `backend/tests/test_diarization.py`:

```python
import wave
import struct
import math
from unittest.mock import patch, MagicMock
from services.pipeline import process_call


def _create_stereo_wav_file(path, duration_sec=2, sample_rate=16000):
    """Create a stereo WAV with different tones per channel."""
    n_samples = sample_rate * duration_sec
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            left = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            right = int(16000 * math.sin(2 * math.pi * 880 * i / sample_rate))
            wf.writeframes(struct.pack("<hh", left, right))


def test_process_call_twilio_uses_dual_channel(tmp_path):
    """Twilio calls should split stereo audio and produce speaker-labeled segments."""
    db = SessionLocal()

    # Create a Twilio call with patient_name
    call = Call(
        title="Test Twilio Call",
        source_type="twilio",
        status="processing",
        audio_filename="test_stereo.wav",
        uploaded_by=1,
        patient_name="Lionel",
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    # Create stereo WAV in storage dir
    from config import STORAGE_DIR
    audio_path = STORAGE_DIR / "test_stereo.wav"
    _create_stereo_wav_file(audio_path)

    # Mock Whisper to return fake transcription
    fake_result = {
        "text": "Test segment.",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Test segment."}],
    }
    with patch("services.transcription._get_model") as mock_model:
        model_instance = MagicMock()
        model_instance.transcribe.return_value = fake_result
        mock_model.return_value = model_instance

        with patch("services.tonality.analyze_tonality") as mock_tonality:
            mock_tonality.return_value = {
                "overall_sentiment": "neutral",
                "overall_score": 0.0,
                "sentiment_scores": [],
                "key_moments": [],
                "summary": "Test.",
                "tone_labels": ["neutral"],
                "rubric_scores": {
                    "empathy": {"score": 5.0, "reasoning": "ok"},
                    "professionalism": {"score": 5.0, "reasoning": "ok"},
                    "resolution": {"score": 5.0, "reasoning": "ok"},
                    "compliance": {"score": 5.0, "reasoning": "ok"},
                },
            }

            process_call(call.id, db)

    db.refresh(call)
    assert call.status == "completed"

    # Verify transcript has speaker labels
    from database import Transcript
    transcript = db.query(Transcript).filter(Transcript.call_id == call.id).first()
    assert transcript is not None
    assert len(transcript.segments) > 0

    # At least one segment should have a speaker label
    speakers = [s.get("speaker") for s in transcript.segments]
    assert any(s is not None for s in speakers)

    # Clean up
    for f in STORAGE_DIR.glob("test_stereo*"):
        f.unlink()
    db.delete(transcript)
    db.delete(call)
    db.commit()
    db.close()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_diarization.py::test_process_call_twilio_uses_dual_channel -v`
Expected: FAIL — pipeline doesn't do dual-channel yet

**Step 3: Update process_call in pipeline.py**

Replace the transcription section of `process_call()` in `backend/services/pipeline.py`. The full updated function:

```python
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

        # --- Transcribe ---
        logger.info("Transcribing call %d", call_id)

        if call.source_type == "twilio" and _is_stereo(wav_path):
            # Dual-channel: split and transcribe each channel
            from services.transcription import merge_speaker_segments
            ch1_path, ch2_path = split_stereo_channels(wav_path)

            worker_result = transcribe_audio(ch1_path)
            patient_result = transcribe_audio(ch2_path)

            # Get speaker names
            worker_name = "Worker"
            if call.uploaded_by:
                from database import User
                uploader = db.query(User).filter(User.id == call.uploaded_by).first()
                if uploader:
                    worker_name = uploader.name
            patient_name = call.patient_name or "Patient"

            # Merge segments with speaker labels
            merged_segments = merge_speaker_segments(
                worker_result["segments"],
                patient_result["segments"],
                worker_name,
                patient_name,
            )

            full_text = "\n".join(f'{s["speaker"]}: {s["text"]}' for s in merged_segments)
            duration = max(
                worker_result["duration"],
                patient_result["duration"],
            )

            tx_result = {
                "full_text": full_text,
                "segments": merged_segments,
                "duration": duration,
            }

            # Clean up split files
            ch1_path.unlink(missing_ok=True)
            ch2_path.unlink(missing_ok=True)
        else:
            # Mono: standard transcription
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
```

Also add this helper to `pipeline.py`:

```python
def _is_stereo(wav_path: Path) -> bool:
    """Check if a WAV file has 2 channels."""
    import wave
    try:
        with wave.open(str(wav_path)) as wf:
            return wf.getnchannels() == 2
    except Exception:
        return False
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_diarization.py::test_process_call_twilio_uses_dual_channel -v`
Expected: PASS

**Step 5: Run all tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests pass (existing + new)

**Step 6: Commit**

```bash
git add backend/services/pipeline.py backend/tests/test_diarization.py
git commit -m "feat: dual-channel transcription pipeline for Twilio calls"
```

---

### Task 5: Frontend — add patient name to dial form

**Files:**
- Modify: `frontend/src/components/CallDialer.jsx` — add patient name input
- Modify: `frontend/src/api/client.js` — pass `patient_name` in dialCall

**Step 1: Update api/client.js**

In `frontend/src/api/client.js`, update the `dialCall` function to accept and pass `patient_name`:

```javascript
export async function dialCall({ patient_phone, mode, worker_phone, title, patient_name }) {
  const { data } = await api.post('/calls/dial', { patient_phone, mode, worker_phone, title, patient_name })
  return data
}
```

**Step 2: Update CallDialer.jsx**

Add a `patientName` state variable:

```javascript
const [patientName, setPatientName] = useState('')
```

Add the input field after the "Patient Phone Number" input:

```jsx
<div>
  <label className="block text-sm font-medium mb-1">Patient Name</label>
  <input
    type="text"
    value={patientName}
    onChange={(e) => setPatientName(e.target.value)}
    placeholder="e.g. Lionel"
    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none"
  />
</div>
```

Update the `handleDial` call to pass `patient_name`:

```javascript
const data = await dialCall({
  patient_phone: patientPhone,
  mode,
  worker_phone: mode === 'phone' ? workerPhone : undefined,
  title: title || `Call to ${patientPhone}`,
  patient_name: patientName || undefined,
})
```

Also reset `patientName` in the "New Call" button handler:

```javascript
setPatientName('')
```

**Step 3: Copy to Linux fs and verify build**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/components/CallDialer.jsx ~/workspace/call-monitor-frontend/src/components/CallDialer.jsx
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/api/client.js ~/workspace/call-monitor-frontend/src/api/client.js
cd ~/workspace/call-monitor-frontend && npx vite build
```

Expected: Build succeeds

**Step 4: Commit**

```bash
git add frontend/src/components/CallDialer.jsx frontend/src/api/client.js
git commit -m "feat: add patient name input to call dialer"
```

---

### Task 6: Frontend — speaker-labeled transcript display

**Files:**
- Modify: `frontend/src/components/CallDetail.jsx` — show speaker labels with color coding

**Step 1: Update transcript rendering**

Replace the transcript segment rendering section in `CallDetail.jsx` (the `<div>` with `max-h-96`) with:

```jsx
{call.transcript && (
  <div className="mb-6">
    <h2 className="text-lg font-semibold mb-3">Transcript</h2>
    <div className="bg-white rounded-lg shadow p-4 max-h-96 overflow-y-auto space-y-3">
      {call.transcript.segments?.length > 0 ? (
        call.transcript.segments.map((seg, i) => {
          const prevSpeaker = i > 0 ? call.transcript.segments[i - 1].speaker : null
          const showSpeaker = seg.speaker && seg.speaker !== prevSpeaker
          return (
            <div key={i} className="flex gap-3 text-sm">
              <span className="font-mono text-gray-400 whitespace-nowrap text-xs mt-0.5">
                {formatTime(seg.start)}
              </span>
              <div>
                {showSpeaker && (
                  <span className={`text-xs font-semibold mr-1 ${
                    call.transcript.segments.findIndex(s => s.speaker) === i ||
                    seg.speaker === call.transcript.segments.find(s => s.speaker)?.speaker
                      ? 'text-indigo-600'
                      : 'text-emerald-600'
                  }`}>
                    {seg.speaker}:
                  </span>
                )}
                <span>{seg.text}</span>
              </div>
            </div>
          )
        })
      ) : (
        <p className="text-sm whitespace-pre-wrap">{call.transcript.full_text}</p>
      )}
    </div>
  </div>
)}
```

The color logic: the first speaker found in segments gets indigo (worker), the other speaker gets emerald (patient).

**Step 2: Copy and verify build**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/components/CallDetail.jsx ~/workspace/call-monitor-frontend/src/components/CallDetail.jsx
cd ~/workspace/call-monitor-frontend && npx vite build
```

Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/CallDetail.jsx
git commit -m "feat: speaker-labeled transcript display with color coding"
```

---

### Task 7: Final verification and cleanup

**Step 1: Run all backend tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
source ~/workspace/call-monitor-venv/bin/activate
python3 -m pytest tests/ -v
```

Expected: All tests pass

**Step 2: Verify frontend build**

```bash
cd ~/workspace/call-monitor-frontend && npx vite build
```

Expected: Build succeeds

**Step 3: Delete calls.db (schema changed)**

```bash
rm -f /mnt/c/Users/ticta/workspace/call-monitor/backend/calls.db
```

**Step 4: Commit and push**

```bash
git add -A
git commit -m "docs: add speaker diarization design and plan"
git push
```
