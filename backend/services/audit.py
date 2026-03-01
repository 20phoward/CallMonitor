from fastapi import Request
from sqlalchemy.orm import Session

from database import AuditLog, User


def log_audit(
    db: Session,
    user: User,
    action: str,
    request: Request | None = None,
    resource_type: str | None = None,
    resource_id: int | None = None,
    details: dict | None = None,
):
    ip = None
    if request:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)

    entry = AuditLog(
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip,
    )
    db.add(entry)
    db.commit()
