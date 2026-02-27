# Phase 2: Call Rating & Review System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add AI-powered rubric scoring (empathy, professionalism, resolution, compliance) to the existing call processing pipeline, with a supervisor review workflow (approve/flag/override).

**Architecture:** Extend the single Claude API call to also return rubric scores. Store scores in a new `CallScore` table, reviews in a new `Review` table. Add score card + review panel to the Call Detail page. Update Dashboard and Call List with rating/review data.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Anthropic Claude API, React 18, Tailwind CSS, Recharts, pytest (new)

**Design doc:** `docs/plans/2026-02-27-phase2-rating-review-design.md`

---

### Task 1: Add pytest and test infrastructure

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Modify: `backend/requirements.txt`

**Step 1: Add pytest + httpx to requirements**

Add to end of `backend/requirements.txt`:
```
pytest==8.3.3
httpx==0.27.2
```

**Step 2: Create test conftest with in-memory DB and FastAPI test client**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app

TEST_DATABASE_URL = "sqlite:///./test.db"
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
```

**Step 3: Verify test setup works**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 0 tests collected, no errors

**Step 4: Commit**

```bash
git add backend/tests/ backend/requirements.txt
git commit -m "chore: add pytest infrastructure with test DB fixtures"
```

---

### Task 2: Add CallScore and Review database models

**Files:**
- Create: `backend/tests/test_models.py`
- Modify: `backend/database.py`

**Step 1: Write failing test for new models**

Create `backend/tests/test_models.py`:
```python
from database import Call, CallScore, Review


def test_call_score_creation(db):
    call = Call(title="Test Call", status="completed")
    db.add(call)
    db.commit()

    score = CallScore(
        call_id=call.id,
        empathy=7.5,
        professionalism=8.0,
        resolution=6.0,
        compliance=9.0,
        overall_rating=7.625,
        category_details={
            "empathy": {"reasoning": "Good active listening"},
            "professionalism": {"reasoning": "Clear communication"},
            "resolution": {"reasoning": "Addressed main concern"},
            "compliance": {"reasoning": "No issues found"},
        },
    )
    db.add(score)
    db.commit()

    assert score.id is not None
    assert score.call.title == "Test Call"
    assert score.overall_rating == 7.625
    assert score.category_details["empathy"]["reasoning"] == "Good active listening"


def test_review_creation(db):
    call = Call(title="Test Call", status="completed")
    db.add(call)
    db.commit()

    review = Review(
        call_id=call.id,
        status="approved",
        score_overrides={"empathy": 8.0},
        notes="Good call overall",
    )
    db.add(review)
    db.commit()

    assert review.id is not None
    assert review.call.title == "Test Call"
    assert review.status == "approved"
    assert review.score_overrides["empathy"] == 8.0


def test_call_relationships(db):
    call = Call(title="Test Call", status="completed")
    db.add(call)
    db.commit()

    score = CallScore(call_id=call.id, empathy=7.0, professionalism=7.0,
                      resolution=7.0, compliance=7.0, overall_rating=7.0)
    review = Review(call_id=call.id, status="flagged")
    db.add_all([score, review])
    db.commit()

    db.refresh(call)
    assert call.score is not None
    assert call.review is not None
    assert call.score.empathy == 7.0
    assert call.review.status == "flagged"


def test_call_cascade_delete(db):
    call = Call(title="Test Call", status="completed")
    db.add(call)
    db.commit()

    db.add(CallScore(call_id=call.id, empathy=7.0, professionalism=7.0,
                     resolution=7.0, compliance=7.0, overall_rating=7.0))
    db.add(Review(call_id=call.id, status="approved"))
    db.commit()

    db.delete(call)
    db.commit()

    assert db.query(CallScore).count() == 0
    assert db.query(Review).count() == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: ImportError — `CallScore` and `Review` not defined

**Step 3: Add CallScore and Review models to database.py**

Add after the `TonalityResult` class in `backend/database.py`:

```python
class CallScore(Base):
    __tablename__ = "call_scores"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    empathy = Column(Float, nullable=True)
    professionalism = Column(Float, nullable=True)
    resolution = Column(Float, nullable=True)
    compliance = Column(Float, nullable=True)
    overall_rating = Column(Float, nullable=True)
    category_details = Column(JSON, nullable=True)

    call = relationship("Call", back_populates="score")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    status = Column(String, default="unreviewed")  # unreviewed/approved/flagged
    score_overrides = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    call = relationship("Call", back_populates="review")
```

