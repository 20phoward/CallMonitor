# Call Monitor - CLAUDE.md

## Project Overview
Healthcare/rehab call monitoring app. Workers upload or record patient calls; the system transcribes audio via Whisper and analyzes emotional tone via Claude API. Supervisors review call quality through a dashboard.

## Tech Stack
- **Backend:** Python 3 / FastAPI / SQLAlchemy / SQLite / Whisper / Anthropic Claude API
- **Frontend:** React 18 / Vite / Tailwind CSS / Recharts / Axios
- **Audio processing:** ffmpeg (convert to WAV 16kHz mono)

## Project Structure
```
call-monitor/
├── backend/
│   ├── main.py            # FastAPI app, CORS, routers
│   ├── config.py          # Environment config
│   ├── database.py        # SQLAlchemy engine + models
│   ├── models/schemas.py  # Pydantic request/response schemas
│   ├── routers/           # API route handlers (calls, upload, webrtc)
│   ├── services/          # Business logic (pipeline, transcription, tonality)
│   └── storage/audio/     # Uploaded audio files (UUID names)
└── frontend/
    ├── src/
    │   ├── App.jsx         # Router + layout
    │   ├── api/client.js   # Axios API wrapper
    │   └── components/     # React components
    ├── vite.config.js      # Dev proxy to backend
    └── package.json
```

## Running the App

### Backend
```bash
cd backend
source venv/bin/activate  # or create: python -m venv venv
pip install -r requirements.txt
# Ensure .env has ANTHROPIC_API_KEY set
uvicorn main:app --reload  # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

## Key Conventions
- **API prefix:** All endpoints under `/api/`
- **Audio served at:** `/audio/{filename}` (static files from storage dir)
- **Processing is async:** Upload returns immediately; pipeline runs in background task
- **Status flow:** pending -> processing -> completed | failed
- **Tonality scores:** -1.0 (negative) to 1.0 (positive)
- **Tone labels:** professional, friendly, aggressive, frustrated, confused, satisfied, empathetic, neutral, anxious, confident

## Environment Variables
```
ANTHROPIC_API_KEY=<required for tonality analysis>
WHISPER_MODEL=base          # tiny, base, small, medium, large
DATABASE_URL=sqlite:///./calls.db
UPLOAD_DIR=./storage/audio
```

## Dependencies to Note
- **ffmpeg** must be installed on the system for audio conversion
- **Whisper** downloads model on first run (~140MB for base)
- Frontend proxies `/api` and `/audio` to `localhost:8000` in dev

## Current Status
- Phase 1 (core pipeline) is complete
- See ROADMAP.md for upcoming phases
- WebRTC recording is partially scaffolded but not functional
- No auth/roles yet

## When Making Changes
- Backend schemas live in `models/schemas.py` — update when adding DB fields
- New API routes go in `routers/` and get registered in `main.py`
- New services go in `services/` — keep business logic out of routers
- Frontend API calls go through `api/client.js` — don't use raw axios in components
- Tailwind classes for styling — no separate CSS files per component
