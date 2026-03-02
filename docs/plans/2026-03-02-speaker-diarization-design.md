# Speaker Diarization Design

## Goal
Label transcript segments with speaker names (worker vs patient) for Twilio calls using dual-channel audio splitting.

## Scope
- **Twilio calls only** — dual-channel recordings guarantee reliable speaker separation
- Uploaded recordings stay as-is (mono, no speaker labels)

## Approach: Dual-Channel Splitting
Twilio's `record-from-answer-dual` produces stereo WAV where channel 1 (left) = caller (worker), channel 2 (right) = callee (patient). We split with ffmpeg, transcribe each channel separately, then merge by timestamp.

## Data Model Changes
- Add `patient_name` (nullable string) to `Call` model
- Add `patient_name` (optional) to `DialRequest` schema
- Transcript segment `speaker` field (already exists as null) gets populated with names

## Pipeline Changes
For Twilio calls (`source_type == "twilio"`):
1. Split stereo → two mono WAVs (ffmpeg pan filter)
2. Transcribe each channel with Whisper independently
3. Merge segments chronologically, tag with speaker name
4. Build labeled `full_text`: `"Patrick: ... \n Lionel: ..."`
5. Pass labeled transcript to Claude (tonality prompt already handles speaker labels)

For uploads: no change.

## Frontend Changes
- **CallDialer**: Add optional "Patient Name" input (defaults to "Patient")
- **CallDetail**: Color-coded speaker labels in transcript (worker blue, patient green)

## Dependencies
- No new dependencies — uses existing ffmpeg + Whisper
