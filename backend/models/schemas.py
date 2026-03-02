from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# --- Auth ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "worker"
    team_id: Optional[int] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- Users ---

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    team_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    role: Optional[str] = None
    team_id: Optional[int] = None


# --- Teams ---

class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Audit Log ---

class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


# --- Twilio / Dialing ---

class DialRequest(BaseModel):
    patient_phone: str
    mode: str = "browser"  # "browser" or "phone"
    worker_phone: Optional[str] = None  # Required when mode="phone"
    title: str = "Phone Call"


class DialResponse(BaseModel):
    call_id: int
    status: str


class TwilioTokenResponse(BaseModel):
    token: str
    identity: str


# --- Transcript ---

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


class TranscriptResponse(BaseModel):
    id: int
    call_id: int
    full_text: str
    segments: Optional[list[TranscriptSegment]] = None

    model_config = {"from_attributes": True}


# --- Tonality ---

class SentimentPoint(BaseModel):
    time: float
    score: float
    label: str


class KeyMoment(BaseModel):
    time: float
    description: str
    emotion: str


class TonalityResponse(BaseModel):
    id: int
    call_id: int
    overall_sentiment: Optional[str] = None
    overall_score: Optional[float] = None
    sentiment_scores: Optional[list[SentimentPoint]] = None
    key_moments: Optional[list[KeyMoment]] = None
    summary: Optional[str] = None
    tone_labels: Optional[list[str]] = None

    model_config = {"from_attributes": True}


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


# --- Call ---

class CallCreate(BaseModel):
    title: str
    source_type: str = "upload"


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
    call_direction: Optional[str] = None
    connection_mode: Optional[str] = None

    model_config = {"from_attributes": True}


class CallDetail(BaseModel):
    id: int
    title: str
    date: datetime
    duration: Optional[float] = None
    status: str
    source_type: str
    audio_filename: Optional[str] = None
    error_message: Optional[str] = None
    call_direction: Optional[str] = None
    connection_mode: Optional[str] = None
    patient_phone: Optional[str] = None
    transcript: Optional[TranscriptResponse] = None
    tonality: Optional[TonalityResponse] = None
    score: Optional[CallScoreResponse] = None
    review: Optional[ReviewResponse] = None

    model_config = {"from_attributes": True}


class CallStatusResponse(BaseModel):
    id: int
    status: str
    error_message: Optional[str] = None


# --- Dashboard ---

class DashboardStats(BaseModel):
    total_calls: int
    completed_calls: int
    avg_sentiment_score: Optional[float] = None
    recent_calls: list[CallSummary]
    avg_rating: Optional[float] = None
    unreviewed_count: int = 0
    approved_count: int = 0
    flagged_count: int = 0
