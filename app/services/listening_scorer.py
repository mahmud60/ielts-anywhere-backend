from typing import Any
from app.models.listening import ListeningQuestion


def score_answer(question: ListeningQuestion, user_answer: Any) -> bool:
    qt = question.question_type

    if qt == "multiple_choices" or qt == "dropdown":
        # answer_key is the correct option order (int)
        try:
            return int(user_answer) == int(question.answer_key)
        except (TypeError, ValueError):
            return str(user_answer).lower().strip() == str(question.answer_key).lower().strip()

    elif qt == "fill_in_the_blank":
        if user_answer is None:
            return False
        user = str(user_answer).lower().strip()
        correct = str(question.answer_key).lower().strip()
        return user == correct

    elif qt == "multiple_select":
        # answer_key: list of correct option orders; user_answer: list of selected orders
        if not isinstance(user_answer, list) or not isinstance(question.answer_key, list):
            return False
        return set(str(x) for x in user_answer) == set(str(x) for x in question.answer_key)

    return False


def calculate_band(correct: int, total: int) -> float:
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
        "multiple_choices": (
            "Multiple choice: read all options before the audio plays. "
            "The correct answer is usually a paraphrase — not word-for-word."
        ),
        "fill_in_the_blank": (
            "Fill-in-the-blank: listen for stressed words and proper nouns. "
            "They are often spelled out letter by letter in the recording."
        ),
        "multiple_select": (
            "Multiple select: eliminate wrong answers first. "
            "Speakers sometimes mention something then correct themselves."
        ),
        "dropdown": (
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
            tip = generic.get(q.question_type)
            if tip:
                tips.append(tip)
            seen.add(q.question_type)
        if len(tips) >= 4:
            break
    if not tips:
        tips.append(
            "Great score! Keep practising Sections 3 and 4 — "
            "academic monologue moves faster and requires tracking multiple ideas."
        )
    return tips