Add to the `Call` class (after existing relationships):
```python
    score = relationship("CallScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    review = relationship("Review", back_populates="call", uselist=False, cascade="all, delete-orphan")
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add backend/database.py backend/tests/test_models.py
git commit -m "feat: add CallScore and Review database models"
```

---

### Task 3: Add Pydantic schemas for scores and reviews

**Files:**
- Modify: `backend/models/schemas.py`

**Step 1: Write failing test**

Add to `backend/tests/test_models.py`:
```python
from models.schemas import (
    CallScoreResponse, ReviewRequest, ReviewResponse, CallSummary
)


def test_call_score_response_schema():
    data = CallScoreResponse(
        id=1, call_id=1, empathy=7.5, professionalism=8.0,
        resolution=6.0, compliance=9.0, overall_rating=7.625,
        category_details={"empathy": {"reasoning": "Good"}},
    )
    assert data.overall_rating == 7.625


def test_review_request_schema():
    req = ReviewRequest(
        status="approved",
        score_overrides={"empathy": 8.0},
        notes="Looks good",
    )
    assert req.status == "approved"
    assert req.score_overrides["empathy"] == 8.0


def test_call_summary_includes_rating_and_review():
    summary = CallSummary(
        id=1, title="Test", date="2026-01-01T00:00:00",
        status="completed", source_type="upload",
        overall_rating=7.5, review_status="approved",
    )
    assert summary.overall_rating == 7.5
    assert summary.review_status == "approved"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py::test_call_score_response_schema -v`
Expected: ImportError — `CallScoreResponse` not defined

**Step 3: Add schemas to models/schemas.py**

Add after the `TonalityResponse` class:
```python
# --- Scores ---

class CallScoreResponse(BaseModel):
    id: int
    call_id: int
    empathy: Optional[float] = None
    professionalism: Optional[float] = None
    resolution: Optional[float] = None
    compliance: Optional[float] = None
    overall_rating: Optional[float] = None
    category_details: Optional[dict] = None

    model_config = {"from_attributes": True}


# --- Reviews ---

class ReviewRequest(BaseModel):
    status: str  # approved / flagged
    score_overrides: Optional[dict] = None
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    call_id: int
    status: str
    score_overrides: Optional[dict] = None
    notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
```

Add `overall_rating` and `review_status` to the existing `CallSummary`:
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

    model_config = {"from_attributes": True}
```

Add scores and review to `CallDetail`:
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
    transcript: Optional[TranscriptResponse] = None
    tonality: Optional[TonalityResponse] = None
    score: Optional[CallScoreResponse] = None
    review: Optional[ReviewResponse] = None

    model_config = {"from_attributes": True}
```

Update `DashboardStats`:
```python
class DashboardStats(BaseModel):
    total_calls: int
    completed_calls: int
    avg_sentiment_score: Optional[float] = None
    avg_rating: Optional[float] = None
    unreviewed_count: int = 0
    approved_count: int = 0
    flagged_count: int = 0
    recent_calls: list[CallSummary]
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
git add backend/models/schemas.py backend/tests/test_models.py
git commit -m "feat: add Pydantic schemas for scores and reviews"
```

---

### Task 4: Extend Claude prompt for rubric scoring

**Files:**
- Create: `backend/tests/test_tonality.py`
- Modify: `backend/services/tonality.py`

**Step 1: Write failing test for rubric parsing**

