from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

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


class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    duration = Column(Float, nullable=True)  # seconds
    status = Column(String, default="pending")  # pending/processing/completed/failed
    source_type = Column(String, default="upload")  # upload/webrtc
    audio_filename = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    transcript = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    tonality = relationship("TonalityResult", back_populates="call", uselist=False, cascade="all, delete-orphan")
    score = relationship("CallScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    review = relationship("Review", back_populates="call", uselist=False, cascade="all, delete-orphan")


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
