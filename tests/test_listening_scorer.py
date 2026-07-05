"""Deterministic listening scoring — the core of the free Listening module.

These are pure functions; we build lightweight stand-ins for ListeningQuestion
(only .question_type / .answer_key / .options are read) so no DB is needed.
"""
from types import SimpleNamespace

import pytest

from app.services.listening_scorer import score_answer, calculate_band


def q(question_type, answer_key, options=None):
    return SimpleNamespace(question_type=question_type, answer_key=answer_key, options=options or [])


# ── fill_in_the_blank ─────────────────────────────────────────────────────────
def test_fill_exact_case_insensitive():
    assert score_answer(q("fill_in_the_blank", "Paris"), "paris") is True


def test_fill_wrong():
    assert score_answer(q("fill_in_the_blank", "Paris"), "London") is False


def test_fill_none_answer():
    assert score_answer(q("fill_in_the_blank", "Paris"), None) is False


def test_fill_accepts_any_in_list():
    assert score_answer(q("fill_in_the_blank", ["colour", "color"]), "COLOR") is True


# ── multiple_choices / dropdown (answer_key = option text; user submits order) ─
MC_OPTS = [{"order": 1, "option": "Medical Science"}, {"order": 2, "option": "Law"}]


def test_mcq_order_maps_to_correct_text():
    assert score_answer(q("multiple_choices", "Medical Science", MC_OPTS), 1) is True


def test_mcq_wrong_order():
    assert score_answer(q("multiple_choices", "Medical Science", MC_OPTS), 2) is False


def test_dropdown_correct():
    assert score_answer(q("dropdown", "Law", MC_OPTS), 2) is True


def test_mcq_none_answer():
    assert score_answer(q("multiple_choices", "Law", MC_OPTS), None) is False


# ── multiple_select (set equality, order-independent) ─────────────────────────
MS_OPTS = [{"order": 1, "option": "A"}, {"order": 2, "option": "B"}, {"order": 3, "option": "C"}]


def test_multiselect_exact_set():
    assert score_answer(q("multiple_select", ["A", "B"], MS_OPTS), [1, 2]) is True


def test_multiselect_order_independent():
    assert score_answer(q("multiple_select", ["A", "B"], MS_OPTS), [2, 1]) is True


def test_multiselect_missing_one_is_wrong():
    assert score_answer(q("multiple_select", ["A", "B"], MS_OPTS), [1]) is False


def test_multiselect_extra_one_is_wrong():
    assert score_answer(q("multiple_select", ["A", "B"], MS_OPTS), [1, 2, 3]) is False


def test_multiselect_non_list_answer_is_wrong():
    assert score_answer(q("multiple_select", ["A"], MS_OPTS), 1) is False


# ── edge cases ────────────────────────────────────────────────────────────────
def test_unknown_type_returns_false():
    assert score_answer(q("essay", "x"), "x") is False


def test_empty_answer_key_returns_false():
    assert score_answer(q("fill_in_the_blank", None), "anything") is False


# ── calculate_band (Cambridge table, scaled to 40 questions) ──────────────────
@pytest.mark.parametrize("correct,total,band", [
    (40, 40, 9.0),
    (39, 40, 9.0),
    (30, 40, 7.0),
    (23, 40, 6.0),
    (20, 40, 5.5),
    (1, 40, 3.5),
    (0, 40, 0.0),
])
def test_calculate_band(correct, total, band):
    assert calculate_band(correct, total) == band


def test_calculate_band_zero_total():
    assert calculate_band(0, 0) == 0.0
