from database import Call, CallScore, Review
from models.schemas import (
    CallScoreResponse, ReviewRequest, ReviewResponse, CallSummary
)


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
