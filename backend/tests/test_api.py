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
    calls = db.query(Call).all()
    db.add(Review(call_id=calls[0].id, status="approved"))
    db.add(Review(call_id=calls[1].id, status="flagged"))
    db.commit()

    resp = client.get("/api/calls/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avg_rating"] == 7.0
    assert data["approved_count"] == 1
    assert data["flagged_count"] == 1
    assert data["unreviewed_count"] == 1
