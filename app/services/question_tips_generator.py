import anthropic
from app.core.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM = (
    "You are an IELTS coach. Write a single specific, actionable tip (1-2 sentences) "
    "that helps a student get this exact question right next time. "
    "Focus on the listening/reading strategy — what to listen/look for, "
    "common traps for this question type, or how the correct answer is signalled. "
    "Do NOT reveal or restate the answer. Return only the tip text, no preamble."
)

_LISTENING_TYPE_HINTS = {
    "fill_in_the_blank": "Listen for stressed words, spelling cues, and number/name signposting.",
    "multiple_choices":  "Listen for paraphrases of the options, not the exact words.",
    "multiple_select":   "Speakers sometimes mention a point then contradict it — wait for the final stance.",
    "dropdown":          "Match by meaning, not by word — the recording uses synonyms of the options.",
}

_READING_TYPE_HINTS = {
    "tfng":               "Check whether the passage directly supports or contradicts the statement, or simply doesn't mention it.",
    "mcq":                "Locate the relevant paragraph first, then eliminate wrong options using the passage — not general knowledge.",
    "fill":               "Copy the exact word(s) from the passage; paraphrases are wrong.",
    "matching_headings":  "Read the paragraph's main idea first, ignore minor details, then match to the heading.",
    "matching_info":      "Scan for the specific fact or name in each paragraph; it may appear once.",
    "short_answer":       "Use only words from the passage; do not exceed the word limit.",
    "multiple_select":    "All correct options must be stated in the passage, not just implied.",
}


def generate_listening_question_tip(question_type: str, stem: str, answer_key) -> str:
    hint = _LISTENING_TYPE_HINTS.get(question_type, "")
    prompt = (
        f"Question type: {question_type}\n"
        f"Question: {(stem or '(fill in the blank)')[:200]}\n"
        f"Correct answer: {str(answer_key)[:80]}\n"
        f"Strategy hint: {hint}\n\n"
        "Write the tip."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""


def generate_reading_question_tip(
    question_type: str, question_text: str, answer_key, instruction: str = ""
) -> str:
    hint = _READING_TYPE_HINTS.get(question_type, "")
    prompt = (
        f"Question type: {question_type}\n"
        f"Instruction: {(instruction or '')[:150]}\n"
        f"Question: {(question_text or '')[:200]}\n"
        f"Correct answer: {str(answer_key)[:80]}\n"
        f"Strategy hint: {hint}\n\n"
        "Write the tip."
    )
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""