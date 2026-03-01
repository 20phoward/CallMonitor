# Phase 3: Authentication & Roles — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add HIPAA-hardened JWT authentication, role-based access control (worker/supervisor/admin), data scoping, and audit logging to Call Monitor.

**Architecture:** FastAPI dependency injection for auth (same pattern as Lionel). JWT access tokens (15min) + refresh tokens (7 days). Scoping via `get_accessible_calls()` dependency. Audit log via explicit `log_audit()` helper in route handlers.

**Tech Stack:** python-jose[cryptography] (JWT), passlib[bcrypt] + bcrypt==4.0.1 (passwords), existing FastAPI/SQLAlchemy/React stack.

---

## Sub-Phase 3a: Backend Auth Infrastructure

### Task 1: Add Auth Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add auth libraries to requirements.txt**

Add these lines to `backend/requirements.txt`:

```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```

**Step 2: Install dependencies**

Run: `source ~/workspace/call-monitor-venv/bin/activate && pip install -r /mnt/c/Users/ticta/workspace/call-monitor/backend/requirements.txt`
Expected: Successfully installed python-jose passlib bcrypt

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add auth dependencies (python-jose, passlib, bcrypt)"
```

---

### Task 2: Auth Config Variables

**Files:**
- Modify: `backend/config.py:1-16`

**Step 1: Add auth config variables**

Add after the existing config variables in `config.py`:

```python
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
```

**Step 2: Add SECRET_KEY to backend/.env**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" >> .env`

**Step 3: Commit**

```bash
git add backend/config.py
git commit -m "chore: add auth config variables"
```

---

### Task 3: User, Team, AuditLog Models + Modify Call

**Files:**
- Modify: `backend/database.py:1-96`

**Step 1: Add new models and modify Call**

Add `Enum` to the sqlalchemy imports at the top of `database.py`. Add `Team`, `User`, and `AuditLog` classes BEFORE the `Call` class. Add `uploaded_by` column and `uploader` relationship to `Call`.

Updated `database.py`:

```python
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, Enum, Boolean, create_engine,
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
    duration = Column(Float, nullable=True)
    status = Column(String, default="pending")
    source_type = Column(String, default="upload")
    audio_filename = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    uploader = relationship("User", back_populates="calls")
    transcript = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    tonality = relationship("TonalityResult", back_populates="call", uselist=False, cascade="all, delete-orphan")
    score = relationship("CallScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    review = relationship("Review", back_populates="call", uselist=False, cascade="all, delete-orphan")


# Transcript, TonalityResult, CallScore, Review remain unchanged
```

Keep the existing `Transcript`, `TonalityResult`, `CallScore`, `Review` classes and `init_db()` exactly as they are.

