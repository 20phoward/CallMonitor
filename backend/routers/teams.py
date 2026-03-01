from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Team, User
from dependencies import get_current_user, require_admin
from models.schemas import TeamCreate, TeamResponse

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=list[TeamResponse])
def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Team).order_by(Team.name).all()


@router.post("", response_model=TeamResponse)
def create_team(
    req: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if db.query(Team).filter(Team.name == req.name).first():
        raise HTTPException(status_code=400, detail="Team already exists")
    team = Team(name=req.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team
