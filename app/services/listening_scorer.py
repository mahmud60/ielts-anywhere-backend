import re
from typing import Any
from app.models.listening import ListeningQuestion, QuestionType


def score_answer(question: ListeningQuestion, user_answer: Any) -> bool:
    qt = question.question_type

    if qt == QuestionType.mcq or qt == QuestionType.tfng:
        try:
            return int(user_answer) == int(question.answer_key)
        except (TypeError, ValueError):
            return False

    elif qt == QuestionType.fill:
        if user_answer is None:
            return False
        user = str(user_answer).lower().strip()
        correct = str(question.answer_key).lower().strip()
        return user == correct

    elif qt == QuestionType.matching:
        # answer_key: {"0": "Student A", "1": "Supervisor", "2": "Student B"}
        # user_answer: same structure
        if not isinstance(user_answer, dict) or not isinstance(question.answer_key, dict):
            return False
        for idx, correct_val in question.answer_key.items():
            user_val = str(user_answer.get(str(idx), "")).lower().strip()
            if user_val != str(correct_val).lower().strip():
                return False
        return True

    return False


def calculate_band(correct: int, total: int) -> float:
    """
    Scales to 40 questions then applies the official Cambridge
    IELTS listening band conversion table.
    """
    if total == 0:
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


def generate_tips(wrong_questions: list[ListeningQuestion]) -> list[str]:
    generic = {
        QuestionType.mcq: (
            "MCQ: read all options before the audio plays. "
            "The correct answer is usually a paraphrase — not word-for-word."
        ),
        QuestionType.fill: (
            "Fill-in-the-blank: listen for stressed words and proper nouns. "
            "They are often spelled out letter by letter in the recording."
        ),
        QuestionType.tfng: (
            "True/False/Not Given: 'Not Given' means no evidence in either "
            "direction. Base your answer only on what the audio says."
        ),
        QuestionType.matching: (
            "Matching: listen for synonyms and paraphrases. "
            "Speakers rarely use the exact words from the question sheet."
        ),
    }
    tips = []
    seen = set()
    for q in wrong_questions:
        if q.wrong_answer_tip:
            tips.append(q.wrong_answer_tip)
        elif q.question_type not in seen:
            tips.append(generic[q.question_type])
            seen.add(q.question_type)
        if len(tips) >= 4:
            break
    if not tips:
        tips.append(
            "Great score! Keep practising Sections 3 and 4 — "
            "academic monologue moves faster and requires tracking multiple ideas."
        )
    return tips