**Step 2: Verify models load**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -c "from database import Base, User, Team, AuditLog, Call; print('Models OK')"`
Expected: `Models OK`

**Step 3: Commit**

```bash
git add backend/database.py
git commit -m "feat: add User, Team, AuditLog models and Call.uploaded_by"
```

---

### Task 4: Auth Utilities

**Files:**
- Create: `backend/auth.py`

**Step 1: Create auth.py with password hashing, JWT, and password validation**

```python
import re
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def validate_password_complexity(password: str) -> str | None:
    """Returns error message if password doesn't meet HIPAA requirements, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number"
    return None


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "access"}, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "refresh"}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
```

**Step 2: Verify it loads**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -c "from auth import hash_password, verify_password, validate_password_complexity; h = hash_password('Test1234'); print(verify_password('Test1234', h)); print(validate_password_complexity('short'))"`
Expected: `True` then `Password must be at least 8 characters`

**Step 3: Commit**

```bash
git add backend/auth.py
git commit -m "feat: auth utilities (password hashing, JWT, password validation)"
```

---

### Task 5: Auth Dependencies

**Files:**
- Create: `backend/dependencies.py`

**Step 1: Create dependencies.py**

```python
from fastapi import Depends, HTTPException, Header
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
```

**Step 2: Commit**

```bash
git add backend/dependencies.py
git commit -m "feat: auth dependencies (get_current_user, role guards)"
```

---

### Task 6: Auth & User Schemas

**Files:**
- Modify: `backend/models/schemas.py:1-141`

**Step 1: Add auth and user schemas**

Add these classes at the TOP of `models/schemas.py`, after the imports but before the Transcript section:

```python
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
```

**Step 2: Commit**

```bash
git add backend/models/schemas.py
git commit -m "feat: auth, user, team, audit log Pydantic schemas"
```

---

### Task 7: Audit Log Helper

**Files:**
- Create: `backend/services/audit.py`

**Step 1: Create audit helper**

```python
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
```

**Step 2: Commit**

```bash
git add backend/services/audit.py
git commit -m "feat: audit log helper"
```

---

### Task 8: Update Test Fixtures for Auth

**Files:**
- Modify: `backend/tests/conftest.py:1-49`

**Step 1: Add auth fixtures**

Replace the entire `conftest.py` with:

```python
import sys
from unittest.mock import MagicMock

# Mock heavy/optional dependencies before any app imports
if "whisper" not in sys.modules:
    sys.modules["whisper"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db, User, Team
from auth import hash_password
from main import app

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def team(db):
    t = Team(name="Test Team")
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def admin_user(db):
    user = User(
        email="admin@test.com",
        hashed_password=hash_password("Admin123"),
        name="Admin User",
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    from auth import create_access_token
    return create_access_token(admin_user.id)


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def supervisor_user(db, team):
    user = User(
        email="supervisor@test.com",
        hashed_password=hash_password("Super123"),
        name="Supervisor User",
        role="supervisor",
        team_id=team.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def supervisor_token(supervisor_user):
    from auth import create_access_token
    return create_access_token(supervisor_user.id)


@pytest.fixture
def supervisor_headers(supervisor_token):
    return {"Authorization": f"Bearer {supervisor_token}"}


@pytest.fixture
def worker_user(db, team):
    user = User(
        email="worker@test.com",
        hashed_password=hash_password("Worker123"),
        name="Worker User",
        role="worker",
        team_id=team.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def worker_token(worker_user):
    from auth import create_access_token
    return create_access_token(worker_user.id)


@pytest.fixture
def worker_headers(worker_token):
    return {"Authorization": f"Bearer {worker_token}"}
```

**Step 2: Run existing tests to make sure they still pass**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/ -v`
Expected: All 19 existing tests pass

**Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "feat: auth test fixtures (admin, supervisor, worker)"
```

---

### Task 9: Auth Router + Tests

**Files:**
- Create: `backend/routers/auth.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/main.py:9,26-28` (add auth router import and registration)

**Step 1: Write the auth tests**

Create `backend/tests/test_auth.py`:

```python
def test_register_first_user_becomes_admin(client):
    response = client.post("/api/auth/register", json={
        "email": "first@test.com",
        "password": "First123",
        "name": "First User",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "first@test.com"
    assert data["role"] == "admin"


def test_register_second_user_becomes_worker(client, admin_user):
    response = client.post("/api/auth/register", json={
        "email": "second@test.com",
        "password": "Second123",
        "name": "Second User",
    })
    assert response.status_code == 200
    assert response.json()["role"] == "worker"


def test_register_weak_password_rejected(client):
    response = client.post("/api/auth/register", json={
        "email": "weak@test.com",
        "password": "short",
        "name": "Weak Password",
    })
    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


def test_register_no_uppercase_rejected(client):
    response = client.post("/api/auth/register", json={
        "email": "weak@test.com",
        "password": "nouppercase1",
        "name": "No Upper",
    })
    assert response.status_code == 400
    assert "uppercase" in response.json()["detail"]


def test_register_duplicate_email(client, admin_user):
    response = client.post("/api/auth/register", json={
        "email": "admin@test.com",
        "password": "Duplicate1",
        "name": "Duplicate",
    })
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success(client, admin_user):
    response = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client, admin_user):
    response = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "WrongPass1",
    })
    assert response.status_code == 401


def test_refresh_token(client, admin_user):
    login = client.post("/api/auth/login", json={
        "email": "admin@test.com",
        "password": "Admin123",
    })
    refresh_token = login.json()["refresh_token"]
    response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_get_me(client, admin_headers):
    response = client.get("/api/users/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@test.com"


def test_get_me_no_token(client):
    response = client.get("/api/users/me")
    assert response.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_auth.py -v`
Expected: FAIL (no auth router)

**Step 3: Create auth router**

Create `backend/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db, User
from auth import hash_password, verify_password, validate_password_complexity, create_access_token, create_refresh_token, decode_token
from models.schemas import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, UserResponse
from dependencies import get_current_user
from services.audit import log_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Validate password complexity
    error = validate_password_complexity(req.password)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Check duplicate email
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # First user becomes admin
    is_first = db.query(User).count() == 0
    role = "admin" if is_first else req.role

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        name=req.name,
        role=role,
        team_id=req.team_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit(db, user, "create_user", request, "user", user.id)
    return user


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is deactivated")

    log_audit(db, user, "login", request)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )
```

**Step 4: Create users router (for /users/me)**

Create `backend/routers/users.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, User
from dependencies import get_current_user, require_admin
from models.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return db.query(User).order_by(User.created_at).all()


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and req.role and req.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
```

**Step 5: Register routers in main.py**

Add to imports in `main.py`:

```python
from routers import calls, upload, webrtc, auth, users
```

Add after existing router registrations:

```python
app.include_router(auth.router)
app.include_router(users.router)
```

**Step 6: Run auth tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_auth.py -v`
Expected: All 10 tests pass

**Step 7: Run ALL tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/ -v`
Expected: All tests pass (19 existing + 10 new = 29)

**Step 8: Commit**

```bash
git add backend/routers/auth.py backend/routers/users.py backend/main.py backend/tests/test_auth.py
git commit -m "feat: auth router (register/login/refresh) + users router + tests"
```

---

### Task 10: Teams Router + Tests

**Files:**
- Create: `backend/routers/teams.py`
- Create: `backend/tests/test_teams.py`
- Modify: `backend/main.py` (add teams router)

**Step 1: Write team tests**

Create `backend/tests/test_teams.py`:

```python
def test_create_team_admin(client, admin_headers):
    response = client.post("/api/teams", json={"name": "Legal"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Legal"


def test_create_team_non_admin_forbidden(client, worker_headers):
    response = client.post("/api/teams", json={"name": "Legal"}, headers=worker_headers)
    assert response.status_code == 403


def test_create_team_duplicate_name(client, admin_headers, team):
    response = client.post("/api/teams", json={"name": "Test Team"}, headers=admin_headers)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_list_teams(client, admin_headers, team):
    response = client.get("/api/teams", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_teams_no_auth(client):
    response = client.get("/api/teams")
    assert response.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_teams.py -v`
Expected: FAIL

**Step 3: Create teams router**

Create `backend/routers/teams.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Team
from dependencies import get_current_user, require_admin
from models.schemas import TeamCreate, TeamResponse
from database import User

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
```

**Step 4: Register in main.py**

Add `teams` to the routers import and add `app.include_router(teams.router)`.

```python
from routers import calls, upload, webrtc, auth, users, teams
```

```python
app.include_router(teams.router)
```

**Step 5: Run tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_teams.py tests/test_auth.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/routers/teams.py backend/tests/test_teams.py backend/main.py
git commit -m "feat: teams router (list/create) + tests"
```

---

### Task 11: Users Router Tests

**Files:**
- Create: `backend/tests/test_users.py`

**Step 1: Write user management tests**

Create `backend/tests/test_users.py`:

```python
def test_list_users_admin(client, admin_headers, worker_user):
    response = client.get("/api/users", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_users_non_admin_forbidden(client, worker_headers):
    response = client.get("/api/users", headers=worker_headers)
    assert response.status_code == 403


def test_update_user_role(client, admin_headers, worker_user):
    response = client.put(f"/api/users/{worker_user.id}", json={"role": "supervisor"}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "supervisor"


def test_update_user_role_non_admin_forbidden(client, worker_headers, admin_user):
    response = client.put(f"/api/users/{admin_user.id}", json={"role": "worker"}, headers=worker_headers)
    assert response.status_code == 403


def test_cannot_demote_self(client, admin_headers, admin_user):
    response = client.put(f"/api/users/{admin_user.id}", json={"role": "worker"}, headers=admin_headers)
    assert response.status_code == 400
    assert "Cannot demote yourself" in response.json()["detail"]
```

**Step 2: Run tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_users.py -v`
Expected: All 5 pass (users router already created in Task 9)

**Step 3: Commit**

```bash
git add backend/tests/test_users.py
git commit -m "test: user management tests (list, role update, self-demotion guard)"
```

---

### Task 12: Audit Log Router + Tests

**Files:**
- Create: `backend/routers/audit.py`
- Create: `backend/tests/test_audit.py`
- Modify: `backend/main.py` (add audit router)

**Step 1: Write audit log tests**

Create `backend/tests/test_audit.py`:

```python
def test_audit_log_admin(client, admin_headers, admin_user, db):
    # Login creates an audit entry
    client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123"})
    response = client.get("/api/audit-log", headers=admin_headers)
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) >= 1


def test_audit_log_non_admin_forbidden(client, worker_headers):
    response = client.get("/api/audit-log", headers=worker_headers)
    assert response.status_code == 403


def test_audit_log_pagination(client, admin_headers, admin_user):
    # Make several login attempts to generate audit entries
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123"})
    response = client.get("/api/audit-log?limit=2", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_audit.py -v`
Expected: FAIL

**Step 3: Create audit log router**

Create `backend/routers/audit.py`:

```python
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
```

**Step 4: Register in main.py**

```python
from routers import calls, upload, webrtc, auth, users, teams, audit
```

```python
app.include_router(audit.router)
```

**Step 5: Run audit tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/test_audit.py -v`
Expected: All 3 pass

**Step 6: Run ALL tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/ -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add backend/routers/audit.py backend/tests/test_audit.py backend/main.py
git commit -m "feat: audit log router (paginated, admin-only) + tests"
```

---

## Sub-Phase 3b: Retrofit Existing Endpoints

### Task 13: Scoping Dependency

**Files:**
- Modify: `backend/dependencies.py`

**Step 1: Add get_accessible_calls dependency**

Add to `dependencies.py`:

```python
from sqlalchemy import or_


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
```

Also add this import at the top: `from sqlalchemy import or_`

**Step 2: Commit**

```bash
git add backend/dependencies.py
git commit -m "feat: call scoping dependency (worker/supervisor/admin)"
```

---

### Task 14: Retrofit Call Endpoints + Tests

**Files:**
- Modify: `backend/routers/calls.py:1-166`
- Modify: `backend/routers/upload.py:1-59`
- Create: `backend/tests/test_scoping.py`

**Step 1: Write scoping tests**

Create `backend/tests/test_scoping.py`:

```python
from database import Call


def test_worker_sees_only_own_calls(client, worker_headers, worker_user, admin_user, db):
    # Create a call for worker
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    # Create a call for admin
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls", headers=worker_headers)
    assert response.status_code == 200
    titles = [c["title"] for c in response.json()]
    assert "Worker Call" in titles
    assert "Admin Call" not in titles


def test_supervisor_sees_team_calls(client, supervisor_headers, supervisor_user, worker_user, admin_user, db):
    # Worker and supervisor are on same team
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls", headers=supervisor_headers)
    assert response.status_code == 200
    titles = [c["title"] for c in response.json()]
    assert "Worker Call" in titles
    assert "Admin Call" not in titles


def test_admin_sees_all_calls(client, admin_headers, worker_user, admin_user, db):
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_worker_cannot_view_others_call(client, worker_headers, admin_user, db):
    call = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.get(f"/api/calls/{call.id}", headers=worker_headers)
    assert response.status_code == 403


def test_worker_cannot_delete(client, worker_headers, worker_user, db):
    call = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.delete(f"/api/calls/{call.id}", headers=worker_headers)
    assert response.status_code == 403


def test_supervisor_can_delete_team_call(client, supervisor_headers, worker_user, db):
    call = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.delete(f"/api/calls/{call.id}", headers=supervisor_headers)
    assert response.status_code == 200


def test_worker_cannot_submit_review(client, worker_headers, worker_user, db):
    call = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.post(f"/api/calls/{call.id}/review", json={"status": "approved"}, headers=worker_headers)
    assert response.status_code == 403


def test_no_auth_returns_403(client, db):
    call = Call(title="Test", status="completed")
    db.add(call)
    db.commit()
    db.refresh(call)

    response = client.get("/api/calls")
    assert response.status_code == 403


def test_stats_scoped_to_worker(client, worker_headers, worker_user, admin_user, db):
    call1 = Call(title="Worker Call", uploaded_by=worker_user.id, status="completed")
    call2 = Call(title="Admin Call", uploaded_by=admin_user.id, status="completed")
    db.add_all([call1, call2])
    db.commit()

    response = client.get("/api/calls/stats", headers=worker_headers)
    assert response.status_code == 200
    assert response.json()["total_calls"] == 1


def test_health_no_auth_required(client):
    response = client.get("/api/health")
    assert response.status_code == 200
```

**Step 2: Retrofit calls.py**

Replace `backend/routers/calls.py` with auth + scoping + audit:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Call, TonalityResult, CallScore, Review, User
from models.schemas import (
    CallSummary, CallDetail, CallStatusResponse, DashboardStats,
    CallScoreResponse, ReviewRequest, ReviewResponse,
)
from config import STORAGE_DIR
from dependencies import get_current_user, get_call_scope_filter, require_supervisor_or_admin
from services.audit import log_audit

router = APIRouter(prefix="/api/calls", tags=["calls"])


def _check_call_access(call, scope_filter, db):
    """Verify user can access this specific call."""
    from sqlalchemy.orm import Query
    q = db.query(Call).filter(Call.id == call.id)
    q = scope_filter(q, Call, db)
    if q.first() is None:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("", response_model=list[CallSummary])
def list_calls(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    query = db.query(Call).order_by(Call.date.desc())
    query = scope_filter(query, Call, db)
    calls = query.all()

    results = []
    for c in calls:
        sentiment = None
        score = None
        if c.tonality:
            sentiment = c.tonality.overall_sentiment
            score = c.tonality.overall_score
        results.append(CallSummary(
            id=c.id,
            title=c.title,
            date=c.date,
            duration=c.duration,
            status=c.status,
            source_type=c.source_type,
            overall_sentiment=sentiment,
            overall_score=score,
            overall_rating=c.score.overall_rating if c.score else None,
            review_status=c.review.status if c.review else "unreviewed",
        ))
    return results


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    base_query = scope_filter(db.query(Call), Call, db)
    scoped_ids = [c.id for c in base_query.all()]

    if not scoped_ids:
        return DashboardStats(
            total_calls=0, completed_calls=0, avg_sentiment_score=None,
            avg_rating=None, unreviewed_count=0, approved_count=0,
            flagged_count=0, recent_calls=[],
        )

    total = len(scoped_ids)
    completed = base_query.filter(Call.status == "completed").count()

    avg_score = db.query(func.avg(TonalityResult.overall_score)).filter(
        TonalityResult.call_id.in_(scoped_ids)
    ).scalar()
    avg_rating = db.query(func.avg(CallScore.overall_rating)).filter(
        CallScore.call_id.in_(scoped_ids)
    ).scalar()

    approved = db.query(func.count(Review.id)).filter(
        Review.call_id.in_(scoped_ids), Review.status == "approved"
    ).scalar()
    flagged = db.query(func.count(Review.id)).filter(
        Review.call_id.in_(scoped_ids), Review.status == "flagged"
    ).scalar()
    reviewed_total = approved + flagged
    unreviewed = completed - reviewed_total

    recent = base_query.order_by(Call.date.desc()).limit(5).all()
    recent_summaries = []
    for c in recent:
        sentiment = c.tonality.overall_sentiment if c.tonality else None
        score = c.tonality.overall_score if c.tonality else None
        recent_summaries.append(CallSummary(
            id=c.id, title=c.title, date=c.date, duration=c.duration,
            status=c.status, source_type=c.source_type,
            overall_sentiment=sentiment, overall_score=score,
            overall_rating=c.score.overall_rating if c.score else None,
            review_status=c.review.status if c.review else "unreviewed",
        ))

    return DashboardStats(
        total_calls=total, completed_calls=completed,
        avg_sentiment_score=round(avg_score, 3) if avg_score is not None else None,
        avg_rating=round(avg_rating, 2) if avg_rating is not None else None,
        unreviewed_count=max(unreviewed, 0),
        approved_count=approved, flagged_count=flagged,
        recent_calls=recent_summaries,
    )


@router.get("/{call_id}", response_model=CallDetail)
def get_call(
    call_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    log_audit(db, current_user, "view_call", request, "call", call_id)
    return call


@router.get("/{call_id}/status", response_model=CallStatusResponse)
def get_call_status(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    return CallStatusResponse(id=call.id, status=call.status, error_message=call.error_message)


@router.delete("/{call_id}")
def delete_call(
    call_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)

    if call.audio_filename:
        audio_path = STORAGE_DIR / call.audio_filename
        if audio_path.exists():
            audio_path.unlink()
        wav_path = audio_path.with_suffix(".wav")
        if wav_path.exists() and wav_path != audio_path:
            wav_path.unlink()

    log_audit(db, current_user, "delete_call", request, "call", call_id)
    db.delete(call)
    db.commit()
    return {"detail": "Call deleted"}


@router.get("/{call_id}/scores", response_model=CallScoreResponse)
def get_call_scores(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    if not call.score:
        raise HTTPException(status_code=404, detail="Scores not available")
    return call.score


@router.get("/{call_id}/review", response_model=ReviewResponse)
def get_call_review(
    call_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)
    if not call.review:
        raise HTTPException(status_code=404, detail="No review found")
    return call.review


@router.post("/{call_id}/review", response_model=ReviewResponse)
def submit_review(
    call_id: int,
    req: ReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_supervisor_or_admin),
    scope_filter=Depends(get_call_scope_filter),
):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    _check_call_access(call, scope_filter, db)

    review = db.query(Review).filter(Review.call_id == call_id).first()
    action = "update_review" if review else "submit_review"
    if review:
        review.status = req.status
        review.score_overrides = req.score_overrides
        review.notes = req.notes
        review.reviewed_at = datetime.now(timezone.utc)
    else:
        review = Review(
            call_id=call_id,
            status=req.status,
            score_overrides=req.score_overrides,
            notes=req.notes,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)

    log_audit(db, current_user, action, request, "review", call_id)
    db.commit()
    db.refresh(review)
    return review
```

**Step 3: Retrofit upload.py (add uploaded_by)**

Replace `backend/routers/upload.py`:

```python
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from sqlalchemy.orm import Session

from database import get_db, Call, SessionLocal, User
from models.schemas import CallDetail
from config import STORAGE_DIR, ALLOWED_AUDIO_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from services.pipeline import process_call
from dependencies import get_current_user
from services.audit import log_audit

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
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form("Untitled Call"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_UPLOAD_SIZE_MB} MB)")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest = STORAGE_DIR / unique_name
    dest.write_bytes(content)

    call = Call(
        title=title,
        source_type="upload",
        audio_filename=unique_name,
        status="pending",
        uploaded_by=current_user.id,
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    log_audit(db, current_user, "upload_call", request, "call", call.id)
    background_tasks.add_task(_run_pipeline, call.id)

    return call
```

**Step 4: Update existing tests to use auth headers**

Modify `backend/tests/test_api.py` — every test that hits a call endpoint now needs auth headers. Add `admin_headers` fixture parameter to all test functions and pass `headers=admin_headers` to every client call.

Also, when creating calls in test fixtures, set `uploaded_by=admin_user.id` where the test creates Call objects directly.

Check the existing test file first for exact modifications needed.

**Step 5: Run ALL tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && python3 -m pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/routers/calls.py backend/routers/upload.py backend/dependencies.py backend/tests/test_scoping.py backend/tests/test_api.py
git commit -m "feat: retrofit call endpoints with auth, scoping, and audit logging"
```

---

## Sub-Phase 3c: Frontend

### Task 15: Frontend API Client with Auth

**Files:**
- Modify: `frontend/src/api/client.js:1-58`

**Step 1: Add token interceptor and auth functions**

Replace `frontend/src/api/client.js`:

```javascript
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const resp = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
          localStorage.setItem('access_token', resp.data.access_token)
          localStorage.setItem('refresh_token', resp.data.refresh_token)
          originalRequest.headers.Authorization = `Bearer ${resp.data.access_token}`
          return api(originalRequest)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// Auth
export const login = (email, password) => api.post('/auth/login', { email, password })
export const register = (data) => api.post('/auth/register', data)
export const getMe = () => api.get('/users/me')

// Teams
export const fetchTeams = () => api.get('/teams')
export const createTeam = (data) => api.post('/teams', data)

// Users
export const fetchUsers = () => api.get('/users')
export const updateUser = (id, data) => api.put(`/users/${id}`, data)

// Calls (existing, now auth-protected)
export async function fetchCalls() {
  const { data } = await api.get('/calls')
  return data
}

export async function fetchCallDetail(id) {
  const { data } = await api.get(`/calls/${id}`)
  return data
}

export async function fetchCallStatus(id) {
  const { data } = await api.get(`/calls/${id}/status`)
  return data
}

export async function fetchDashboardStats() {
  const { data } = await api.get('/calls/stats')
  return data
}

export async function uploadAudio(file, title) {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title || file.name)
  const { data } = await api.post('/calls/upload', form)
  return data
}

export async function deleteCall(id) {
  const { data } = await api.delete(`/calls/${id}`)
  return data
}

export async function fetchCallScores(id) {
  const { data } = await api.get(`/calls/${id}/scores`)
  return data
}

export async function fetchCallReview(id) {
  const { data } = await api.get(`/calls/${id}/review`)
  return data
}

export async function submitReview(id, review) {
  const { data } = await api.post(`/calls/${id}/review`, review)
  return data
}

// Audit log
export const fetchAuditLog = (params) => api.get('/audit-log', { params })

export function audioUrl(filename) {
  return `/audio/${filename}`
}

export default api
```

**Step 2: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat: API client with Bearer token interceptor and auth functions"
```

---

### Task 16: AuthContext + Login Component

**Files:**
- Create: `frontend/src/contexts/AuthContext.jsx`
- Create: `frontend/src/components/Login.jsx`

**Step 1: Create AuthContext**

Create `frontend/src/contexts/AuthContext.jsx`:

```jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { getMe } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      getMe()
        .then((res) => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const loginUser = (userData, accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    setUser(userData)
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading...</div>
  }

  return (
    <AuthContext.Provider value={{ user, loginUser, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
```

**Step 2: Create Login component**

Create `frontend/src/components/Login.jsx`:

```jsx
import { useState } from 'react'
import { login, register, getMe } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const [isRegister, setIsRegister] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', name: '' })
  const [error, setError] = useState('')
  const { loginUser } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      if (isRegister) {
        await register({ email: form.email, password: form.password, name: form.name })
      }
      const { data } = await login(form.email, form.password)
      localStorage.setItem('access_token', data.access_token)
      const meRes = await getMe()
      loginUser(meRes.data, data.access_token, data.refresh_token)
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h1 className="text-2xl font-bold text-center mb-6 text-indigo-700">Call Monitor</h1>
        <h2 className="text-lg font-semibold mb-4">{isRegister ? 'Create Account' : 'Sign In'}</h2>

        {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <input
              type="text" placeholder="Full Name" required
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          )}
          <input
            type="email" placeholder="Email" required
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <input
            type="password" placeholder="Password" required
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          {isRegister && (
            <p className="text-xs text-gray-500">Min 8 chars, uppercase, lowercase, and number required</p>
          )}
          <button type="submit" className="w-full bg-indigo-600 text-white py-2 rounded-md hover:bg-indigo-700 font-medium">
            {isRegister ? 'Register' : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-4">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
          <button onClick={() => { setIsRegister(!isRegister); setError(''); }} className="text-indigo-600 hover:underline">
            {isRegister ? 'Sign In' : 'Register'}
          </button>
        </p>
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/contexts/AuthContext.jsx frontend/src/components/Login.jsx
git commit -m "feat: AuthContext + Login component"
```

---

### Task 17: ProtectedRoute + InactivityTimer

**Files:**
- Create: `frontend/src/components/ProtectedRoute.jsx`
- Create: `frontend/src/components/InactivityTimer.jsx`

**Step 1: Create ProtectedRoute**

Create `frontend/src/components/ProtectedRoute.jsx`:

```jsx
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute({ children, roles }) {
  const { user } = useAuth()

  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) {
    return <div className="text-center py-8 text-red-600">Access denied</div>
  }
  return children
}
```

**Step 2: Create InactivityTimer**

Create `frontend/src/components/InactivityTimer.jsx`:

```jsx
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'

const TIMEOUT_MS = 15 * 60 * 1000  // 15 minutes
const WARNING_MS = 13 * 60 * 1000  // 13 minutes

export default function InactivityTimer() {
  const { user, logout } = useAuth()
  const [showWarning, setShowWarning] = useState(false)

  const resetTimer = useCallback(() => {
    setShowWarning(false)
  }, [])

  useEffect(() => {
    if (!user) return

    let warningTimeout
    let logoutTimeout

    const startTimers = () => {
      clearTimeout(warningTimeout)
      clearTimeout(logoutTimeout)
      setShowWarning(false)

      warningTimeout = setTimeout(() => setShowWarning(true), WARNING_MS)
      logoutTimeout = setTimeout(() => {
        logout()
        window.location.href = '/login'
      }, TIMEOUT_MS)
    }

    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart']
    const handleActivity = () => {
      startTimers()
    }

    events.forEach((e) => window.addEventListener(e, handleActivity))
    startTimers()

    return () => {
      events.forEach((e) => window.removeEventListener(e, handleActivity))
      clearTimeout(warningTimeout)
      clearTimeout(logoutTimeout)
    }
  }, [user, logout])

  if (!showWarning) return null

  return (
    <div className="fixed bottom-4 right-4 bg-yellow-50 border border-yellow-300 text-yellow-800 px-4 py-3 rounded-lg shadow-lg z-50">
      <p className="text-sm font-medium">Session expiring soon</p>
      <p className="text-xs">Move your mouse or press a key to stay logged in.</p>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/ProtectedRoute.jsx frontend/src/components/InactivityTimer.jsx
git commit -m "feat: ProtectedRoute + InactivityTimer (15min HIPAA auto-logoff)"
```

---

### Task 18: App.jsx + Navbar Updates

**Files:**
- Modify: `frontend/src/App.jsx:1-33`
- Modify: `frontend/src/main.jsx:1-13`

**Step 1: Update main.jsx to wrap with AuthProvider**

Replace `frontend/src/main.jsx`:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
```

**Step 2: Update App.jsx with auth routes and navbar**

Replace `frontend/src/App.jsx`:

```jsx
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import Login from './components/Login'
import ProtectedRoute from './components/ProtectedRoute'
import InactivityTimer from './components/InactivityTimer'
import Dashboard from './components/Dashboard'
import CallList from './components/CallList'
import CallDetail from './components/CallDetail'
import AudioUpload from './components/AudioUpload'
import UserManagement from './components/UserManagement'
import TeamManagement from './components/TeamManagement'
import AuditLog from './components/AuditLog'

function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const roleColors = {
    admin: 'bg-purple-200 text-purple-800',
    supervisor: 'bg-blue-200 text-blue-800',
    worker: 'bg-green-200 text-green-800',
  }

  return (
    <nav className="bg-indigo-700 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="text-xl font-bold tracking-tight">Call Monitor</Link>
          <div className="flex gap-6 text-sm font-medium">
            <Link to="/" className="hover:text-indigo-200">Dashboard</Link>
            <Link to="/calls" className="hover:text-indigo-200">Calls</Link>
            <Link to="/upload" className="hover:text-indigo-200">Upload</Link>
            {user.role === 'admin' && (
              <>
                <Link to="/users" className="hover:text-indigo-200">Users</Link>
                <Link to="/teams" className="hover:text-indigo-200">Teams</Link>
                <Link to="/audit-log" className="hover:text-indigo-200">Audit Log</Link>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span>{user.name}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${roleColors[user.role]}`}>
            {user.role}
          </span>
          <button onClick={handleLogout} className="text-indigo-200 hover:text-white ml-2">
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <InactivityTimer />

      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/calls" element={<ProtectedRoute><CallList /></ProtectedRoute>} />
          <Route path="/calls/:id" element={<ProtectedRoute><CallDetail /></ProtectedRoute>} />
          <Route path="/upload" element={<ProtectedRoute><AudioUpload /></ProtectedRoute>} />
          <Route path="/users" element={<ProtectedRoute roles={['admin']}><UserManagement /></ProtectedRoute>} />
          <Route path="/teams" element={<ProtectedRoute roles={['admin']}><TeamManagement /></ProtectedRoute>} />
          <Route path="/audit-log" element={<ProtectedRoute roles={['admin']}><AuditLog /></ProtectedRoute>} />
        </Routes>
      </main>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/App.jsx frontend/src/main.jsx
git commit -m "feat: App with auth routes, Navbar with role badge + admin links"
```

---

### Task 19: UserManagement + TeamManagement Components

**Files:**
- Create: `frontend/src/components/UserManagement.jsx`
- Create: `frontend/src/components/TeamManagement.jsx`

**Step 1: Create UserManagement**

Create `frontend/src/components/UserManagement.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { fetchUsers, register, fetchTeams, updateUser } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export default function UserManagement() {
  const [users, setUsers] = useState([])
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({ email: '', password: '', name: '', role: 'worker', team_id: '' })
  const [error, setError] = useState('')
  const { user: currentUser } = useAuth()

  const loadData = () => {
    Promise.all([fetchUsers(), fetchTeams()])
      .then(([usersRes, teamsRes]) => {
        setUsers(usersRes.data)
        setTeams(teamsRes.data)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const data = { ...formData }
      if (data.team_id) data.team_id = parseInt(data.team_id)
      else delete data.team_id
      await register(data)
      setFormData({ email: '', password: '', name: '', role: 'worker', team_id: '' })
      setShowForm(false)
      loadData()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user')
    }
  }

  const handleRoleChange = async (userId, newRole) => {
    try {
      await updateUser(userId, { role: newRole })
      loadData()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update role')
    }
  }

  const roleColor = {
    admin: 'text-purple-600 bg-purple-50',
    supervisor: 'text-blue-600 bg-blue-50',
    worker: 'text-green-600 bg-green-50',
  }

  if (loading) return <div className="text-center py-8">Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">User Management</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 transition text-sm">
          {showForm ? 'Cancel' : 'New User'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6 max-w-lg">
          {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
          <form onSubmit={handleCreate} className="space-y-4">
            <input type="text" placeholder="Full Name" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <input type="email" placeholder="Email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <input type="password" placeholder="Password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <p className="text-xs text-gray-500">Min 8 chars, uppercase, lowercase, and number</p>
            <div className="flex space-x-4">
              <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })} className="border border-gray-300 rounded-md px-3 py-2">
                <option value="worker">Worker</option>
                <option value="supervisor">Supervisor</option>
                <option value="admin">Admin</option>
              </select>
              <select value={formData.team_id} onChange={(e) => setFormData({ ...formData, team_id: e.target.value })} className="border border-gray-300 rounded-md px-3 py-2">
                <option value="">No Team</option>
                {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm">Create User</button>
          </form>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Joined</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 font-medium">{u.name}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{u.email}</td>
                <td className="px-6 py-4">
                  {u.id === currentUser?.id ? (
                    <span className={`px-2 py-1 rounded text-xs font-medium ${roleColor[u.role]}`}>
                      {u.role} (you)
                    </span>
                  ) : (
                    <select value={u.role} onChange={(e) => handleRoleChange(u.id, e.target.value)} className={`px-2 py-1 rounded text-xs font-medium border-0 cursor-pointer ${roleColor[u.role]}`}>
                      <option value="admin">admin</option>
                      <option value="supervisor">supervisor</option>
                      <option value="worker">worker</option>
                    </select>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{new Date(u.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

**Step 2: Create TeamManagement**

Create `frontend/src/components/TeamManagement.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { fetchTeams, createTeam } from '../api/client'

export default function TeamManagement() {
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const loadTeams = () => {
    fetchTeams()
      .then((res) => setTeams(res.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadTeams() }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await createTeam({ name })
      setName('')
      setShowForm(false)
      loadTeams()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create team')
    }
  }

  if (loading) return <div className="text-center py-8">Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Team Management</h1>
        <button onClick={() => setShowForm(!showForm)} className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 transition text-sm">
          {showForm ? 'Cancel' : 'New Team'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6 max-w-lg">
          {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{error}</div>}
          <form onSubmit={handleCreate} className="flex gap-4">
            <input type="text" placeholder="Team Name" value={name} onChange={(e) => setName(e.target.value)} className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500" required />
            <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 text-sm">Create</button>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map((t) => (
          <div key={t.id} className="bg-white rounded-lg shadow-sm p-4">
            <h3 className="font-semibold">{t.name}</h3>
            <p className="text-sm text-gray-500">Created {new Date(t.created_at).toLocaleDateString()}</p>
          </div>
        ))}
        {teams.length === 0 && <p className="text-gray-500 col-span-full">No teams yet.</p>}
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/UserManagement.jsx frontend/src/components/TeamManagement.jsx
git commit -m "feat: UserManagement + TeamManagement components"
```

---

### Task 20: AuditLog Component

**Files:**
- Create: `frontend/src/components/AuditLog.jsx`

**Step 1: Create AuditLog component**

Create `frontend/src/components/AuditLog.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { fetchAuditLog } from '../api/client'

export default function AuditLog() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const limit = 50

  const loadLogs = (newOffset) => {
    setLoading(true)
    fetchAuditLog({ limit, offset: newOffset })
      .then((res) => {
        setLogs(res.data)
        setOffset(newOffset)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadLogs(0) }, [])

  const actionColors = {
    login: 'bg-green-100 text-green-800',
    logout: 'bg-gray-100 text-gray-800',
    view_call: 'bg-blue-100 text-blue-800',
    view_transcript: 'bg-blue-100 text-blue-800',
    upload_call: 'bg-indigo-100 text-indigo-800',
    delete_call: 'bg-red-100 text-red-800',
    submit_review: 'bg-yellow-100 text-yellow-800',
    update_review: 'bg-yellow-100 text-yellow-800',
    create_user: 'bg-purple-100 text-purple-800',
    update_role: 'bg-purple-100 text-purple-800',
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Audit Log</h1>

      {loading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Resource</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm font-medium">{log.user_name || 'Unknown'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${actionColors[log.action] || 'bg-gray-100'}`}>
                        {log.action.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {log.resource_type && `${log.resource_type} #${log.resource_id}`}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400 font-mono">{log.ip_address}</td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr><td colSpan="5" className="px-4 py-8 text-center text-gray-500">No audit log entries.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between mt-4">
            <button
              onClick={() => loadLogs(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="text-sm text-indigo-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            >
              Previous
            </button>
            <button
              onClick={() => loadLogs(offset + limit)}
              disabled={logs.length < limit}
              className="text-sm text-indigo-600 hover:underline disabled:text-gray-400 disabled:no-underline"
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/AuditLog.jsx
git commit -m "feat: AuditLog component (paginated, admin-only)"
```

---

### Task 21: Hide Review Panel for Workers

**Files:**
- Modify: `frontend/src/components/CallDetail.jsx:162-176`

**Step 1: Import useAuth and conditionally render ReviewPanel**

Add import at top of `CallDetail.jsx`:

```javascript
import { useAuth } from '../contexts/AuthContext'
```

Add inside the component function, after the existing state declarations:

```javascript
const { user } = useAuth()
```

Replace the quality score section (lines 162-176) with a version that hides ReviewPanel for workers:

```jsx
{/* Quality Score */}
{call.score && (
  <div className="mb-6">
    <h2 className="text-lg font-semibold mb-3">Quality Score</h2>
    <div className={`grid grid-cols-1 ${user?.role !== 'worker' ? 'md:grid-cols-2' : ''} gap-4`}>
      <ScoreCard score={call.score} review={call.review} />
      {user?.role !== 'worker' && (
        <ReviewPanel
          callId={call.id}
          score={call.score}
          review={call.review}
          onReviewSubmitted={() => fetchCallDetail(id).then(setCall)}
        />
      )}
    </div>
  </div>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/components/CallDetail.jsx
git commit -m "feat: hide ReviewPanel from workers in CallDetail"
```

---

### Task 22: Sync Frontend + Run All Tests + Push

**Step 1: Copy frontend to Linux filesystem**

Run: `rm -rf ~/workspace/call-monitor-frontend/src && cp -r /mnt/c/Users/ticta/workspace/call-monitor/frontend/src ~/workspace/call-monitor-frontend/src`

**Step 2: Run all backend tests**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor/backend && source ~/workspace/call-monitor-venv/bin/activate && python3 -m pytest tests/ -v`
Expected: All tests pass (19 existing + new auth/teams/users/audit/scoping tests)

**Step 3: Push to GitHub**

Run: `cd /mnt/c/Users/ticta/workspace/call-monitor && git push origin main`

**Step 4: Delete the existing SQLite database to get a fresh schema**

Run: `rm -f /mnt/c/Users/ticta/workspace/call-monitor/backend/calls.db`

The database will be recreated with the new schema on next backend startup.
