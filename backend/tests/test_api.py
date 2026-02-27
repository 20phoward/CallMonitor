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
