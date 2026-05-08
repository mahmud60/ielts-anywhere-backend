import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.writing_grader import (
    _count_words, _clean_json, _round_band, grade_writing
)

def test_count_words():
    assert _count_words("Hello world") == 2
    assert _count_words("  One   two three  ") == 3
    assert _count_words("") == 0
    assert _count_words("   ") == 0

def test_clean_json():
    raw = "```json\n{\"key\": \"value\"}\n```"
    assert _clean_json(raw) == "{\"key\": \"value\"}"

    raw = "  {\"key\": \"value\"}  "
    assert _clean_json(raw) == "{\"key\": \"value\"}"

    raw = "```\n{\"key\": \"value\"}\n```"
    assert _clean_json(raw) == "{\"key\": \"value\"}"

def test_round_band():
    # Python's round(12.5) is 12.0 (round to even)
    assert _round_band(6.25) == 6.0
    assert _round_band(6.26) == 6.5
    assert _round_band(6.1) == 6.0
    assert _round_band(6.75) == 7.0
    assert _round_band(9.5) == 9.0
    assert _round_band(0.5) == 1.0

@patch("app.services.writing_grader.client.messages.create")
def test_grade_writing(mock_create):
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "task1": {
                "task_achievement": 6.0,
                "coherence_cohesion": 6.0,
                "lexical_resource": 6.0,
                "grammatical_range": 6.0,
                "band": 6.0,
                "feedback": "Good job"
            },
            "task2": {
                "task_achievement": 7.0,
                "coherence_cohesion": 7.0,
                "lexical_resource": 7.0,
                "grammatical_range": 7.0,
                "band": 7.0,
                "feedback": "Very good"
            },
            "overall_band": 6.5,
            "improvement_tips": ["Tip 1"]
        }))
    ]
    mock_create.return_value = mock_response

    result = grade_writing(
        "Task 1 Prompt", "Task 1 Response",
        "Task 2 Prompt", "Task 2 Response"
    )

    assert result["overall_band"] == 6.5
    assert result["task1"]["band"] == 6.0
    assert result["task2"]["band"] == 7.0
    assert mock_create.called
