import re
from typing import Any
from app.models.reading import ReadingQuestion, ReadingQuestionType


# ── Normalisation ─────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """
    Lowercase, strip punctuation, collapse whitespace.
    Used for fill and short_answer so capitalisation and minor
    punctuation differences don't penalise correct answers.
    """
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


# ── Per-type scorers ──────────────────────────────────────────────────────────

def _as_list(key: Any) -> list:
    """Normalise answer_key to a list for uniform comparison."""
    if isinstance(key, list):
        return key
    return [key]


def _score_mcq(key: Any, user: Any) -> bool:
    # Old format: key is int (option order), user is int.
    # New Cathoven format: key is list of accepted option text strings.
    if isinstance(key, list):
        if user is None:
            return False
        return _norm(str(user)) in [_norm(str(k)) for k in key]
    try:
        return int(user) == int(key)
    except (TypeError, ValueError):
        return False


def _score_tfng(key: Any, user: Any) -> bool:
    # Old format: int. New Cathoven format: ["TRUE","T"] / ["FALSE","F"] / ["NOT GIVEN","NG"].
    if isinstance(key, list):
        if user is None:
            return False
        return _norm(str(user)) in [_norm(str(k)) for k in key]
    return _score_mcq(key, user)


def _score_fill(key: Any, user: Any) -> bool:
    if user is None:
        return False
    user_norm = _norm(str(user))
    return any(user_norm == _norm(str(k)) for k in _as_list(key))


def _score_matching_headings(key: Any, user: Any) -> bool:
    if user is None:
        return False
    user_val = str(user).lower().strip()
    return any(user_val == str(k).lower().strip() for k in _as_list(key))


def _score_matching_info(key: Any, user: Any) -> bool:
    if user is None:
        return False
    user_val = str(user).upper().strip()
    return any(user_val == str(k).upper().strip() for k in _as_list(key))


def _score_multiple_select(key: Any, user: Any) -> bool:
    """
    key: list of accepted option texts (all must match).
    user: list of selected option texts from frontend.
    """
    if user is None:
        return False
    if not isinstance(key, list):
        key = [key]
    if not isinstance(user, list):
        user = [user]
    key_norms = {_norm(str(k)) for k in key}
    user_norms = {_norm(str(u)) for u in user}
    return key_norms == user_norms


def _score_short_answer(key: Any, user: Any) -> bool:
    """
    key: list of accepted answer strings (all lowercase in DB)
    user: the student's typed answer

    Checks exact normalised match OR word-set containment.
    Word-set containment lets "urban heat island" match
    "the urban heat island effect" without being too loose.

    We deliberately avoid fuzzy/Levenshtein matching — IELTS
    short answers require precise language from the passage.
    """
    if user is None:
        return False
    if not isinstance(key, list):
        key = [key]

    user_norm = _norm(str(user))
    user_words = set(user_norm.split())

    for accepted in key:
        accepted_norm = _norm(str(accepted))
        if user_norm == accepted_norm:
            return True
        accepted_words = set(accepted_norm.split())
        if accepted_words and accepted_words.issubset(user_words):
            return True

    return False


# ── Dispatch table ────────────────────────────────────────────────────────────

_SCORERS = {
    ReadingQuestionType.mcq: _score_mcq,
    ReadingQuestionType.tfng: _score_tfng,
    ReadingQuestionType.fill: _score_fill,
    ReadingQuestionType.matching_headings: _score_matching_headings,
    ReadingQuestionType.matching_info: _score_matching_info,
    ReadingQuestionType.short_answer: _score_short_answer,
    ReadingQuestionType.multiple_select: _score_multiple_select,
}


def score_answer(question: ReadingQuestion, user_answer: Any) -> bool:
    """
    Routes to the correct scorer based on the question's group type.
    Note: question.group must be loaded (selectinload) before calling this.
    """
    scorer = _SCORERS.get(question.group.question_type)
    if scorer is None:
        return False
    return scorer(question.answer_key, user_answer)


def calculate_band(correct: int, total: int) -> float:
    """
    Official Cambridge IELTS Academic Reading band table,
    scaled proportionally from 40 questions.
    """
    if total == 0 or correct == 0:
        return 0.0
    scaled = (correct / total) * 40

    if scaled >= 39: return 9.0
    if scaled >= 37: return 8.5
    if scaled >= 35: return 8.0
    if scaled >= 33: return 7.5
    if scaled >= 30: return 7.0
    if scaled >= 27: return 6.5
    if scaled >= 23: return 6.0
    if scaled >= 19: return 5.5
    if scaled >= 15: return 5.0
    if scaled >= 13: return 4.5
    if scaled >= 10: return 4.0
    return 3.5


def generate_tips(wrong_questions: list[ReadingQuestion]) -> list[str]:
    generic = {
        ReadingQuestionType.mcq: (
            "MCQ: eliminate obviously wrong options first. "
            "The correct answer is almost always a paraphrase — "
            "not a word-for-word copy from the passage."
        ),
        ReadingQuestionType.tfng: (
            "True/False/Not Given: 'Not Given' means the passage provides "
            "no evidence in either direction. Never use outside knowledge — "
            "base every answer solely on what the passage states."
        ),
        ReadingQuestionType.fill: (
            "Sentence completion: copy words directly from the passage. "
            "Check the word limit — exceeding it makes a correct answer wrong."
        ),
        ReadingQuestionType.matching_headings: (
            "Matching headings: read the first and last sentence of each "
            "paragraph first — the main idea is almost always there. "
            "Ignore specific details and focus on the central argument."
        ),
        ReadingQuestionType.matching_info: (
            "Matching information: use keywords to scan each paragraph. "
            "Questions are not in passage order — scan the whole text each time."
        ),
        ReadingQuestionType.short_answer: (
            "Short answer: use exact words from the passage. "
            "Never paraphrase — IELTS short answers require passage language."
        ),
        ReadingQuestionType.multiple_select: (
            "Multiple select: read all options carefully before choosing. "
            "All selected answers must be correct — a partially correct selection scores zero."
        ),
    }
    tips: list[str] = []
    seen: set = set()
    for q in wrong_questions:
        qt = q.group.question_type
        if q.wrong_answer_tip:
            tips.append(q.wrong_answer_tip)
        elif qt not in seen:
            tips.append(generic[qt])
            seen.add(qt)
        if len(tips) >= 4:
            break
    if not tips:
        tips.append(
            "Excellent! Maintain your speed — aim for no more than "
            "20 minutes per passage including transferring answers."
        )
    return tips