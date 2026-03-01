import json
from services.tonality import parse_tonality_response


def test_parse_tonality_response_with_rubric():
    raw = json.dumps({
        "overall_sentiment": "positive",
        "overall_score": 0.6,
        "sentiment_over_time": [{"time": 0, "score": 0.5, "label": "friendly"}],
        "key_moments": [{"time": 10, "description": "Greeting", "emotion": "friendly"}],
        "summary": "A positive call.",
        "tone_labels": ["professional", "friendly"],
        "rubric_scores": {
            "empathy": {"score": 7.5, "reasoning": "Good listening"},
            "professionalism": {"score": 8.0, "reasoning": "Clear tone"},
            "resolution": {"score": 6.0, "reasoning": "Partial resolution"},
            "compliance": {"score": 9.0, "reasoning": "No issues"},
        },
    })

    result = parse_tonality_response(raw)

    assert result["overall_sentiment"] == "positive"
    assert result["overall_score"] == 0.6
    assert result["rubric_scores"]["empathy"]["score"] == 7.5
    assert result["rubric_scores"]["compliance"]["reasoning"] == "No issues"


def test_parse_tonality_response_missing_rubric():
    raw = json.dumps({
        "overall_sentiment": "neutral",
        "overall_score": 0.0,
        "sentiment_over_time": [],
        "key_moments": [],
        "summary": "Neutral call.",
        "tone_labels": ["neutral"],
    })

    result = parse_tonality_response(raw)

    assert result["overall_sentiment"] == "neutral"
    assert result["rubric_scores"] is None
