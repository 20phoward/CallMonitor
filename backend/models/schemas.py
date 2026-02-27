from datetime import datetime
from typing import Optional
from pydantic import BaseModel


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
    transcript: Optional[TranscriptResponse] = None
    tonality: Optional[TonalityResponse] = None

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
