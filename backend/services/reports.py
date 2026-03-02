"""Reports query logic — trends, team comparison, compliance."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Call, TonalityResult, CallScore, Review, User, Team


def _round_or_none(val, digits=2):
    return round(val, digits) if val is not None else None


def get_scoped_call_ids(db: Session, scope_filter, start_date=None, end_date=None):
    """Return list of call IDs that pass scope + date filters."""
    query = scope_filter(db.query(Call), Call, db)
    query = query.filter(Call.status == "completed")
    if start_date:
        query = query.filter(Call.date >= start_date)
    if end_date:
        # Include the full end day
        query = query.filter(Call.date < end_date + timedelta(days=1))
    return [c.id for c in query.all()], query


def compute_trends(db: Session, scope_filter, current_user, period="weekly",
                   start_date=None, end_date=None, worker_id=None):
    """Compute time-bucketed trends for calls."""
    if not end_date:
        end_date = datetime.now(timezone.utc).date()
    if not start_date:
        start_date = end_date - timedelta(days=90)

    call_ids, base_query = get_scoped_call_ids(db, scope_filter, start_date, end_date)
    if worker_id:
        call_ids = [
            c.id for c in base_query.filter(Call.uploaded_by == worker_id).all()
        ]

    # Generate time buckets
    bucket_days = 7 if period == "weekly" else 30
    buckets = []
    cursor = start_date
    while cursor <= end_date:
        bucket_end = cursor + timedelta(days=bucket_days - 1)
        if bucket_end > end_date:
            bucket_end = end_date

        # Find calls in this bucket
        bucket_call_ids = [
            c.id for c in db.query(Call).filter(
                Call.id.in_(call_ids),
                Call.date >= datetime(cursor.year, cursor.month, cursor.day, tzinfo=timezone.utc),
                Call.date < datetime(bucket_end.year, bucket_end.month, bucket_end.day, tzinfo=timezone.utc) + timedelta(days=1),
            ).all()
        ] if call_ids else []

        avg_sentiment = db.query(func.avg(TonalityResult.overall_score)).filter(
            TonalityResult.call_id.in_(bucket_call_ids)).scalar() if bucket_call_ids else None
        avg_scores = db.query(
            func.avg(CallScore.overall_rating),
            func.avg(CallScore.empathy),
            func.avg(CallScore.professionalism),
            func.avg(CallScore.resolution),
            func.avg(CallScore.compliance),
        ).filter(CallScore.call_id.in_(bucket_call_ids)).first() if bucket_call_ids else (None,) * 5

        flagged = db.query(func.count(Review.id)).filter(
            Review.call_id.in_(bucket_call_ids), Review.status == "flagged"
        ).scalar() if bucket_call_ids else 0

        buckets.append({
            "start_date": cursor.isoformat(),
            "end_date": bucket_end.isoformat(),
            "call_count": len(bucket_call_ids),
            "avg_sentiment": _round_or_none(avg_sentiment, 3),
            "avg_rating": _round_or_none(avg_scores[0]),
            "avg_empathy": _round_or_none(avg_scores[1]),
            "avg_professionalism": _round_or_none(avg_scores[2]),
            "avg_resolution": _round_or_none(avg_scores[3]),
            "avg_compliance": _round_or_none(avg_scores[4]),
            "flagged_count": flagged or 0,
        })
        cursor += timedelta(days=bucket_days)

    # Worker breakdown (only for supervisors/admins, and not in per-worker recursion)
    workers = None
    if current_user.role != "worker" and not worker_id:
        uploader_ids = db.query(Call.uploaded_by).filter(
            Call.id.in_(call_ids), Call.uploaded_by.isnot(None)
        ).distinct().all()
        uploader_ids = [uid[0] for uid in uploader_ids]

        workers = []
        for uid in uploader_ids:
            user = db.query(User).filter(User.id == uid).first()
            if not user:
                continue
            # Recompute buckets for this worker
            worker_buckets = compute_trends(
                db, scope_filter, current_user, period, start_date, end_date, worker_id=uid
            )["buckets"]
            workers.append({
                "worker_id": uid,
                "worker_name": user.name,
                "buckets": worker_buckets,
            })

    return {"period": period, "buckets": buckets, "workers": workers}


def compute_team_comparison(db: Session, scope_filter, current_user,
                            start_date=None, end_date=None):
    """Compare teams on key metrics."""
    if not end_date:
        end_date = datetime.now(timezone.utc).date()
    if not start_date:
        start_date = end_date - timedelta(days=90)

    call_ids, _ = get_scoped_call_ids(db, scope_filter, start_date, end_date)

    teams = db.query(Team).all()
    result = []

    for team in teams:
        team_user_ids = [u.id for u in db.query(User).filter(User.team_id == team.id).all()]
        team_call_ids = [
            c.id for c in db.query(Call).filter(
                Call.id.in_(call_ids), Call.uploaded_by.in_(team_user_ids)
            ).all()
        ] if team_user_ids else []

        if not team_call_ids:
            continue

        call_count = len(team_call_ids)
        avg_sentiment = db.query(func.avg(TonalityResult.overall_score)).filter(
            TonalityResult.call_id.in_(team_call_ids)).scalar()
        avg_rating = db.query(func.avg(CallScore.overall_rating)).filter(
            CallScore.call_id.in_(team_call_ids)).scalar()

        flagged = db.query(func.count(Review.id)).filter(
            Review.call_id.in_(team_call_ids), Review.status == "flagged").scalar()
        approved = db.query(func.count(Review.id)).filter(
            Review.call_id.in_(team_call_ids), Review.status == "approved").scalar()

        # Top / lowest scorer
        worker_ratings = []
        for uid in team_user_ids:
            worker_avg = db.query(func.avg(CallScore.overall_rating)).join(Call).filter(
                Call.id.in_(team_call_ids), Call.uploaded_by == uid).scalar()
            if worker_avg is not None:
                user = db.query(User).filter(User.id == uid).first()
                worker_ratings.append((user.name, worker_avg))

        worker_ratings.sort(key=lambda x: x[1], reverse=True)
        top_worker = worker_ratings[0][0] if worker_ratings else None
        lowest_scorer = worker_ratings[-1][0] if len(worker_ratings) > 1 else None

        result.append({
            "team_id": team.id,
            "team_name": team.name,
            "call_count": call_count,
            "avg_sentiment": _round_or_none(avg_sentiment, 3),
            "avg_rating": _round_or_none(avg_rating),
            "flagged_pct": round(flagged / call_count * 100, 1) if call_count else 0.0,
            "approved_pct": round(approved / call_count * 100, 1) if call_count else 0.0,
            "top_worker": top_worker,
            "lowest_scorer": lowest_scorer,
        })

    return {"teams": result}


def compute_compliance(db: Session, scope_filter, current_user,
                       threshold=7.0, start_date=None, end_date=None):
    """Compute score compliance and review completion metrics."""
    if not end_date:
        end_date = datetime.now(timezone.utc).date()
    if not start_date:
        start_date = end_date - timedelta(days=90)

    call_ids, _ = get_scoped_call_ids(db, scope_filter, start_date, end_date)

    # Score compliance
    total_with_scores = db.query(CallScore).filter(
        CallScore.call_id.in_(call_ids), CallScore.overall_rating.isnot(None)
    ).count()
    passing = db.query(CallScore).filter(
        CallScore.call_id.in_(call_ids), CallScore.overall_rating >= threshold
    ).count()

    # Failing workers
    uploader_ids = db.query(Call.uploaded_by).filter(
        Call.id.in_(call_ids), Call.uploaded_by.isnot(None)
    ).distinct().all()

    failing_workers = []
    for (uid,) in uploader_ids:
        worker_avg = db.query(func.avg(CallScore.overall_rating)).join(Call).filter(
            Call.id.in_(call_ids), Call.uploaded_by == uid
        ).scalar()
        if worker_avg is not None and worker_avg < threshold:
            calls_below = db.query(CallScore).join(Call).filter(
                Call.id.in_(call_ids), Call.uploaded_by == uid,
                CallScore.overall_rating < threshold
            ).count()
            user = db.query(User).filter(User.id == uid).first()
            failing_workers.append({
                "worker_id": uid,
                "name": user.name if user else "Unknown",
                "avg_score": round(worker_avg, 2),
                "calls_below": calls_below,
            })

    # Review completion
    reviewed = db.query(Review).filter(
        Review.call_id.in_(call_ids), Review.status.in_(["approved", "flagged"])
    ).all()

    avg_days = None
    if reviewed:
        days_list = []
        for r in reviewed:
            if r.reviewed_at:
                call = db.query(Call).filter(Call.id == r.call_id).first()
                if call and call.date:
                    delta = (r.reviewed_at - call.date).total_seconds() / 86400
                    days_list.append(max(delta, 0))
        if days_list:
            avg_days = round(sum(days_list) / len(days_list), 1)

    total_calls = len(call_ids)
    reviewed_count = len(reviewed)

    return {
        "score_compliance": {
            "threshold": threshold,
            "total_calls": total_with_scores,
            "passing_calls": passing,
            "passing_pct": round(passing / total_with_scores * 100, 1) if total_with_scores else 0.0,
            "failing_workers": failing_workers,
        },
        "review_completion": {
            "total_completed_calls": total_calls,
            "reviewed_count": reviewed_count,
            "review_pct": round(reviewed_count / total_calls * 100, 1) if total_calls else 0.0,
            "avg_days_to_review": avg_days,
            "unreviewed_backlog": total_calls - reviewed_count,
        },
    }


def get_calls_for_export(db: Session, scope_filter, start_date=None, end_date=None):
    """Return flat list of call data for CSV/PDF export."""
    call_ids, _ = get_scoped_call_ids(db, scope_filter, start_date, end_date)
    calls = db.query(Call).filter(Call.id.in_(call_ids)).order_by(Call.date.desc()).all()

    rows = []
    for c in calls:
        uploader = db.query(User).filter(User.id == c.uploaded_by).first() if c.uploaded_by else None
        rows.append({
            "id": c.id,
            "title": c.title,
            "date": c.date.strftime("%Y-%m-%d %H:%M") if c.date else "",
            "duration_sec": round(c.duration, 1) if c.duration else "",
            "status": c.status,
            "source_type": c.source_type or "",
            "worker": uploader.name if uploader else "",
            "sentiment": round(c.tonality.overall_score, 3) if c.tonality and c.tonality.overall_score is not None else "",
            "rating": round(c.score.overall_rating, 2) if c.score and c.score.overall_rating is not None else "",
            "empathy": round(c.score.empathy, 2) if c.score and c.score.empathy is not None else "",
            "professionalism": round(c.score.professionalism, 2) if c.score and c.score.professionalism is not None else "",
            "resolution": round(c.score.resolution, 2) if c.score and c.score.resolution is not None else "",
            "compliance": round(c.score.compliance, 2) if c.score and c.score.compliance is not None else "",
            "review_status": c.review.status if c.review else "unreviewed",
        })
    return rows
