from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Call, TonalityResult, CallScore, Review, User
from models.schemas import (
    CallSummary, CallDetail, CallStatusResponse, DashboardStats,
    CallScoreResponse, ReviewRequest, ReviewResponse,
)
from config import STORAGE_DIR
from dependencies import get_current_user, get_call_scope_filter, require_supervisor_or_admin
from services.audit import log_audit

router = APIRouter(prefix="/api/calls", tags=["calls"])


def _check_call_access(call, scope_filter, db):
    """Verify user can access this specific call."""
    q = db.query(Call).filter(Call.id == call.id)
    q = scope_filter(q, Call, db)
    if q.first() is None:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("", response_model=list[CallSummary])
def list_calls(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    query = db.query(Call).order_by(Call.date.desc())
    query = scope_filter(query, Call, db)
    calls = query.all()

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


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    base_query = scope_filter(db.query(Call), Call, db)
    scoped_ids = [c.id for c in base_query.all()]

    if not scoped_ids:
        return DashboardStats(
            total_calls=0, completed_calls=0, avg_sentiment_score=None,
            avg_rating=None, unreviewed_count=0, approved_count=0,
            flagged_count=0, recent_calls=[],
        )

    total = len(scoped_ids)
    completed = base_query.filter(Call.status == "completed").count()

    avg_score = db.query(func.avg(TonalityResult.overall_score)).filter(
        TonalityResult.call_id.in_(scoped_ids)
    ).scalar()
    avg_rating = db.query(func.avg(CallScore.overall_rating)).filter(
        CallScore.call_id.in_(scoped_ids)
    ).scalar()

    approved = db.query(func.count(Review.id)).filter(
        Review.call_id.in_(scoped_ids), Review.status == "approved"
    ).scalar()
    flagged = db.query(func.count(Review.id)).filter(
        Review.call_id.in_(scoped_ids), Review.status == "flagged"
    ).scalar()
    reviewed_total = approved + flagged
    unreviewed = completed - reviewed_total

    recent = base_query.order_by(Call.date.desc()).limit(5).all()
    recent_summaries = []
    for c in recent:
        sentiment = c.tonality.overall_sentiment if c.tonality else None
        score = c.tonality.overall_score if c.tonality else None
        recent_summaries.append(CallSummary(
            id=c.id, title=c.title, date=c.date, duration=c.duration,
            status=c.status, source_type=c.source_type,
            overall_sentiment=sentiment, overall_score=score,
            overall_rating=c.score.overall_rating if c.score else None,
            review_status=c.review.status if c.review else "unreviewed",
        ))

    return DashboardStats(
        total_calls=total, completed_calls=completed,
        avg_sentiment_score=round(avg_score, 3) if avg_score is not None else None,
        avg_rating=round(avg_rating, 2) if avg_rating is not None else None,
        unreviewed_count=max(unreviewed, 0),
        approved_count=approved, flagged_count=flagged,
        recent_calls=recent_summaries,
    )


@router.get("/{call_id}", response_model=CallDetail)
def get_call(
    call_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    log_audit(db, current_user, "view_call", request, "call", call_id)
    return call


@router.get("/{call_id}/status", response_model=CallStatusResponse)
def get_call_status(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    return CallStatusResponse(id=call.id, status=call.status, error_message=call.error_message)


@router.delete("/{call_id}")
def delete_call(
    call_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)

    if call.audio_filename:
        audio_path = STORAGE_DIR / call.audio_filename
        if audio_path.exists():
            audio_path.unlink()
        wav_path = audio_path.with_suffix(".wav")
        if wav_path.exists() and wav_path != audio_path:
            wav_path.unlink()

    log_audit(db, current_user, "delete_call", request, "call", call_id)
    db.delete(call)
    db.commit()
    return {"detail": "Call deleted"}


@router.get("/{call_id}/scores", response_model=CallScoreResponse)
def get_call_scores(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    if not call.score:
        raise HTTPException(status_code=404, detail="Scores not available")
    return call.score


@router.get("/{call_id}/review", response_model=ReviewResponse)
def get_call_review(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    if not call.review:
        raise HTTPException(status_code=404, detail="No review found")
    return call.review


@router.post("/{call_id}/review", response_model=ReviewResponse)
def submit_review(
    call_id: int,
    req: ReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)

    review = db.query(Review).filter(Review.call_id == call_id).first()
    action = "update_review" if review else "submit_review"
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

    log_audit(db, current_user, action, request, "review", call_id)
    db.commit()
    db.refresh(review)
    return review
