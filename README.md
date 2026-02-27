# Call Monitor Service

A service that monitors, transcribes, and tracks tonality of calls. Upload audio files or make WebRTC calls, get automatic transcription via Whisper, and sentiment/tonality analysis via Claude.

## Architecture

- **Backend**: FastAPI (Python) with SQLite database
- **Frontend**: React + Vite + Tailwind CSS
- **Transcription**: OpenAI Whisper (runs locally)
- **Tonality Analysis**: Claude API (Anthropic)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- ffmpeg (for audio conversion)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit environment variables
cp ../.env.example .env
# Edit .env with your ANTHROPIC_API_KEY

uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173`.

## Usage

1. Open the dashboard at `http://localhost:5173`
2. Click **Upload** and drag-and-drop an audio file (WAV, MP3, M4A, WebM, OGG, FLAC)
3. The file will be automatically processed:
   - Converted to WAV (if needed)
   - Transcribed with Whisper
   - Analyzed for tonality/sentiment with Claude
4. View results on the call detail page: transcript, sentiment timeline, key moments, tone labels

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/calls` | List all calls |
| GET | `/api/calls/stats` | Dashboard statistics |
| GET | `/api/calls/{id}` | Full call detail |
| GET | `/api/calls/{id}/status` | Processing status |
| POST | `/api/calls/upload` | Upload audio file |
| DELETE | `/api/calls/{id}` | Delete a call |
| GET | `/api/health` | Health check |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Your Anthropic API key |
| `WHISPER_MODEL` | `base` | Whisper model size: base, small, medium, large |
| `DATABASE_URL` | `sqlite:///./calls.db` | Database connection string |
| `UPLOAD_DIR` | `./storage/audio` | Audio file storage directory |
