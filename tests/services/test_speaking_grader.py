import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.speaking_grader import (
    _clean_json, _round_band, _format_transcript, grade_speaking
)

def test_clean_json():
    raw = "```json\n{\"key\": \"value\"}\n```"
    assert _clean_json(raw) == "{\"key\": \"value\"}"

def test_round_band():
    # Python's round(12.5) is 12.0 (round to even)
    assert _round_band(6.25) == 6.0
    assert _round_band(6.26) == 6.5
    assert _round_band(7.75) == 8.0

def test_format_transcript():
    part_responses = [
        {
            "part_number": 1,
            "exchanges": [
                {"question": "What is your name?", "answer": "My name is John."},
                {"question": "Where are you from?", "answer": "I am from London."}
            ]
        }
    ]
    transcript = _format_transcript(part_responses)
    assert "=== Part 1 ===" in transcript
    assert "Examiner: What is your name?" in transcript
    assert "Candidate: My name is John." in transcript

@patch("app.services.speaking_grader.client.messages.create")
def test_grade_speaking(mock_create):
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "part1": {
                "fluency_coherence": 6.5,
                "lexical_resource": 6.0,
                "grammatical_range": 6.0,
                "pronunciation": 6.5,
                "band": 6.5,
                "feedback": "...",
                "examiner_notes": "..."
            },
            "part2": {
                "fluency_coherence": 6.5,
                "lexical_resource": 6.0,
                "grammatical_range": 6.0,
                "pronunciation": 6.5,
                "band": 6.5,
                "feedback": "...",
                "examiner_notes": "..."
            },
            "part3": {
                "fluency_coherence": 6.5,
                "lexical_resource": 6.0,
                "grammatical_range": 6.0,
                "pronunciation": 6.5,
                "band": 6.5,
                "feedback": "...",
                "examiner_notes": "..."
            },
            "overall_band": 6.5,
            "improvement_tips": ["Tip 1"]
        }))
    ]
    mock_create.return_value = mock_response

    part_responses = [
        {"part_number": 1, "exchanges": [{"question": "Q", "answer": "A"}]},
        {"part_number": 2, "exchanges": [{"question": "Q", "answer": "A"}]},
        {"part_number": 3, "exchanges": [{"question": "Q", "answer": "A"}]}
    ]

    result = grade_speaking(part_responses)
    assert result["overall_band"] == 6.5
    assert "part1" in result
    assert mock_create.called
