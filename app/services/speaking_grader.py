import json
import re
import anthropic
from app.core.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _round_band(score: float) -> float:
    rounded = round(score * 2) / 2
    return max(1.0, min(9.0, rounded))


def _format_transcript(part_responses: list[dict]) -> str:
    """
    Converts the list of part responses into a readable transcript
    for the AI examiner to evaluate.
    """
    lines = []
    for part in part_responses:
        lines.append(f"\n=== Part {part['part_number']} ===")
        for ex in part["exchanges"]:
            lines.append(f"Examiner: {ex['question']}")
            lines.append(f"Candidate: {ex['answer']}")
            lines.append("")
    return "\n".join(lines)


SYSTEM_PROMPT = """IELTS speaking examiner. Score 3 parts on 4 criteria (1.0-9.0, 0.5 steps). Most candidates: 5.0-7.0.
Criteria: fluency_coherence, lexical_resource, grammatical_range, pronunciation (estimate from text patterns).
Penalise very short or off-topic answers.
Reply ONLY valid JSON, no markdown:
{"part1":{"fluency_coherence":6.0,"lexical_resource":6.0,"grammatical_range":6.0,"pronunciation":6.0,"band":6.0,"feedback":"1-2 sentences"},"part2":{"fluency_coherence":6.0,"lexical_resource":6.0,"grammatical_range":6.0,"pronunciation":6.0,"band":6.0,"feedback":"1-2 sentences"},"part3":{"fluency_coherence":6.0,"lexical_resource":6.0,"grammatical_range":6.0,"pronunciation":6.0,"band":6.0,"feedback":"1-2 sentences"},"overall_band":6.0,"improvement_tips":["tip1","tip2","tip3"]}"""


def grade_speaking(part_responses: list[dict]) -> dict:
    """
    Calls Claude Haiku to evaluate a full speaking transcript.

    part_responses: list of dicts with keys:
      part_number: int
      exchanges: list of {question: str, answer: str}

    Returns parsed grading dict or raises on failure.
    """
    transcript = _format_transcript(part_responses)

    # Count words per part for context
    part_word_counts = []
    for part in part_responses:
        words = sum(len(ex["answer"].split()) for ex in part["exchanges"])
        part_word_counts.append(f"Part {part['part_number']}: ~{words} words total")

    user_message = (
        f"Candidate response word counts: {', '.join(part_word_counts)}\n\n"
        f"Full transcript:\n{transcript}"
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    result = json.loads(_clean_json(raw))

    # Round all scores
    for part_key in ["part1", "part2", "part3"]:
        p = result[part_key]
        p["fluency_coherence"] = _round_band(p["fluency_coherence"])
        p["lexical_resource"] = _round_band(p["lexical_resource"])
        p["grammatical_range"] = _round_band(p["grammatical_range"])
        p["pronunciation"] = _round_band(p["pronunciation"])
        p["band"] = _round_band(p["band"])

    result["overall_band"] = _round_band(result["overall_band"])
    return result