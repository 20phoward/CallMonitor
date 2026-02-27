from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Call, TonalityResult, CallScore, Review
from models.schemas import (
    CallSummary, CallDetail, CallStatusResponse, DashboardStats,
    CallScoreResponse, ReviewRequest, ReviewResponse,
)
from config import STORAGE_DIR

router = APIRouter(prefix="/api/calls", tags=["calls"])


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
        ))
    return results


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Call.id)).scalar()
    completed = db.query(func.count(Call.id)).filter(Call.status == "completed").scalar()
    avg_score = db.query(func.avg(TonalityResult.overall_score)).scalar()

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
        ))

    return DashboardStats(
        total_calls=total,
        completed_calls=completed,
        avg_sentiment_score=round(avg_score, 3) if avg_score is not None else None,
        recent_calls=recent_summaries,
    )


@router.get("/{call_id}", response_model=CallDetail)
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.get("/{call_id}/status", response_model=CallStatusResponse)
def get_call_status(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return CallStatusResponse(id=call.id, status=call.status, error_message=call.error_message)


@router.delete("/{call_id}")
def delete_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    # Delete audio file
    if call.audio_filename:
        audio_path = STORAGE_DIR / call.audio_filename
        if audio_path.exists():
            audio_path.unlink()
        # Also remove WAV conversion if different
        wav_path = audio_path.with_suffix(".wav")
        if wav_path.exists() and wav_path != audio_path:
            wav_path.unlink()

    db.delete(call)
    db.commit()
    return {"detail": "Call deleted"}


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
