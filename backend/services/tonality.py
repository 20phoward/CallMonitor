import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """\
You are an expert call analyst specializing in healthcare and rehabilitation settings. Analyze the following call transcript and provide a structured tonality/sentiment analysis with quality scoring.

<transcript>
{transcript}
</transcript>

Respond with ONLY valid JSON (no markdown, no code fences) in this exact schema:
{{
  "overall_sentiment": "positive" | "negative" | "neutral" | "mixed",
  "overall_score": <float from -1.0 (very negative) to 1.0 (very positive)>,
  "sentiment_over_time": [
    {{"time": <start_seconds>, "score": <float -1 to 1>, "label": "<emotion>"}}
  ],
  "key_moments": [
    {{"time": <seconds>, "description": "<what happened>", "emotion": "<emotion label>"}}
  ],
  "summary": "<2-3 sentence summary of the call>",
  "tone_labels": ["<tone1>", "<tone2>"],
  "rubric_scores": {{
    "empathy": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }},
    "professionalism": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }},
    "resolution": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }},
    "compliance": {{
      "score": <float 0-10>,
      "reasoning": "<1-2 sentences>"
    }}
  }}
}}

For sentiment_over_time, sample at the timestamps of the transcript segments provided.
For tone_labels, pick from: professional, friendly, aggressive, frustrated, confused, satisfied, empathetic, neutral, anxious, confident.

Rubric scoring guide (healthcare/rehab context, 0-10 scale):
- **Empathy & Compassion**: Active listening, validating feelings, patience, emotional support, acknowledging patient concerns.
- **Professionalism**: Courteous tone, clear communication, appropriate boundaries, composed demeanor.
- **Resolution & Follow-through**: Were concerns addressed? Were next steps communicated? Was there a clear plan?
- **Compliance & Safety**: Proper introduction, required disclosures, safety protocols, no red flags, HIPAA awareness.

Score guide: 0-3 Poor, 4-5 Below expectations, 6-7 Meets expectations, 8-9 Exceeds expectations, 10 Exceptional.
"""


def parse_tonality_response(raw: str) -> dict:
    """Parse Claude's JSON response into a structured dict."""
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response: %s", raw[:500])
        return None

    return {
        "overall_sentiment": data.get("overall_sentiment", "neutral"),
        "overall_score": float(data.get("overall_score", 0)),
        "sentiment_scores": data.get("sentiment_over_time", []),
        "key_moments": data.get("key_moments", []),
        "summary": data.get("summary", ""),
        "tone_labels": data.get("tone_labels", []),
        "rubric_scores": data.get("rubric_scores", None),
    }


def analyze_tonality(transcript_text: str, segments: list[dict]) -> dict:
    """Send transcript to Claude for tonality analysis.

    Returns parsed JSON dict with sentiment data.
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder tonality")
        return _placeholder_result(segments)

    # Build transcript with timestamps for context
    lines = []
    for seg in segments:
        ts = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
        speaker = f" ({seg['speaker']})" if seg.get("speaker") else ""
        lines.append(f"{ts}{speaker} {seg['text']}")
    formatted_transcript = "\n".join(lines)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": ANALYSIS_PROMPT.format(transcript=formatted_transcript)},
        ],
    )

    raw = message.content[0].text.strip()
    result = parse_tonality_response(raw)
    if result is None:
        return _placeholder_result(segments)
    return result


def _placeholder_result(segments: list[dict]) -> dict:
    """Return a neutral placeholder when API key is missing."""
    return {
        "overall_sentiment": "neutral",
        "overall_score": 0.0,
        "sentiment_scores": [
            {"time": seg["start"], "score": 0.0, "label": "neutral"}
            for seg in segments[:10]
        ],
        "key_moments": [],
        "summary": "Tonality analysis unavailable (no API key configured).",
        "tone_labels": ["neutral"],
    }
