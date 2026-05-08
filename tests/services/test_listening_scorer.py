import pytest
from unittest.mock import MagicMock
from app.services.listening_scorer import (
    score_answer, calculate_band, generate_tips
)
from app.models.listening import ListeningQuestion, QuestionType

def test_score_answer_mcq_tfng():
    q = MagicMock(spec=ListeningQuestion)
    q.question_type = QuestionType.mcq
    q.answer_key = 1

    assert score_answer(q, "1") is True
    assert score_answer(q, 1) is True
    assert score_answer(q, "2") is False

    q.question_type = QuestionType.tfng
    q.answer_key = 0
    assert score_answer(q, "0") is True
    assert score_answer(q, "abc") is False

def test_score_answer_fill():
    q = MagicMock(spec=ListeningQuestion)
    q.question_type = QuestionType.fill
    q.answer_key = "Station Road"

    assert score_answer(q, "station road") is True
    assert score_answer(q, "  STATION ROAD  ") is True
    assert score_answer(q, "Main Street") is False
    assert score_answer(q, None) is False

def test_score_answer_matching():
    q = MagicMock(spec=ListeningQuestion)
    q.question_type = QuestionType.matching
    q.answer_key = {"0": "Student A", "1": "Supervisor"}

    assert score_answer(q, {"0": "student a", "1": "supervisor"}) is True
    assert score_answer(q, {"0": "student a", "1": "wrong"}) is False
    assert score_answer(q, {"0": "student a"}) is False # Missing key
    assert score_answer(q, "not a dict") is False

def test_calculate_band():
    assert calculate_band(40, 40) == 9.0
    assert calculate_band(30, 40) == 7.0
    assert calculate_band(0, 40) == 3.5
    assert calculate_band(0, 0) == 0.0

def test_generate_tips():
    q1 = MagicMock(spec=ListeningQuestion)
    q1.question_type = QuestionType.mcq
    q1.wrong_answer_tip = "Listen for the distractors."

    q2 = MagicMock(spec=ListeningQuestion)
    q2.question_type = QuestionType.fill
    q2.wrong_answer_tip = None

    tips = generate_tips([q1, q2])
    assert "Listen for the distractors." in tips
    assert "Fill-in-the-blank: listen for stressed words and proper nouns. They are often spelled out letter by letter in the recording." in tips

    assert "Great score!" in generate_tips([])[0]
