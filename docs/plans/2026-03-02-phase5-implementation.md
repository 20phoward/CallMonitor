# Phase 5: Reporting & Analytics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reporting endpoints (trends, team comparison, compliance) with CSV/PDF export and a frontend Reports page.

**Architecture:** Backend-driven — new `/api/reports/` router with 5 endpoints handles all aggregation. A new `services/reports.py` contains the query logic. Frontend adds a `/reports` page with Recharts visualizations and export buttons. Role-based scoping reuses existing `get_call_scope_filter` and `get_current_user` dependencies.

**Tech Stack:** FastAPI, SQLAlchemy, ReportLab (PDF), Python csv module, React, Recharts

---

### Task 1: Add ReportLab Dependency and Pydantic Schemas

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/models/schemas.py`

**Step 1: Add reportlab to requirements.txt**

Add this line at the end of `backend/requirements.txt`:
```
reportlab
```

**Step 2: Install the dependency**

Run:
```bash
source ~/workspace/call-monitor-venv/bin/activate
pip install reportlab
```
Expected: successful install

**Step 3: Add all report Pydantic schemas to `backend/models/schemas.py`**

Add at the bottom of the file, after the `DashboardStats` class:

```python
# --- Reports ---

class TrendBucket(BaseModel):
    start_date: str
    end_date: str
    call_count: int = 0
    avg_sentiment: Optional[float] = None
    avg_rating: Optional[float] = None
    avg_empathy: Optional[float] = None
    avg_professionalism: Optional[float] = None
    avg_resolution: Optional[float] = None
    avg_compliance: Optional[float] = None
    flagged_count: int = 0


class WorkerTrend(BaseModel):
    worker_id: int
    worker_name: str
    buckets: list[TrendBucket]


class TrendsResponse(BaseModel):
    period: str
    buckets: list[TrendBucket]
    workers: Optional[list[WorkerTrend]] = None


class TeamStats(BaseModel):
    team_id: int
    team_name: str
    call_count: int = 0
    avg_sentiment: Optional[float] = None
    avg_rating: Optional[float] = None
    flagged_pct: float = 0.0
    approved_pct: float = 0.0
    top_worker: Optional[str] = None
    lowest_scorer: Optional[str] = None


class TeamComparisonResponse(BaseModel):
    teams: list[TeamStats]


class FailingWorker(BaseModel):
    worker_id: int
    name: str
    avg_score: float
    calls_below: int


class ScoreCompliance(BaseModel):
    threshold: float
    total_calls: int
    passing_calls: int
    passing_pct: float
    failing_workers: list[FailingWorker]


class ReviewCompletion(BaseModel):
    total_completed_calls: int
    reviewed_count: int
    review_pct: float
    avg_days_to_review: Optional[float] = None
    unreviewed_backlog: int


class ComplianceResponse(BaseModel):
    score_compliance: ScoreCompliance
    review_completion: ReviewCompletion
```

**Step 4: Commit**

```bash
git add backend/requirements.txt backend/models/schemas.py
git commit -m "feat: add reportlab dependency and report schemas"
```

---

### Task 2: Reports Service — Trends Query Logic

**Files:**
- Create: `backend/services/reports.py`
- Create: `backend/tests/test_reports.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_reports.py`:

```python
"""Tests for the reports service and endpoints."""
from datetime import datetime, timezone, timedelta
from database import Call, TonalityResult, CallScore, Review


