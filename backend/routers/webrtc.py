"""WebRTC signaling endpoints (stretch goal).

Provides basic signaling for browser-to-browser calls.
A full implementation would use WebSockets; this is a simplified
HTTP-based signaling approach for demonstration purposes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])

# In-memory session store (single-server only)
_sessions: dict[str, dict] = {}


class OfferRequest(BaseModel):
    session_id: str
    sdp: str
    type: str = "offer"


class AnswerRequest(BaseModel):
    session_id: str
    sdp: str
    type: str = "answer"


class IceCandidateRequest(BaseModel):
    session_id: str
    candidate: dict


@router.post("/offer")
def post_offer(req: OfferRequest):
    _sessions[req.session_id] = {
        "offer": {"sdp": req.sdp, "type": req.type},
        "answer": None,
        "ice_candidates": [],
    }
    return {"status": "ok"}


@router.get("/offer/{session_id}")
def get_offer(session_id: str):
    session = _sessions.get(session_id)
    if not session or not session.get("offer"):
        raise HTTPException(404, "No offer found for this session")
    return session["offer"]


@router.post("/answer")
def post_answer(req: AnswerRequest):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session["answer"] = {"sdp": req.sdp, "type": req.type}
    return {"status": "ok"}


@router.get("/answer/{session_id}")
def get_answer(session_id: str):
    session = _sessions.get(session_id)
    if not session or not session.get("answer"):
        raise HTTPException(404, "No answer yet")
    return session["answer"]


@router.post("/ice-candidate")
def post_ice_candidate(req: IceCandidateRequest):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session["ice_candidates"].append(req.candidate)
    return {"status": "ok"}


@router.get("/ice-candidates/{session_id}")
def get_ice_candidates(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session["ice_candidates"]
