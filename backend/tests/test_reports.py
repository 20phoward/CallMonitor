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
    total = sum(b["call_count"] for b in data["buckets"])
    assert total == 2  # both calls should appear in some bucket


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
