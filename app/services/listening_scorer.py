from typing import Any
from app.models.listening import ListeningQuestion


def _option_text(question: ListeningQuestion, order: Any) -> str | None:
    """Return the option text for the given order value, or None if not found."""
    for opt in (question.options or []):
        if isinstance(opt, dict):
            if opt.get("order") == order:
                return opt.get("option", "")
        elif isinstance(opt, str):
            return opt
    return None


def _correct_set(answer_key: Any) -> set[str]:
    """Normalise answer_key (string or list) to a set of lowercase stripped strings."""
    if isinstance(answer_key, list):
        return {str(k).lower().strip() for k in answer_key}
    if answer_key is None:
        return set()
    return {str(answer_key).lower().strip()}


def score_answer(question: ListeningQuestion, user_answer: Any) -> bool:
    qt = question.question_type
    correct = _correct_set(question.answer_key)

    if not correct:
        return False

    if qt == "fill_in_the_blank":
        if user_answer is None:
            return False
        return str(user_answer).lower().strip() in correct

    elif qt in ("multiple_choices", "dropdown"):
        if user_answer is None:
            return False
        # user_answer is opt.order (int); look up the option text to compare
        text = _option_text(question, user_answer)
        if text is not None:
            return text.lower().strip() in correct
        # fallback: direct comparison
        return str(user_answer).lower().strip() in correct

    elif qt == "multiple_select":
        if not isinstance(user_answer, list):
            return False
        selected = set()
        for order in user_answer:
            text = _option_text(question, order)
            selected.add((text if text is not None else str(order)).lower().strip())
        return selected == correct

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
            "Great score! Keep practising Sections 3 and 4 - "
            "academic monologue moves faster and requires tracking multiple ideas."
        )
    return tips