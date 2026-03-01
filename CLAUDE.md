# Call Monitor - CLAUDE.md

## Project Overview
Healthcare/rehab call monitoring app. Workers upload or record patient calls; the system transcribes audio via Whisper and analyzes emotional tone via Claude API. Supervisors review call quality through a dashboard. HIPAA-hardened authentication with role-based access control.

## Tech Stack
- **Backend:** Python 3 / FastAPI / SQLAlchemy / SQLite / Whisper / Anthropic Claude API
- **Auth:** python-jose (JWT) / passlib + bcrypt (passwords)
- **Frontend:** React 18 / Vite / Tailwind CSS / Recharts / Axios
- **Audio processing:** ffmpeg (convert to WAV 16kHz mono)

## Project Structure
```
call-monitor/
├── backend/
│   ├── main.py            # FastAPI app, CORS, routers
│   ├── config.py          # Environment config (incl. auth settings)
│   ├── database.py        # SQLAlchemy engine + models (User, Team, AuditLog, Call, etc.)
│   ├── auth.py            # Password hashing, JWT utils, password validation
│   ├── dependencies.py    # FastAPI deps (get_current_user, role guards, scoping)
│   ├── models/schemas.py  # Pydantic request/response schemas
│   ├── routers/           # API route handlers (auth, users, teams, audit, calls, upload)
│   ├── services/          # Business logic (pipeline, transcription, tonality, audit)
│   ├── tests/             # pytest tests (52 tests)
│   └── storage/audio/     # Uploaded audio files (UUID names)
└── frontend/
    ├── src/
    │   ├── App.jsx         # Router + Navbar + auth routes
    │   ├── api/client.js   # Axios wrapper with Bearer token interceptor
    │   ├── contexts/       # AuthContext (user state, login/logout)
    │   └── components/     # React components
    ├── vite.config.js      # Dev proxy to backend
    └── package.json
```

## Running the App

### Backend (WSL)
```bash
source ~/workspace/call-monitor-venv/bin/activate
cd /mnt/c/Users/ticta/workspace/call-monitor/backend
uvicorn main:app --reload  # http://localhost:8000
```

### Frontend (WSL, separate terminal)
```bash
cd ~/workspace/call-monitor-frontend
npx vite --host  # http://localhost:5173
```

### First-time setup
```bash
# Python venv (must be on Linux filesystem)
python3 -m venv ~/workspace/call-monitor-venv
source ~/workspace/call-monitor-venv/bin/activate
pip install setuptools==75.8.2 wheel
pip install -r /mnt/c/Users/ticta/workspace/call-monitor/backend/requirements.txt

# Frontend (must be on Linux filesystem)
cp -r /mnt/c/Users/ticta/workspace/call-monitor/frontend ~/workspace/call-monitor-frontend
cd ~/workspace/call-monitor-frontend && npm install

# Backend .env (needs ANTHROPIC_API_KEY and SECRET_KEY)
echo "ANTHROPIC_API_KEY=your-key-here" > backend/.env
python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" >> backend/.env
```

### System deps: `sudo apt install ffmpeg nodejs npm python3.12-venv`

## Key Conventions
- **API prefix:** All endpoints under `/api/`
- **Auth:** JWT tokens (access 15min + refresh 7 days), Bearer header
- **Roles:** worker, supervisor, admin — first registered user auto-becomes admin
- **Data scoping:** workers see own calls, supervisors see team's, admins see all
- **Audio served at:** `/audio/{filename}` (static files from storage dir)
- **Processing is async:** Upload returns immediately; pipeline runs in background task
- **Status flow:** pending -> processing -> completed | failed
- **Tonality scores:** -1.0 (negative) to 1.0 (positive)
- **HIPAA:** password complexity (8+ chars, mixed case, number), 15min auto-logoff

## Environment Variables
```
ANTHROPIC_API_KEY=<required for tonality analysis>
SECRET_KEY=<required for JWT signing>
WHISPER_MODEL=base          # tiny, base, small, medium, large
DATABASE_URL=sqlite:///./calls.db
UPLOAD_DIR=./storage/audio
```

## Dependencies to Note
- **ffmpeg** must be installed on the system for audio conversion
- **Whisper** downloads model on first run (~140MB for base)
- **bcrypt** pinned to 4.0.1 (passlib incompatible with 5.x)
- **setuptools** pinned to 75.8.2 (Whisper needs pkg_resources)
- Frontend proxies `/api` and `/audio` to `localhost:8000` in dev

## Current Status
- Phase 1 (core pipeline) complete
- Phase 2 (rating/review) complete
- Phase 3 (auth/roles) complete — 52 backend tests passing
- See ROADMAP.md for upcoming phases
- Next: Phase 4 (live recording)
- WebRTC recording is partially scaffolded but not functional

## When Making Changes
- Backend schemas live in `models/schemas.py` — update when adding DB fields
- New API routes go in `routers/` and get registered in `main.py`
- Auth dependencies in `dependencies.py` — use `get_current_user`, `require_admin`, `require_supervisor_or_admin`, `get_call_scope_filter`
- Audit logging via `services/audit.py` — call `log_audit()` in route handlers
- New services go in `services/` — keep business logic out of routers
- Frontend API calls go through `api/client.js` — don't use raw axios in components
- Tailwind classes for styling — no separate CSS files per component
- After schema changes, delete `calls.db` to recreate (no migration tool yet)