Create `backend/tests/test_tonality.py`:
```python
import json
from services.tonality import parse_tonality_response


def test_parse_tonality_response_with_rubric():
    raw = json.dumps({
        "overall_sentiment": "positive",
        "overall_score": 0.6,
        "sentiment_over_time": [{"time": 0, "score": 0.5, "label": "friendly"}],
        "key_moments": [{"time": 10, "description": "Greeting", "emotion": "friendly"}],
        "summary": "A positive call.",
        "tone_labels": ["professional", "friendly"],
        "rubric_scores": {
            "empathy": {"score": 7.5, "reasoning": "Good listening"},
            "professionalism": {"score": 8.0, "reasoning": "Clear tone"},
            "resolution": {"score": 6.0, "reasoning": "Partial resolution"},
            "compliance": {"score": 9.0, "reasoning": "No issues"},
        },
    })

    result = parse_tonality_response(raw)

    assert result["overall_sentiment"] == "positive"
    assert result["overall_score"] == 0.6
    assert result["rubric_scores"]["empathy"]["score"] == 7.5
    assert result["rubric_scores"]["compliance"]["reasoning"] == "No issues"


def test_parse_tonality_response_missing_rubric():
    raw = json.dumps({
        "overall_sentiment": "neutral",
        "overall_score": 0.0,
        "sentiment_over_time": [],
        "key_moments": [],
        "summary": "Neutral call.",
        "tone_labels": ["neutral"],
    })

    result = parse_tonality_response(raw)

    assert result["overall_sentiment"] == "neutral"
    assert result["rubric_scores"] is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tonality.py -v`
Expected: ImportError — `parse_tonality_response` not defined

**Step 3: Refactor tonality.py — extract parsing, extend prompt**

In `backend/services/tonality.py`, update `ANALYSIS_PROMPT` to add rubric scoring instructions after the existing JSON schema:

```python
ANALYSIS_PROMPT = """\
You are an expert call analyst specializing in healthcare and rehabilitation settings. Analyze the following call transcript and provide a structured tonality/sentiment analysis with quality scoring.

<transcript>
{transcript}
</transcript>

Respond with ONLY valid JSON (no markdown, no code fences) in this exact schema:
{{
  "overall_sentiment": "positive" | "negative" | "neutral" | "mixed",
  "overall_score": <float from -1.0 (very negative) to 1.0 (very positive)>,
  "sentiment_over_time": [
    {{"time": <start_seconds>, "score": <float -1 to 1>, "label": "<emotion>"}}
  ],
  "key_moments": [
    {{"time": <seconds>, "description": "<what happened>", "emotion": "<emotion label>"}}
  ],
  "summary": "<2-3 sentence summary of the call>",
  "tone_labels": ["<tone1>", "<tone2>"],
  "rubric_scores": {{
    "empathy": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }},
    "professionalism": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }},
    "resolution": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }},
    "compliance": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }}
  }}
}}

For sentiment_over_time, sample at the timestamps of the transcript segments provided.
For tone_labels, pick from: professional, friendly, aggressive, frustrated, confused, satisfied, empathetic, neutral, anxious, confident.

Rubric scoring guide (healthcare/rehab context, 0-10 scale):
- **Empathy & Compassion**: Active listening, validating feelings, patience, emotional support, acknowledging patient concerns.
- **Professionalism**: Courteous tone, clear communication, appropriate boundaries, composed demeanor.
- **Resolution & Follow-through**: Were concerns addressed? Were next steps communicated? Was there a clear plan?
- **Compliance & Safety**: Proper introduction, required disclosures, safety protocols, no red flags, HIPAA awareness.

Score guide: 0-3 Poor, 4-5 Below expectations, 6-7 Meets expectations, 8-9 Exceeds expectations, 10 Exceptional.
"""
```

Extract a `parse_tonality_response` function from the existing parsing logic in `analyze_tonality`:

```python
def parse_tonality_response(raw: str) -> dict:
    """Parse Claude's JSON response into a structured dict."""
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response: %s", raw[:500])
        return None

    return {
        "overall_sentiment": data.get("overall_sentiment", "neutral"),
        "overall_score": float(data.get("overall_score", 0)),
        "sentiment_scores": data.get("sentiment_over_time", []),
        "key_moments": data.get("key_moments", []),
        "summary": data.get("summary", ""),
        "tone_labels": data.get("tone_labels", []),
        "rubric_scores": data.get("rubric_scores", None),
    }
```

Update `analyze_tonality` to use `parse_tonality_response`:

```python
def analyze_tonality(transcript_text: str, segments: list[dict]) -> dict:
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder tonality")
        return _placeholder_result(segments)

    lines = []
    for seg in segments:
        ts = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
        speaker = f" ({seg['speaker']})" if seg.get("speaker") else ""
        lines.append(f"{ts}{speaker} {seg['text']}")
    formatted_transcript = "\n".join(lines)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": ANALYSIS_PROMPT.format(transcript=formatted_transcript)},
        ],
    )

    raw = message.content[0].text.strip()
    result = parse_tonality_response(raw)
    if result is None:
        return _placeholder_result(segments)
    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_tonality.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/services/tonality.py backend/tests/test_tonality.py
git commit -m "feat: extend Claude prompt with healthcare rubric scoring"
```

