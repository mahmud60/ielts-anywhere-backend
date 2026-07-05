"""Pure helpers in the writing grader (band rounding, word count, JSON cleaning).

The LLM call itself isn't tested here — only the deterministic post-processing.
"""
import json

import pytest

from app.services.writing_grader import _round_band, _count_words, _clean_json


@pytest.mark.parametrize("raw,expected", [
    (6.2, 6.0),
    (6.3, 6.5),
    (6.8, 7.0),
    (7.24, 7.0),
    (7.26, 7.5),
    (0.4, 1.0),   # clamped to the 1.0 floor
    (9.9, 9.0),   # clamped to the 9.0 ceiling
])
def test_round_band(raw, expected):
    assert _round_band(raw) == expected


def test_count_words():
    assert _count_words("hello world  foo") == 3
    assert _count_words("one") == 1
    assert _count_words("   ") == 0
    assert _count_words("") == 0


def test_clean_json_plain():
    assert json.loads(_clean_json('{"a": 1}')) == {"a": 1}


def test_clean_json_fenced_with_lang():
    assert json.loads(_clean_json('```json\n{"a": 1}\n```')) == {"a": 1}


def test_clean_json_fenced_no_lang():
    assert json.loads(_clean_json('```\n{"a": 1}\n```')) == {"a": 1}