def _make_call(db, user, days_ago=0, sentiment=0.5, rating=7.0, review_status=None):
    """Helper to create a completed call with score and tonality."""
    call = Call(
        title=f"Call {days_ago}d ago",
        status="completed",
        uploaded_by=user.id,
        date=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    tonality = TonalityResult(call_id=call.id, overall_score=sentiment, overall_sentiment="positive")
    score = CallScore(
        call_id=call.id,
        empathy=rating, professionalism=rating,
        resolution=rating, compliance=rating,
        overall_rating=rating,
    )
    db.add_all([tonality, score])

    if review_status:
        review = Review(
            call_id=call.id, status=review_status,
            reviewed_at=datetime.now(timezone.utc) - timedelta(days=days_ago - 1) if days_ago > 0 else datetime.now(timezone.utc),
        )
        db.add(review)

    db.commit()
    return call


# --- Trends ---

def test_trends_returns_buckets(client, admin_headers, admin_user, db):
    _make_call(db, admin_user, days_ago=5, sentiment=0.8, rating=8.0)
    _make_call(db, admin_user, days_ago=3, sentiment=0.4, rating=6.0)

    resp = client.get("/api/reports/trends?period=weekly", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "weekly"
    assert len(data["buckets"]) >= 1
    assert data["buckets"][0]["call_count"] >= 1


def test_trends_date_filter(client, admin_headers, admin_user, db):
    _make_call(db, admin_user, days_ago=100)  # old call
    _make_call(db, admin_user, days_ago=5)    # recent call

    start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = client.get(f"/api/reports/trends?start_date={start}&end_date={end}", headers=admin_headers)
    assert resp.status_code == 200
    total = sum(b["call_count"] for b in resp.json()["buckets"])
    assert total == 1  # only recent call


def test_trends_worker_scoping(client, worker_headers, worker_user, admin_user, db):
    _make_call(db, worker_user, days_ago=3)
    _make_call(db, admin_user, days_ago=3)

    resp = client.get("/api/reports/trends", headers=worker_headers)
    assert resp.status_code == 200
    total = sum(b["call_count"] for b in resp.json()["buckets"])
    assert total == 1  # worker sees own only
    assert resp.json()["workers"] is None  # no worker breakdown for workers


def test_trends_admin_sees_worker_breakdown(client, admin_headers, admin_user, worker_user, db):
    _make_call(db, admin_user, days_ago=3)
    _make_call(db, worker_user, days_ago=3)

    resp = client.get("/api/reports/trends", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["workers"] is not None
    assert len(resp.json()["workers"]) == 2


# --- Team Comparison ---

def test_team_comparison_admin(client, admin_headers, admin_user, worker_user, team, db):
    _make_call(db, worker_user, days_ago=3, rating=8.0)

    resp = client.get("/api/reports/team-comparison", headers=admin_headers)
    assert resp.status_code == 200
    teams = resp.json()["teams"]
    assert len(teams) >= 1
    assert teams[0]["team_name"] == "Test Team"
    assert teams[0]["call_count"] == 1


def test_team_comparison_worker_denied(client, worker_headers):
    resp = client.get("/api/reports/team-comparison", headers=worker_headers)
    assert resp.status_code == 403


# --- Compliance ---

def test_compliance_report(client, admin_headers, admin_user, db):
    _make_call(db, admin_user, days_ago=3, rating=8.0, review_status="approved")
    _make_call(db, admin_user, days_ago=2, rating=5.0)  # below threshold

    resp = client.get("/api/reports/compliance?threshold=7.0", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score_compliance"]["total_calls"] == 2
    assert data["score_compliance"]["passing_calls"] == 1
    assert data["score_compliance"]["passing_pct"] == 50.0
    assert data["review_completion"]["reviewed_count"] == 1
    assert data["review_completion"]["unreviewed_backlog"] == 1


def test_compliance_worker_scoped(client, worker_headers, worker_user, admin_user, db):
    _make_call(db, worker_user, days_ago=3, rating=8.0)
    _make_call(db, admin_user, days_ago=3, rating=5.0)

    resp = client.get("/api/reports/compliance", headers=worker_headers)
    assert resp.status_code == 200
    assert resp.json()["score_compliance"]["total_calls"] == 1


# --- Export ---

def test_export_csv(client, admin_headers, admin_user, db):
    _make_call(db, admin_user, days_ago=3)

    resp = client.get("/api/reports/export/csv?report_type=calls", headers=admin_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2  # header + 1 data row


def test_export_pdf(client, admin_headers, admin_user, db):
    _make_call(db, admin_user, days_ago=3)

    resp = client.get("/api/reports/export/pdf?report_type=calls", headers=admin_headers)
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]
    assert resp.content[:5] == b"%PDF-"


def test_no_auth_returns_403(client):
    resp = client.get("/api/reports/trends")
    assert resp.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
source ~/workspace/call-monitor-venv/bin/activate
pytest tests/test_reports.py -v
```
Expected: FAIL (no `/api/reports/` routes exist yet)

**Step 3: Create `backend/services/reports.py`**

```python
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

    # Worker breakdown (only for supervisors/admins)
    workers = None
    if current_user.role != "worker":
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
```

**Step 4: Commit**

```bash
git add backend/services/reports.py backend/tests/test_reports.py
git commit -m "feat: add reports service with trends, team comparison, compliance logic"
```

---

### Task 3: Reports Router

**Files:**
- Create: `backend/routers/reports.py`
- Modify: `backend/main.py`

**Step 1: Create `backend/routers/reports.py`**

```python
"""Report endpoints — trends, team comparison, compliance, CSV/PDF export."""

import csv
import io
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, User
from dependencies import get_current_user, get_call_scope_filter, require_supervisor_or_admin
from models.schemas import TrendsResponse, TeamComparisonResponse, ComplianceResponse
from services.reports import (
    compute_trends, compute_team_comparison, compute_compliance, get_calls_for_export,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _parse_date(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {d}. Use YYYY-MM-DD.")


@router.get("/trends", response_model=TrendsResponse)
def trends_report(
    period: str = Query("weekly", regex="^(weekly|monthly)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    worker_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    return compute_trends(db, scope_filter, current_user, period, sd, ed, worker_id)


@router.get("/team-comparison", response_model=TeamComparisonResponse)
def team_comparison_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    return compute_team_comparison(db, scope_filter, current_user, sd, ed)


@router.get("/compliance", response_model=ComplianceResponse)
def compliance_report(
    threshold: float = Query(7.0, ge=0, le=10),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)
    return compute_compliance(db, scope_filter, current_user, threshold, sd, ed)


@router.get("/export/csv")
def export_csv(
    report_type: str = Query("calls", regex="^(calls|trends|compliance)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "calls":
        rows = get_calls_for_export(db, scope_filter, sd, ed)
        if rows:
            writer.writerow(rows[0].keys())
            for row in rows:
                writer.writerow(row.values())
        else:
            writer.writerow(["No data"])
    elif report_type == "trends":
        data = compute_trends(db, scope_filter, current_user, "weekly", sd, ed)
        writer.writerow(["start_date", "end_date", "call_count", "avg_sentiment",
                         "avg_rating", "avg_empathy", "avg_professionalism",
                         "avg_resolution", "avg_compliance", "flagged_count"])
        for b in data["buckets"]:
            writer.writerow([b["start_date"], b["end_date"], b["call_count"],
                             b["avg_sentiment"], b["avg_rating"], b["avg_empathy"],
                             b["avg_professionalism"], b["avg_resolution"],
                             b["avg_compliance"], b["flagged_count"]])
    elif report_type == "compliance":
        data = compute_compliance(db, scope_filter, current_user, 7.0, sd, ed)
        sc = data["score_compliance"]
        rc = data["review_completion"]
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Score Threshold", sc["threshold"]])
        writer.writerow(["Total Calls with Scores", sc["total_calls"]])
        writer.writerow(["Passing Calls", sc["passing_calls"]])
        writer.writerow(["Passing %", sc["passing_pct"]])
        writer.writerow(["Reviewed Count", rc["reviewed_count"]])
        writer.writerow(["Review %", rc["review_pct"]])
        writer.writerow(["Avg Days to Review", rc["avg_days_to_review"]])
        writer.writerow(["Unreviewed Backlog", rc["unreviewed_backlog"]])

    output.seek(0)
    today = datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report-{report_type}-{today}.csv"},
    )


@router.get("/export/pdf")
def export_pdf(
    report_type: str = Query("calls", regex="^(calls|trends|compliance)$"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    sd = _parse_date(start_date)
    ed = _parse_date(end_date)

    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph(f"Call Monitor — {report_type.title()} Report", styles["Title"]))
    date_range = f"{sd or 'All time'} to {ed or 'today'}"
    elements.append(Paragraph(f"Date range: {date_range} | Generated by: {current_user.name}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    if report_type == "calls":
        rows = get_calls_for_export(db, scope_filter, sd, ed)
        if rows:
            headers = ["Title", "Date", "Worker", "Sentiment", "Rating", "Review"]
            table_data = [headers]
            for r in rows:
                table_data.append([
                    r["title"][:30], r["date"], r["worker"],
                    str(r["sentiment"]), str(r["rating"]), r["review_status"],
                ])
        else:
            table_data = [["No data"]]
    elif report_type == "trends":
        data = compute_trends(db, scope_filter, current_user, "weekly", sd, ed)
        headers = ["Period", "Calls", "Avg Sentiment", "Avg Rating", "Flagged"]
        table_data = [headers]
        for b in data["buckets"]:
            table_data.append([
                f"{b['start_date']} - {b['end_date']}", str(b["call_count"]),
                str(b["avg_sentiment"] or "—"), str(b["avg_rating"] or "—"),
                str(b["flagged_count"]),
            ])
    elif report_type == "compliance":
        data = compute_compliance(db, scope_filter, current_user, 7.0, sd, ed)
        sc = data["score_compliance"]
        rc = data["review_completion"]
        table_data = [
            ["Metric", "Value"],
            ["Score Threshold", str(sc["threshold"])],
            ["Total Calls", str(sc["total_calls"])],
            ["Passing", f"{sc['passing_calls']} ({sc['passing_pct']}%)"],
            ["Reviewed", f"{rc['reviewed_count']} ({rc['review_pct']}%)"],
            ["Avg Days to Review", str(rc["avg_days_to_review"] or "—")],
            ["Unreviewed Backlog", str(rc["unreviewed_backlog"])],
        ]

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338ca")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 20))

    footer = datetime.now().strftime("Generated %Y-%m-%d %H:%M UTC")
    elements.append(Paragraph(footer, styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    today = datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report-{report_type}-{today}.pdf"},
    )
```

**Step 2: Register the router in `backend/main.py`**

Change the import line:
```python
from routers import calls, upload, twilio_webhooks, auth, users, teams, audit, reports
```

Add after the audit router:
```python
app.include_router(reports.router)
```

**Step 3: Run all tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
pytest tests/test_reports.py -v
```
Expected: All tests PASS

```bash
pytest -v
```
Expected: All 71+ existing tests PASS, plus new report tests

**Step 4: Commit**

```bash
git add backend/routers/reports.py backend/main.py
git commit -m "feat: add reports router with trends, team comparison, compliance, CSV/PDF export"
```

---

### Task 4: Frontend — API Client Functions

**Files:**
- Modify: `frontend/src/api/client.js` (source of truth: `/home/tictac/workspace/call-monitor-frontend/src/api/client.js`)

**Step 1: Add report API functions**

Add before the `export default api` line at the bottom of the file:

```javascript
// Reports
export async function fetchTrends(params = {}) {
  const { data } = await api.get('/reports/trends', { params })
  return data
}

export async function fetchTeamComparison(params = {}) {
  const { data } = await api.get('/reports/team-comparison', { params })
  return data
}

export async function fetchCompliance(params = {}) {
  const { data } = await api.get('/reports/compliance', { params })
  return data
}

export function exportCsvUrl(params = {}) {
  const query = new URLSearchParams(params).toString()
  return `/api/reports/export/csv?${query}`
}

export function exportPdfUrl(params = {}) {
  const query = new URLSearchParams(params).toString()
  return `/api/reports/export/pdf?${query}`
}
```

**Step 2: Copy to frontend working directory**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/api/client.js ~/workspace/call-monitor-frontend/src/api/client.js
```

**Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat: add report API client functions"
```

---

### Task 5: Frontend — Reports Page Component

**Files:**
- Create: `frontend/src/components/Reports.jsx`
- Modify: `frontend/src/App.jsx` (source of truth: `/home/tictac/workspace/call-monitor-frontend/src/App.jsx`)

**Step 1: Create `frontend/src/components/Reports.jsx`**

```jsx
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { fetchTrends, fetchTeamComparison, fetchCompliance, exportCsvUrl, exportPdfUrl } from '../api/client'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts'

const PRESETS = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
]

function formatDate(d) {
  return d.toISOString().split('T')[0]
}

export default function Reports() {
  const { user } = useAuth()
  const [startDate, setStartDate] = useState(() => formatDate(new Date(Date.now() - 90 * 86400000)))
  const [endDate, setEndDate] = useState(() => formatDate(new Date()))
  const [period, setPeriod] = useState('weekly')
  const [trends, setTrends] = useState(null)
  const [teamData, setTeamData] = useState(null)
  const [compliance, setCompliance] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { start_date: startDate, end_date: endDate }
      const trendsData = await fetchTrends({ ...params, period })
      setTrends(trendsData)

      if (user.role !== 'worker') {
        const teamComp = await fetchTeamComparison(params)
        setTeamData(teamComp)
      }

      const comp = await fetchCompliance(params)
      setCompliance(comp)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load reports')
    } finally {
      setLoading(false)
    }
  }, [startDate, endDate, period, user.role])

  useEffect(() => { loadData() }, [loadData])

  const applyPreset = (days) => {
    setEndDate(formatDate(new Date()))
    setStartDate(formatDate(new Date(Date.now() - days * 86400000)))
  }

  const handleExport = (format) => {
    const params = { report_type: 'calls', start_date: startDate, end_date: endDate }
    const token = localStorage.getItem('access_token')
    const url = format === 'csv' ? exportCsvUrl(params) : exportPdfUrl(params)
    // Use fetch with auth header to download
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(resp => resp.blob())
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `report-calls-${endDate}.${format}`
        a.click()
        URL.revokeObjectURL(a.href)
      })
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-500">Loading reports...</div>
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Reports & Analytics</h1>
        <div className="flex gap-2">
          <button onClick={() => handleExport('csv')}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">Export CSV</button>
          <button onClick={() => handleExport('pdf')}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">Export PDF</button>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-600 p-3 rounded text-sm">{error}</div>}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 flex flex-wrap items-center gap-4">
        <div className="flex gap-1">
          {PRESETS.map(p => (
            <button key={p.days} onClick={() => applyPreset(p.days)}
              className="px-3 py-1 text-xs border rounded-full hover:bg-indigo-50 hover:border-indigo-300">
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-sm">
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="border rounded px-2 py-1" />
          <span className="text-gray-400">to</span>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="border rounded px-2 py-1" />
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label className="text-gray-600">Period:</label>
          <select value={period} onChange={e => setPeriod(e.target.value)}
            className="border rounded px-2 py-1">
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <button onClick={loadData}
          className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
          Apply
        </button>
      </div>

      {/* Trends Chart */}
      {trends && trends.buckets.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Performance Trends</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends.buckets}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="start_date" tick={{ fontSize: 11 }}
                tickFormatter={v => v.slice(5)} />
              <YAxis yAxisId="rating" domain={[0, 10]} />
              <YAxis yAxisId="sentiment" orientation="right" domain={[-1, 1]} />
              <Tooltip />
              <Legend />
              <Line yAxisId="rating" type="monotone" dataKey="avg_rating"
                stroke="#6366f1" strokeWidth={2} name="Avg Rating" dot={false} />
              <Line yAxisId="sentiment" type="monotone" dataKey="avg_sentiment"
                stroke="#10b981" strokeWidth={2} name="Avg Sentiment" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Team Comparison */}
      {teamData && teamData.teams.length > 0 && user.role !== 'worker' && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Team Comparison</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={teamData.teams}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="team_name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="avg_rating" fill="#6366f1" name="Avg Rating" />
              <Bar dataKey="call_count" fill="#a5b4fc" name="Call Count" />
              <Bar dataKey="flagged_pct" fill="#ef4444" name="Flagged %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Compliance Summary */}
      {compliance && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Compliance</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <div className="bg-indigo-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-indigo-700">
                {compliance.score_compliance.passing_pct}%
              </div>
              <div className="text-xs text-gray-600 mt-1">Score Compliance</div>
              <div className="text-xs text-gray-400">
                {compliance.score_compliance.passing_calls}/{compliance.score_compliance.total_calls} calls
              </div>
            </div>
            <div className="bg-green-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-green-700">
                {compliance.review_completion.review_pct}%
              </div>
              <div className="text-xs text-gray-600 mt-1">Review Completion</div>
              <div className="text-xs text-gray-400">
                {compliance.review_completion.reviewed_count}/{compliance.review_completion.total_completed_calls} calls
              </div>
            </div>
            <div className="bg-yellow-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-yellow-700">
                {compliance.review_completion.avg_days_to_review ?? '—'}
              </div>
              <div className="text-xs text-gray-600 mt-1">Avg Days to Review</div>
            </div>
            <div className="bg-red-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-red-700">
                {compliance.review_completion.unreviewed_backlog}
              </div>
              <div className="text-xs text-gray-600 mt-1">Unreviewed Backlog</div>
            </div>
          </div>

          {compliance.score_compliance.failing_workers.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Workers Below Threshold ({compliance.score_compliance.threshold})
              </h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-2">Worker</th>
                    <th className="py-2">Avg Score</th>
                    <th className="py-2">Calls Below</th>
                  </tr>
                </thead>
                <tbody>
                  {compliance.score_compliance.failing_workers.map(w => (
                    <tr key={w.worker_id} className="border-b">
                      <td className="py-2">{w.name}</td>
                      <td className="py-2 text-red-600">{w.avg_score}</td>
                      <td className="py-2">{w.calls_below}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Update `frontend/src/App.jsx`**

Add the import:
```javascript
import Reports from './components/Reports'
```

Add "Reports" link in the navbar (after "Call" link, visible to all roles):
```jsx
<Link to="/reports" className="hover:text-indigo-200">Reports</Link>
```

Add the route (after the `/call` route):
```jsx
<Route path="/reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
```

**Step 3: Copy to frontend working directory**

```bash
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/components/Reports.jsx ~/workspace/call-monitor-frontend/src/components/Reports.jsx
cp /mnt/c/Users/ticta/workspace/call-monitor/frontend/src/App.jsx ~/workspace/call-monitor-frontend/src/App.jsx
```

**Step 4: Verify build**

```bash
cd ~/workspace/call-monitor-frontend && npx vite build
```
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor
git add frontend/src/components/Reports.jsx frontend/src/App.jsx
git commit -m "feat: add Reports page with trends chart, team comparison, compliance summary"
```

---

### Task 6: Final Verification

**Step 1: Run all backend tests**

```bash
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
source ~/workspace/call-monitor-venv/bin/activate
pytest -v
```
Expected: All tests pass (71 existing + new report tests)

**Step 2: Verify frontend build**

```bash
cd ~/workspace/call-monitor-frontend && npx vite build
```
Expected: Build succeeds

**Step 3: Update ROADMAP.md**

Mark Phase 5 items as complete:
```markdown
## Phase 5 - Reporting & Analytics (COMPLETE)
- [x] Export call reports (PDF/CSV)
- [x] Trend analysis over time (per worker, per team)
- [x] Compliance reporting
- [x] Customizable date range filters
- [x] Performance benchmarking
```

**Step 4: Update CLAUDE.md status**

Update the status section:
```
- Phase 5 (reporting & analytics) complete
```

**Step 5: Commit and push**

```bash
git add ROADMAP.md CLAUDE.md
git commit -m "docs: update ROADMAP and CLAUDE.md for Phase 5 completion"
git push
```