---

### Task 5: Update pipeline to store CallScore

**Files:**
- Create: `backend/tests/test_pipeline.py`
- Modify: `backend/services/pipeline.py`

**Step 1: Write failing test**

Create `backend/tests/test_pipeline.py`:
```python
from unittest.mock import patch
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

    with patch("services.pipeline.convert_to_wav") as mock_convert, \
         patch("services.pipeline.transcribe_audio", return_value=mock_tx), \
         patch("services.pipeline.analyze_tonality", return_value=mock_tonality), \
         patch("services.pipeline.STORAGE_DIR") as mock_dir:

        mock_path = mock_dir / "test.wav"
        mock_path.exists.return_value = True
        mock_convert.return_value = mock_path

        from services.pipeline import process_call
        process_call(call.id, db)

    db.refresh(call)
    assert call.status == "completed"
    assert call.score is not None
    assert call.score.empathy == 7.5
    assert call.score.professionalism == 8.0
    assert call.score.resolution == 6.0
    assert call.score.compliance == 9.0
    assert call.score.overall_rating == 7.625
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

    with patch("services.pipeline.convert_to_wav") as mock_convert, \
         patch("services.pipeline.transcribe_audio", return_value=mock_tx), \
         patch("services.pipeline.analyze_tonality", return_value=mock_tonality), \
         patch("services.pipeline.STORAGE_DIR") as mock_dir:

        mock_path = mock_dir / "test.wav"
        mock_path.exists.return_value = True
        mock_convert.return_value = mock_path

        from services.pipeline import process_call
        process_call(call.id, db)

    db.refresh(call)
    assert call.status == "completed"
    assert call.tonality is not None
    # CallScore created but with null scores
    assert call.score is not None
    assert call.score.empathy is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — pipeline doesn't create CallScore yet

**Step 3: Update pipeline.py to store CallScore**

In `backend/services/pipeline.py`, add import:
```python
from database import Call, Transcript, TonalityResult, CallScore
```

After the `TonalityResult` creation block (after `db.add(tonality)`), add:
```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_pipeline.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add backend/services/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: store rubric scores in CallScore during pipeline"
```

---

### Task 6: Add score and review API endpoints

**Files:**
- Create: `backend/tests/test_api.py`
- Modify: `backend/routers/calls.py`

**Step 1: Write failing tests for new endpoints**

Create `backend/tests/test_api.py`:
```python
from database import Call, CallScore, Review


