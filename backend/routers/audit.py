from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, AuditLog, User
from dependencies import require_admin
from models.schemas import AuditLogResponse

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    results = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first()
        results.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_name=user.name if user else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            timestamp=log.timestamp,
        ))
    return results
