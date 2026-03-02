from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, Enum, Integer, String, Float, Text, DateTime, ForeignKey, JSON, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import enum

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RoleEnum(str, enum.Enum):
    worker = "worker"
    supervisor = "supervisor"
    admin = "admin"


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    view_call = "view_call"
    view_transcript = "view_transcript"
    upload_call = "upload_call"
    delete_call = "delete_call"
    submit_review = "submit_review"
    update_review = "update_review"
    create_user = "create_user"
    update_role = "update_role"
    dial_call = "dial_call"
    recording_received = "recording_received"


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    members = relationship("User", back_populates="team")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="worker")
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    password_changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="members")
    calls = relationship("Call", back_populates="uploader")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")


class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    duration = Column(Float, nullable=True)  # seconds
    status = Column(String, default="pending")  # pending/connecting/in_progress/processing/completed/failed
    source_type = Column(String, default="upload")  # upload/twilio
    audio_filename = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    twilio_call_sid = Column(String, nullable=True)
    call_direction = Column(String, nullable=True)  # outbound/inbound
    patient_phone = Column(String, nullable=True)
    connection_mode = Column(String, nullable=True)  # browser/phone
    patient_name = Column(String, nullable=True)

    transcript = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    tonality = relationship("TonalityResult", back_populates="call", uselist=False, cascade="all, delete-orphan")
    score = relationship("CallScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    review = relationship("Review", back_populates="call", uselist=False, cascade="all, delete-orphan")
    uploader = relationship("User", back_populates="calls")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    full_text = Column(Text, nullable=False)
    segments = Column(JSON, nullable=True)  # [{start, end, text, speaker}]

    call = relationship("Call", back_populates="transcript")


class TonalityResult(Base):
    __tablename__ = "tonality_results"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    overall_sentiment = Column(String, nullable=True)  # positive/negative/neutral
    overall_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_scores = Column(JSON, nullable=True)  # [{time, score, label}]
    key_moments = Column(JSON, nullable=True)  # [{time, description, emotion}]
    summary = Column(Text, nullable=True)
    tone_labels = Column(JSON, nullable=True)  # ["professional", "friendly", ...]

    call = relationship("Call", back_populates="tonality")


class CallScore(Base):
    __tablename__ = "call_scores"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    empathy = Column(Float, nullable=True)
    professionalism = Column(Float, nullable=True)
    resolution = Column(Float, nullable=True)
    compliance = Column(Float, nullable=True)
    overall_rating = Column(Float, nullable=True)
    category_details = Column(JSON, nullable=True)

    call = relationship("Call", back_populates="score")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    status = Column(String, default="unreviewed")  # unreviewed/approved/flagged
    score_overrides = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    call = relationship("Call", back_populates="review")


def init_db():
    Base.metadata.create_all(bind=engine)
