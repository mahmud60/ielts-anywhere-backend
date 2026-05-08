import pytest
from unittest.mock import MagicMock
from app.services.reading_scorer import (
    _norm, _score_mcq, _score_tfng, _score_fill,
    _score_matching_headings, _score_matching_info,
    _score_short_answer, calculate_band, generate_tips,
    score_answer
)
from app.models.reading import ReadingQuestion, ReadingQuestionGroup, ReadingQuestionType

def test_norm():
    assert _norm("  Hello World!  ") == "hello world"
    assert _norm("The, quick; brown. fox?") == "the quick brown fox"
    assert _norm("Multiple   Spaces") == "multiple spaces"
    assert _norm(123) == "123"

def test_score_mcq():
    assert _score_mcq(1, "1") is True
    assert _score_mcq(1, 1) is True
    assert _score_mcq(1, "2") is False
    assert _score_mcq("1", "2") is False
    assert _score_mcq(1, "abc") is False

def test_score_tfng():
    # tfng uses _score_mcq
    assert _score_tfng(0, "0") is True
    assert _score_tfng(1, "2") is False

def test_score_fill():
    assert _score_fill("Large City", "large city") is True
    assert _score_fill("Large City", "  LARGE city  ") is True
    assert _score_fill("Large City", "large, city") is True
    assert _score_fill("Large City", "small city") is False
    assert _score_fill("Large City", None) is False

def test_score_matching_headings():
    assert _score_matching_headings("iii", "III") is True
    assert _score_matching_headings("iv", "  iv  ") is True
    assert _score_matching_headings("v", "vi") is False
    assert _score_matching_headings("v", None) is False

def test_score_matching_info():
    assert _score_matching_info("B", "b") is True
    assert _score_matching_info("A", "  A  ") is True
    assert _score_matching_info("C", "D") is False
    assert _score_matching_info("C", None) is False

def test_score_short_answer():
    accepted = ["urban heat island", "the urban heat island effect"]
    assert _score_short_answer(accepted, "urban heat island") is True
    assert _score_short_answer(accepted, "THE urban heat ISLAND effect") is True
    assert _score_short_answer(accepted, "an urban heat island") is True  # because "urban heat island" is subset of "an urban heat island"
    assert _score_short_answer(accepted, "urban island") is False
    assert _score_short_answer("single answer", "single answer") is True
    assert _score_short_answer(accepted, None) is False

def test_calculate_band():
    assert calculate_band(40, 40) == 9.0
    assert calculate_band(39, 40) == 9.0
    assert calculate_band(37, 40) == 8.5
    assert calculate_band(30, 40) == 7.0
    assert calculate_band(20, 40) == 5.5
    assert calculate_band(0, 40) == 3.5
    assert calculate_band(0, 0) == 0.0
    # Proportional scaling
    assert calculate_band(20, 20) == 9.0 # scaled to 40/40

def test_score_answer():
    group = MagicMock(spec=ReadingQuestionGroup)
    group.question_type = ReadingQuestionType.mcq

    question = MagicMock(spec=ReadingQuestion)
    question.group = group
    question.answer_key = 1

    assert score_answer(question, "1") is True
    assert score_answer(question, "2") is False

    group.question_type = "invalid_type"
    assert score_answer(question, "1") is False

def test_generate_tips():
    q1 = MagicMock(spec=ReadingQuestion)
    q1.group.question_type = ReadingQuestionType.mcq
    q1.wrong_answer_tip = "Custom MCQ tip"

    q2 = MagicMock(spec=ReadingQuestion)
    q2.group.question_type = ReadingQuestionType.fill
    q2.wrong_answer_tip = None

    tips = generate_tips([q1, q2])
    assert "Custom MCQ tip" in tips
    assert "Sentence completion: copy words directly from the passage. Check the word limit — exceeding it makes a correct answer wrong." in tips

    # Test empty list
    assert "Excellent!" in generate_tips([])[0]
