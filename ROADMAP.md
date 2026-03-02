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

## Phase 2 - Call Rating & Review System (COMPLETE — merged PR #1)
- [x] Define scoring rubric (empathy, professionalism, resolution, compliance)
- [x] Auto-generate call scores from tonality analysis (Claude prompt extended)
- [x] Supervisor review interface (approve/flag/override scores)
- [x] Dashboard with review stats (avg rating, needs review, flagged counts)
- [ ] Comment/annotation system on call segments (deferred)
- [ ] Flag critical moments for review (deferred)

## Phase 3 - Authentication & Roles (COMPLETE)
- [x] JWT authentication (login/register with 15min access + 7 day refresh tokens)
- [x] HIPAA-hardened passwords (8+ chars, uppercase, lowercase, number)
- [x] Role-based access (worker, supervisor, admin — first user auto-admin)
- [x] Team management (admin creates teams, assigns users)
- [x] Data scoping (workers see own calls, supervisors see team, admin sees all)
- [x] Calls linked to uploaders (uploaded_by field)
- [x] Full audit log (login, view, upload, delete, review actions with IP tracking)
- [x] 15-minute inactivity auto-logoff (HIPAA compliance)
- [x] Admin panels: user management, team management, audit log viewer
- [x] Frontend auth: login/register, protected routes, token refresh interceptor
- [x] Workers cannot delete calls or submit reviews
- [x] 52 backend tests passing

## Phase 4 - Live Call Recording (COMPLETE)
- [x] Twilio Voice SDK integration (replaced WebRTC scaffold)
- [x] Outbound calling — workers dial patients from the app
- [x] Browser mode (WebRTC softphone via Twilio Voice JS SDK)
- [x] Phone mode (Twilio calls worker's phone, bridges to patient)
- [x] Automatic server-side call recording via Twilio
- [x] Recording download and pipeline integration (Whisper + Claude)
- [x] CallDialer component with call timer and hang up controls
- [x] Twilio webhook endpoints (voice, status, recording)
- [x] E.164 phone number validation
- [x] Webhook signature validation (X-Twilio-Signature)
- [x] Call detail badges (direction, connection mode)
- [x] 71 backend tests passing (19 new)
- [ ] Inbound calling — patient calls worker (deferred)
- [ ] Real-time transcription during calls (deferred)
- [ ] Live tonality monitoring (deferred)

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
