# Phase 4: Live Call Recording - Design Document

## Goal
Enable workers to dial patients directly from Call Monitor using Twilio, with automatic call recording that feeds into the existing transcription/tonality pipeline.

## Context
Workers make phone calls to patients on traditional landlines/cell phones. Currently they must record externally and upload files. Phase 4 integrates Twilio so workers can call from the app with automatic high-quality recording.

## Approach: Twilio Voice SDK (Approach A)
- Twilio Voice JS SDK in the browser for softphone mode
- Twilio REST API for phone-connect mode
- Twilio records calls server-side, delivers recording via webhook
- Backend downloads recording and feeds into existing pipeline (Whisper + Claude)

### Why Twilio
- HIPAA-eligible (requires BAA + Security/Enterprise edition for production)
- Best documentation and community support
- Handles both browser (WebRTC) and phone connection modes
- Automatic server-side recording with high audio quality

---

## Architecture

```
Worker clicks "New Call" in browser
        |
Enters patient phone number + chooses Browser or Phone mode
        |
Backend creates Call record (status: "connecting")
        |
    Browser mode:                        Phone mode:
    Twilio Voice JS SDK connects         Twilio calls worker's phone,
    worker via WebRTC in browser          then bridges to patient
        |
Twilio connects both parties, starts recording
Call status -> "in_progress"
        |
Worker sees live call UI (timer, hang up button)
        |
Call ends (worker hangs up or patient disconnects)
        |
Twilio sends webhook -> backend receives recording URL
        |
Backend downloads recording, saves to storage/audio/
Call status -> "processing"
        |
Existing pipeline runs (Whisper -> Claude -> scores)
        |
Call status -> "completed"
```

---

## Data Model Changes

New fields on the **Call** model:
- `twilio_call_sid` (String, nullable) - Twilio's unique call identifier
- `call_direction` (String, nullable) - "outbound" or "inbound"
- `patient_phone` (String, nullable) - phone number called (PHI - encrypted in production)
- `connection_mode` (String, nullable) - "browser" or "phone"

No new tables. Existing Transcript, TonalityResult, CallScore, Review models unchanged.

### New Environment Variables
```
TWILIO_ACCOUNT_SID=ACxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
TWILIO_TWIML_APP_SID=APxxxxxxx
TWILIO_API_KEY=SKxxxxxxx
TWILIO_API_SECRET=xxxxxxx
```

---

## Backend API

### New Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /api/calls/dial | Auth | Initiate outbound call |
| POST | /api/twilio/token | Auth | Generate Voice SDK access token |
| POST | /api/twilio/voice | Twilio webhook | TwiML instructions for call routing |
| POST | /api/twilio/status | Twilio webhook | Call status updates |
| POST | /api/twilio/recording | Twilio webhook | Recording ready - download and pipeline |

### Dial Flow
1. Worker hits `POST /api/calls/dial` with `{ patient_phone, mode, title }`
2. Backend creates Call record (status: "connecting", source_type: "twilio")
3. Browser mode: returns `{ call_id }`, frontend uses Voice SDK to connect
4. Phone mode: backend calls worker's phone via Twilio REST API, bridges to patient
5. Twilio hits `/api/twilio/voice` for TwiML (connect to patient, enable recording)
6. Twilio hits `/api/twilio/status` as call progresses, backend updates Call status
7. Call ends, Twilio hits `/api/twilio/recording` with recording URL
8. Backend downloads audio, saves to storage/audio/, runs pipeline

### Webhook Security
All `/api/twilio/*` webhooks validate `X-Twilio-Signature` header. No JWT auth needed - signature proves request came from Twilio.

### Audit Logging
- `dial` action logged when call initiated
- `recording_received` logged when audio downloaded from Twilio

---

## Frontend

### New Component: `CallDialer.jsx`
- Phone number input with format validation
- Mode toggle: Browser (headset icon) or Phone (phone icon)
  - Phone mode: additional input for worker's phone number
- "Call" button to initiate
- During call: timer, patient number, "Hang Up" button
- After call: auto-navigates to call detail page

### Browser Mode Flow
1. Fetch Twilio access token from `/api/twilio/token`
2. Initialize `Twilio.Device` with token
3. On "Call" click: `device.connect({ To: patientPhone })`
4. SDK handles WebRTC/audio automatically
5. On disconnect: navigate to call detail (shows processing status)

### Changes to Existing Components
- `App.jsx`: Add `/call` route and "Call" navbar link
- `CallDetail.jsx`: Show connection_mode and call_direction badges

### No Changes To
Dashboard, AudioUpload, CallList, admin panels, auth flow

---

## Twilio Setup (One-Time)

1. Create Twilio account (free trial for development)
2. Buy a phone number (~$1.15/mo)
3. Create a TwiML App (Voice URL: `https://your-server/api/twilio/voice`)
4. Create an API Key (for browser access tokens)
5. For development: use ngrok to expose localhost to Twilio webhooks
6. For production: sign BAA, upgrade to Security/Enterprise edition

---

## Sub-Phasing

### Phase 4a: Backend Twilio Integration
- twilio Python SDK + config variables
- Call model new fields
- /api/calls/dial endpoint
- /api/twilio/* webhook endpoints
- Webhook signature validation
- Recording download -> pipeline
- Tests

### Phase 4b: Frontend Calling UI
- @twilio/voice-sdk package
- CallDialer.jsx component
- Token fetch + Twilio Device init
- Route and navbar link
- Call detail badges

### Phase 4c: Polish & Edge Cases
- Call failure handling (busy, no answer, invalid number)
- Network disconnect recovery
- Phone number E.164 validation
- Update AudioUpload description
- Remove old WebRTCCall.jsx scaffold
- Sync frontend

## Explicitly Deferred
- Inbound calling (patient calls worker)
- Real-time transcription during calls
- Live tonality monitoring
- Twilio conference bridge mode