def test_get_scores(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()
    score = CallScore(
        call_id=call.id, empathy=7.5, professionalism=8.0,
        resolution=6.0, compliance=9.0, overall_rating=7.625,
        category_details={"empathy": {"reasoning": "Good"}},
    )
    db.add(score)
    db.commit()

    resp = client.get(f"/api/calls/{call.id}/scores")
    assert resp.status_code == 200
    data = resp.json()
    assert data["empathy"] == 7.5
    assert data["overall_rating"] == 7.625


def test_get_scores_not_found(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()

    resp = client.get(f"/api/calls/{call.id}/scores")
    assert resp.status_code == 404


def test_submit_review(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()

    resp = client.post(f"/api/calls/{call.id}/review", json={
        "status": "approved",
        "score_overrides": {"empathy": 8.0},
        "notes": "Good call",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["score_overrides"]["empathy"] == 8.0
    assert data["reviewed_at"] is not None


def test_submit_review_updates_existing(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()

    client.post(f"/api/calls/{call.id}/review", json={"status": "approved"})
    resp = client.post(f"/api/calls/{call.id}/review", json={
        "status": "flagged",
        "notes": "Actually needs follow up",
    })

    assert resp.status_code == 200
    assert resp.json()["status"] == "flagged"
    assert db.query(Review).filter(Review.call_id == call.id).count() == 1


def test_get_review(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()
    review = Review(call_id=call.id, status="flagged", notes="Check this")
    db.add(review)
    db.commit()

    resp = client.get(f"/api/calls/{call.id}/review")
    assert resp.status_code == 200
    assert resp.json()["status"] == "flagged"


def test_get_review_not_found(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()

    resp = client.get(f"/api/calls/{call.id}/review")
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: 404 errors — endpoints don't exist

**Step 3: Add endpoints to routers/calls.py**

Add imports at top of `backend/routers/calls.py`:
```python
from datetime import datetime, timezone
from database import get_db, Call, TonalityResult, CallScore, Review
from models.schemas import (
    CallSummary, CallDetail, CallStatusResponse, DashboardStats,
    CallScoreResponse, ReviewRequest, ReviewResponse,
)
```

Add new endpoints after existing ones:
```python
@router.get("/{call_id}/scores", response_model=CallScoreResponse)
def get_call_scores(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not call.score:
        raise HTTPException(status_code=404, detail="Scores not available")
    return call.score


@router.get("/{call_id}/review", response_model=ReviewResponse)
def get_call_review(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if not call.review:
        raise HTTPException(status_code=404, detail="No review found")
    return call.review


@router.post("/{call_id}/review", response_model=ReviewResponse)
def submit_review(call_id: int, req: ReviewRequest, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    review = db.query(Review).filter(Review.call_id == call_id).first()
    if review:
        review.status = req.status
        review.score_overrides = req.score_overrides
        review.notes = req.notes
        review.reviewed_at = datetime.now(timezone.utc)
    else:
        review = Review(
            call_id=call_id,
            status=req.status,
            score_overrides=req.score_overrides,
            notes=req.notes,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)

    db.commit()
    db.refresh(review)
    return review
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add backend/routers/calls.py backend/tests/test_api.py
git commit -m "feat: add score and review API endpoints"
```

---

### Task 7: Update existing list/stats endpoints with rating and review data

**Files:**
- Add to: `backend/tests/test_api.py`
- Modify: `backend/routers/calls.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_api.py`:
```python
def test_list_calls_includes_rating_and_review(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()
    db.add(CallScore(call_id=call.id, empathy=7.0, professionalism=7.0,
                     resolution=7.0, compliance=7.0, overall_rating=7.0))
    db.add(Review(call_id=call.id, status="approved"))
    db.commit()

    resp = client.get("/api/calls")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["overall_rating"] == 7.0
    assert data[0]["review_status"] == "approved"


def test_dashboard_stats_includes_review_counts(client, db):
    for i in range(3):
        call = Call(title=f"Call {i}", status="completed")
        db.add(call)
        db.commit()
        db.add(CallScore(call_id=call.id, empathy=7.0, professionalism=7.0,
                         resolution=7.0, compliance=7.0, overall_rating=7.0))
        db.commit()

    # One approved, one flagged, one unreviewed
    db.add(Review(call_id=1, status="approved"))
    db.add(Review(call_id=2, status="flagged"))
    db.commit()

    resp = client.get("/api/calls/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_rating"] == 7.0
    assert data["approved_count"] == 1
    assert data["flagged_count"] == 1
    assert data["unreviewed_count"] == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_api.py::test_list_calls_includes_rating_and_review -v`
Expected: FAIL — response missing `overall_rating` and `review_status`

**Step 3: Update list_calls endpoint**

In `backend/routers/calls.py`, update the `list_calls` function to include rating and review status in the response:

```python
@router.get("", response_model=list[CallSummary])
def list_calls(db: Session = Depends(get_db)):
    calls = db.query(Call).order_by(Call.date.desc()).all()
    results = []
    for c in calls:
        sentiment = None
        score = None
        if c.tonality:
            sentiment = c.tonality.overall_sentiment
            score = c.tonality.overall_score
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
        ))
    return results
```

Update `dashboard_stats` to include review counts and avg rating:

```python
@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Call.id)).scalar()
    completed = db.query(func.count(Call.id)).filter(Call.status == "completed").scalar()
    avg_score = db.query(func.avg(TonalityResult.overall_score)).scalar()
    avg_rating = db.query(func.avg(CallScore.overall_rating)).scalar()

    approved = db.query(func.count(Review.id)).filter(Review.status == "approved").scalar()
    flagged = db.query(func.count(Review.id)).filter(Review.status == "flagged").scalar()
    reviewed_total = approved + flagged
    unreviewed = completed - reviewed_total

    recent = db.query(Call).order_by(Call.date.desc()).limit(5).all()
    recent_summaries = []
    for c in recent:
        sentiment = c.tonality.overall_sentiment if c.tonality else None
        score = c.tonality.overall_score if c.tonality else None
        recent_summaries.append(CallSummary(
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
        ))

    return DashboardStats(
        total_calls=total,
        completed_calls=completed,
        avg_sentiment_score=round(avg_score, 3) if avg_score is not None else None,
        avg_rating=round(avg_rating, 2) if avg_rating is not None else None,
        unreviewed_count=max(unreviewed, 0),
        approved_count=approved,
        flagged_count=flagged,
        recent_calls=recent_summaries,
    )
```

Add `CallScore` and `Review` to the imports at the top if not already there.

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: 8 passed

**Step 5: Commit**

```bash
git add backend/routers/calls.py backend/tests/test_api.py
git commit -m "feat: include rating and review status in list/stats endpoints"
```

---

### Task 8: Add frontend API client functions

**Files:**
- Modify: `frontend/src/api/client.js`

**Step 1: Add new API functions**

Add to end of `frontend/src/api/client.js`:
```javascript
export async function fetchCallScores(id) {
  const { data } = await api.get(`/calls/${id}/scores`)
  return data
}

export async function fetchCallReview(id) {
  const { data } = await api.get(`/calls/${id}/review`)
  return data
}

export async function submitReview(id, review) {
  const { data } = await api.post(`/calls/${id}/review`, review)
  return data
}
```

**Step 2: Verify no syntax errors**

Run: `cd frontend && npx -y acorn --ecma2020 --module src/api/client.js`
Expected: Parses without error

**Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat: add score and review API client functions"
```

---

### Task 9: Create ScoreCard component

**Files:**
- Create: `frontend/src/components/ScoreCard.jsx`

**Step 1: Create the component**

Create `frontend/src/components/ScoreCard.jsx`:
```jsx
function ScoreBar({ label, score, override }) {
  const effective = override ?? score
  const pct = effective != null ? (effective / 10) * 100 : 0
  const color =
    effective >= 8 ? 'bg-green-500' :
    effective >= 6 ? 'bg-yellow-500' :
    effective >= 4 ? 'bg-orange-500' : 'bg-red-500'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-gray-600">
          {effective != null ? effective.toFixed(1) : 'N/A'}
          {override != null && <span className="text-indigo-600 text-xs ml-1">(overridden)</span>}
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function ScoreCard({ score, review }) {
  if (!score) return null

  const overrides = review?.score_overrides || {}
  const categories = [
    { key: 'empathy', label: 'Empathy & Compassion' },
    { key: 'professionalism', label: 'Professionalism' },
    { key: 'resolution', label: 'Resolution & Follow-through' },
    { key: 'compliance', label: 'Compliance & Safety' },
  ]

  const effectiveOverall = categories.reduce((sum, c) => {
    return sum + (overrides[c.key] ?? score[c.key] ?? 0)
  }, 0) / 4

  const ratingColor =
    effectiveOverall >= 8 ? 'text-green-600' :
    effectiveOverall >= 6 ? 'text-yellow-600' :
    effectiveOverall >= 4 ? 'text-orange-600' : 'text-red-600'

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">Quality Score</p>
        <p className={`text-2xl font-bold ${ratingColor}`}>
          {effectiveOverall.toFixed(1)}<span className="text-sm text-gray-400">/10</span>
        </p>
      </div>
      <div className="space-y-3">
        {categories.map(c => (
          <ScoreBar
            key={c.key}
            label={c.label}
            score={score[c.key]}
            override={overrides[c.key]}
          />
        ))}
      </div>
      {score.category_details && (
        <details className="mt-4">
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
            View AI reasoning
          </summary>
          <div className="mt-2 space-y-2">
            {categories.map(c => (
              score.category_details[c.key]?.reasoning && (
                <div key={c.key} className="text-xs text-gray-600">
                  <span className="font-medium">{c.label}:</span>{' '}
                  {score.category_details[c.key].reasoning}
                </div>
              )
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ScoreCard.jsx
git commit -m "feat: add ScoreCard component with score bars and AI reasoning"
```

---

### Task 10: Create ReviewPanel component

**Files:**
- Create: `frontend/src/components/ReviewPanel.jsx`

**Step 1: Create the component**

Create `frontend/src/components/ReviewPanel.jsx`:
```jsx
import { useState } from 'react'
import { submitReview } from '../api/client'

const CATEGORIES = [
  { key: 'empathy', label: 'Empathy' },
  { key: 'professionalism', label: 'Professionalism' },
  { key: 'resolution', label: 'Resolution' },
  { key: 'compliance', label: 'Compliance' },
]

function ReviewStatusBadge({ status }) {
  const styles = {
    unreviewed: 'bg-gray-100 text-gray-800',
    approved: 'bg-green-100 text-green-800',
    flagged: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.unreviewed}`}>
      {status}
    </span>
  )
}

export default function ReviewPanel({ callId, score, review, onReviewSubmitted }) {
  const [status, setStatus] = useState(review?.status || 'unreviewed')
  const [notes, setNotes] = useState(review?.notes || '')
  const [overrides, setOverrides] = useState(review?.score_overrides || {})
  const [editingScore, setEditingScore] = useState(null)
  const [saving, setSaving] = useState(false)

  const handleOverride = (key, value) => {
    const num = parseFloat(value)
    if (isNaN(num) || num < 0 || num > 10) return
    setOverrides(prev => ({ ...prev, [key]: Math.round(num * 10) / 10 }))
    setEditingScore(null)
  }

  const handleSubmit = async (newStatus) => {
    setSaving(true)
    try {
      const result = await submitReview(callId, {
        status: newStatus,
        score_overrides: Object.keys(overrides).length > 0 ? overrides : null,
        notes: notes || null,
      })
      setStatus(result.status)
      if (onReviewSubmitted) onReviewSubmitted(result)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">Supervisor Review</p>
        <ReviewStatusBadge status={status} />
      </div>

      {/* Score overrides */}
      {score && (
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">Click a score to override:</p>
          <div className="grid grid-cols-2 gap-2">
            {CATEGORIES.map(c => (
              <div key={c.key} className="flex items-center justify-between bg-gray-50 rounded px-2 py-1">
                <span className="text-xs">{c.label}</span>
                {editingScore === c.key ? (
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="0.5"
                    defaultValue={overrides[c.key] ?? score[c.key] ?? ''}
                    className="w-14 text-xs border rounded px-1 py-0.5"
                    autoFocus
                    onBlur={e => handleOverride(c.key, e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleOverride(c.key, e.target.value)}
                  />
                ) : (
                  <button
                    onClick={() => setEditingScore(c.key)}
                    className={`text-xs font-medium px-1 rounded hover:bg-gray-200 ${
                      overrides[c.key] != null ? 'text-indigo-600' : 'text-gray-700'
                    }`}
                  >
                    {(overrides[c.key] ?? score[c.key])?.toFixed(1) ?? 'N/A'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notes */}
      <textarea
        value={notes}
        onChange={e => setNotes(e.target.value)}
        placeholder="Optional review notes..."
        className="w-full border rounded-lg p-2 text-sm mb-4 h-20 resize-none"
      />

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => handleSubmit('approved')}
          disabled={saving}
          className="flex-1 bg-green-600 text-white py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Approve'}
        </button>
        <button
          onClick={() => handleSubmit('flagged')}
          disabled={saving}
          className="flex-1 bg-red-600 text-white py-2 rounded-lg text-sm hover:bg-red-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Flag'}
        </button>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/ReviewPanel.jsx
git commit -m "feat: add ReviewPanel component with score overrides"
```

---

### Task 11: Integrate ScoreCard and ReviewPanel into CallDetail

**Files:**
- Modify: `frontend/src/components/CallDetail.jsx`

**Step 1: Update CallDetail to show scores and review panel**

Add imports at top of `frontend/src/components/CallDetail.jsx`:
```javascript
import ScoreCard from './ScoreCard'
import ReviewPanel from './ReviewPanel'
```

In the component's return JSX, add after the Tonality Analysis section (after the closing `{/* Tonality Summary */}` block, before `{/* Transcript */}`):

```jsx
      {/* Quality Score */}
      {call.score && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Quality Score</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ScoreCard score={call.score} review={call.review} />
            <ReviewPanel
              callId={call.id}
              score={call.score}
              review={call.review}
              onReviewSubmitted={() => fetchCallDetail(id).then(setCall)}
            />
          </div>
        </div>
      )}
```

**Step 2: Verify the page renders**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit**

```bash
git add frontend/src/components/CallDetail.jsx
git commit -m "feat: integrate ScoreCard and ReviewPanel into CallDetail page"
```

---

### Task 12: Update CallList with rating and review columns

**Files:**
- Modify: `frontend/src/components/CallList.jsx`

**Step 1: Add ReviewStatusBadge and new columns**

Add a `ReviewStatusBadge` function before the `CallList` component:
```jsx
function ReviewStatusBadge({ status }) {
  const colors = {
    unreviewed: 'bg-gray-100 text-gray-800',
    approved: 'bg-green-100 text-green-800',
    flagged: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100'}`}>
      {status || 'unreviewed'}
    </span>
  )
}

function RatingBadge({ rating }) {
  if (rating == null) return <span className="text-gray-400">-</span>
  const color =
    rating >= 8 ? 'text-green-600' :
    rating >= 6 ? 'text-yellow-600' :
    rating >= 4 ? 'text-orange-600' : 'text-red-600'
  return <span className={`font-medium ${color}`}>{rating.toFixed(1)}</span>
}
```

Add two new `<th>` elements in the header after the Sentiment column:
```jsx
<th className="px-4 py-2">Rating</th>
<th className="px-4 py-2">Review</th>
```

Add two new `<td>` elements in each row after the sentiment cell:
```jsx
<td className="px-4 py-2"><RatingBadge rating={c.overall_rating} /></td>
<td className="px-4 py-2"><ReviewStatusBadge status={c.review_status} /></td>
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/CallList.jsx
git commit -m "feat: add rating and review status columns to CallList"
```

---

### Task 13: Update Dashboard with review stats

**Files:**
- Modify: `frontend/src/components/Dashboard.jsx`

**Step 1: Add new stat cards and review status column**

In `frontend/src/components/Dashboard.jsx`, add three new stat cards after the existing three (inside the grid div):

```jsx
        <div className="bg-white rounded-lg shadow p-5">
          <p className="text-sm text-gray-500">Avg Rating</p>
          <p className="text-3xl font-bold">
            {stats.avg_rating != null ? stats.avg_rating.toFixed(1) : 'N/A'}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-5">
          <p className="text-sm text-gray-500">Needs Review</p>
          <p className="text-3xl font-bold text-yellow-600">{stats.unreviewed_count}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-5">
          <p className="text-sm text-gray-500">Flagged</p>
          <p className="text-3xl font-bold text-red-600">{stats.flagged_count}</p>
        </div>
```

Update the grid from `sm:grid-cols-3` to `sm:grid-cols-3 lg:grid-cols-6` to accommodate six cards.

Add a Review column to the recent calls table. Add `<th>`:
```jsx
<th className="px-4 py-2">Review</th>
```

Add `<td>` in the row after sentiment:
```jsx
<td className="px-4 py-2">
  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
    c.review_status === 'approved' ? 'bg-green-100 text-green-800' :
    c.review_status === 'flagged' ? 'bg-red-100 text-red-800' :
    'bg-gray-100 text-gray-800'
  }`}>
    {c.review_status || 'unreviewed'}
  </span>
</td>
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/components/Dashboard.jsx
git commit -m "feat: add rating and review stats to Dashboard"
```

---

### Task 14: End-to-end smoke test

**Step 1: Start the backend**

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Step 2: Start the frontend**

```bash
cd frontend
npm install
npm run dev
```

**Step 3: Manual verification checklist**

- [ ] Upload an audio file — processing completes
- [ ] Call Detail shows tonality analysis AND quality score card
- [ ] Score card shows 4 category bars with AI reasoning expandable
- [ ] Review panel shows Approve / Flag buttons
- [ ] Clicking Approve changes review status to approved
- [ ] Overriding a score updates the score bar with "(overridden)" label
- [ ] Call List shows Rating and Review columns
- [ ] Dashboard shows Avg Rating, Needs Review, and Flagged stat cards
- [ ] Dashboard recent calls table shows review status

**Step 4: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

**Step 5: Final commit**

```bash
git commit --allow-empty -m "chore: Phase 2 complete — call rating and review system"
```
