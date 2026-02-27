import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db, Call, SessionLocal
from models.schemas import CallDetail
from config import STORAGE_DIR, ALLOWED_AUDIO_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from services.pipeline import process_call

router = APIRouter(prefix="/api/calls", tags=["upload"])


def _run_pipeline(call_id: int):
    """Run the processing pipeline in a background thread with its own DB session."""
    db = SessionLocal()
    try:
        process_call(call_id, db)
    finally:
        db.close()


@router.post("/upload", response_model=CallDetail)
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form("Untitled Call"),
    db: Session = Depends(get_db),
):
    # Validate extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}",
        )

    # Read and check size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_SIZE_MB} MB)")

    # Save file
    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = STORAGE_DIR / unique_name
    dest.write_bytes(content)

    # Create DB record
    call = Call(title=title, source_type="upload", audio_filename=unique_name, status="pending")
    db.add(call)
    db.commit()
    db.refresh(call)

    # Kick off background processing
    background_tasks.add_task(_run_pipeline, call.id)

    return call
