# Call Monitor - Roadmap

## Vision
A healthcare/rehab call monitoring platform that transcribes patient calls, analyzes emotional tone, and provides structured ratings so workers and supervisors can review call quality and patient interactions.

---

## Phase 1 - Core Pipeline (COMPLETE)
- [x] Audio file upload with drag-and-drop UI
- [x] Background processing pipeline
- [x] Whisper transcription (local model)
- [x] Claude API tonality/sentiment analysis
- [x] SQLite database with Call, Transcript, TonalityResult models
- [x] Dashboard with statistics overview
- [x] Call list with filtering and sorting
- [x] Call detail view (transcript + sentiment timeline + key moments)
- [x] Status polling during processing
- [x] Supported formats: WAV, MP3, M4A, WebM, OGG, FLAC

## Phase 2 - Call Rating & Review System
- [ ] Define scoring rubric (empathy, professionalism, resolution, compliance)
- [ ] Auto-generate call scores from tonality analysis
- [ ] Worker review interface (approve/flag/annotate calls)
- [ ] Supervisor dashboard with team-level metrics
- [ ] Comment/annotation system on call segments
- [ ] Flag critical moments for review

## Phase 3 - Authentication & Roles
- [ ] User authentication (login/register)
- [ ] Role-based access (worker, supervisor, admin)
- [ ] Assign calls to specific workers/teams
- [ ] Audit trail for reviews and annotations

## Phase 4 - Live Call Recording
- [ ] Complete WebRTC live recording integration
- [ ] Real-time transcription during calls
- [ ] Live tonality monitoring
- [ ] Call timer and controls

## Phase 5 - Reporting & Analytics
- [ ] Export call reports (PDF/CSV)
- [ ] Trend analysis over time (per worker, per team)
- [ ] Compliance reporting
- [ ] Customizable date range filters
- [ ] Performance benchmarking

## Phase 6 - Production Readiness
- [ ] Migrate from SQLite to PostgreSQL
- [ ] Add Redis for task queue (replace background tasks)
- [ ] Containerize with Docker / docker-compose
- [ ] Environment-based configuration (dev/staging/prod)
- [ ] API rate limiting and input validation hardening
- [ ] Logging and monitoring
- [ ] Deployment documentation

## Future Ideas
- Multi-language transcription support
- Custom tonality models fine-tuned for healthcare
- Integration with EHR/EMR systems
- Mobile app for on-the-go review
- Automated alerts for negative sentiment spikes
- Speaker diarization (identify patient vs. worker)
- Batch upload / bulk processing
