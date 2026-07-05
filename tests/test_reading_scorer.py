"""Deterministic reading scoring — the core of the free Reading module.

Includes a regression test for the short-answer over-scoring fix: a single-word
key must no longer match any verbose answer that merely contains the word.
"""
from types import SimpleNamespace

import pytest

from app.services.reading_scorer import (
    _score_mcq, _score_tfng, _score_fill, _score_short_answer,
    _score_multiple_select, _norm, calculate_band, score_answer,
)
from app.models.reading import ReadingQuestionType


# ── normalisation ─────────────────────────────────────────────────────────────
def test_norm_lowercases_strips_punct_collapses_ws():
    assert _norm("  The  Heat!! ") == "the heat"


# ── short_answer: the over-scoring fix ────────────────────────────────────────
def test_short_answer_exact_match():
    assert _score_short_answer("heat", "heat") is True


def test_short_answer_single_word_not_contained_in_sentence():
    # regression: "heat" must NOT match a verbose answer that only contains it
    assert _score_short_answer("heat", "the heat wave was intense") is False


def test_short_answer_single_word_verbose_wrong():
    assert _score_short_answer("water", "i don't know water maybe") is False


def test_short_answer_multiword_subset_still_lenient():
    assert _score_short_answer("urban heat island", "the urban heat island effect") is True


def test_short_answer_multiword_leading_article():
    assert _score_short_answer("greenhouse effect", "the greenhouse effect") is True


def test_short_answer_list_key():
    assert _score_short_answer(["co2", "carbon dioxide"], "Carbon Dioxide") is True


def test_short_answer_none():
    assert _score_short_answer("heat", None) is False


# ── mcq (legacy int format + Cathoven list-of-text format) ────────────────────
def test_mcq_int_format():
    assert _score_mcq(2, 2) is True
    assert _score_mcq(2, 3) is False


def test_mcq_list_text_format():
    assert _score_mcq(["Apple", "apples"], "apple") is True
    assert _score_mcq(["Apple"], "Orange") is False


def test_mcq_none():
    assert _score_mcq(["A"], None) is False


# ── tfng ──────────────────────────────────────────────────────────────────────
def test_tfng_list_format():
    assert _score_tfng(["TRUE", "T"], "true") is True
    assert _score_tfng(["NOT GIVEN", "NG"], "ng") is True
    assert _score_tfng(["FALSE", "F"], "true") is False


# ── fill (punctuation-insensitive) ────────────────────────────────────────────
def test_fill_punctuation_insensitive():
    assert _score_fill("greenhouse", "Greenhouse.") is True


def test_fill_wrong():
    assert _score_fill("greenhouse", "green house") is False


# ── multiple_select (set equality) ────────────────────────────────────────────
def test_multiple_select_exact_set_order_independent():
    assert _score_multiple_select(["A", "B"], ["b", "a"]) is True


def test_multiple_select_partial_is_wrong():
    assert _score_multiple_select(["A", "B"], ["A"]) is False


# ── score_answer routing (reads question.group.question_type) ─────────────────
def rq(qtype, answer_key):
    return SimpleNamespace(group=SimpleNamespace(question_type=qtype), answer_key=answer_key)


def test_score_answer_routes_tfng():
    assert score_answer(rq(ReadingQuestionType.tfng, ["TRUE"]), "true") is True


def test_score_answer_unknown_type_returns_false():
    assert score_answer(rq("bogus", "x"), "x") is False


# ── calculate_band ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("correct,total,band", [
    (40, 40, 9.0),
    (30, 40, 7.0),
    (10, 40, 4.0),
    (0, 40, 0.0),
])
def test_reading_band(correct, total, band):
    assert calculate_band(correct, total) == band
