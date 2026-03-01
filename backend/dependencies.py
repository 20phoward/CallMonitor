from fastapi import Depends, HTTPException, Header
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db, User
from auth import decode_token


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User not found or inactive")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_supervisor_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("supervisor", "admin"):
        raise HTTPException(status_code=403, detail="Supervisor or admin access required")
    return current_user


def get_call_scope_filter(current_user: User = Depends(get_current_user)):
    """Returns a function that applies scope filtering to a Call query."""
    def apply_filter(query, Call, db):
        if current_user.role == "admin":
            return query
        elif current_user.role == "supervisor":
            team_user_ids = [
                u.id for u in db.query(User).filter(User.team_id == current_user.team_id).all()
            ]
            return query.filter(or_(Call.uploaded_by.in_(team_user_ids), Call.uploaded_by.is_(None)))
        else:
            # Worker: own calls only
            return query.filter(Call.uploaded_by == current_user.id)
    return apply_filter
