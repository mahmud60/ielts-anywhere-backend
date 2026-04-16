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


SYSTEM_PROMPT = """You are a highly experienced IELTS speaking examiner.
Evaluate the candidate's spoken responses against the official IELTS band descriptors.

The four official IELTS speaking criteria are:
- Fluency and Coherence: how naturally and logically the candidate speaks
- Lexical Resource: range, accuracy, and appropriateness of vocabulary
- Grammatical Range and Accuracy: range and accuracy of grammatical structures
- Pronunciation: clarity and intelligibility (estimate from text patterns — repetition, fillers, sentence structure variety)

Important context:
- You are evaluating TYPED responses that represent what the candidate would say
- For pronunciation, estimate based on: sentence variety, use of hedging language, natural discourse markers
- Part 1 answers should be 2-3 sentences (brief but natural)
- Part 2 should be a 1-2 minute monologue (well-developed, 150-250 words)
- Part 3 answers should be 4-6 sentences with supporting reasoning
- Penalise very short answers or responses that ignore the question
- Be realistic — most candidates score between 5.0 and 7.0

Respond ONLY with valid JSON matching this exact structure — no markdown, no extra text:
{
  "part1": {
    "fluency_coherence": 6.5,
    "lexical_resource": 6.0,
    "grammatical_range": 6.0,
    "pronunciation": 6.5,
    "band": 6.5,
    "feedback": "2-3 sentences of specific examiner feedback on Part 1",
    "examiner_notes": "One specific observation about vocabulary or grammar"
  },
  "part2": {
    "fluency_coherence": 7.0,
    "lexical_resource": 6.5,
    "grammatical_range": 6.5,
    "pronunciation": 6.5,
    "band": 6.5,
    "feedback": "2-3 sentences of specific examiner feedback on Part 2",
    "examiner_notes": "One specific observation about discourse development"
  },
  "part3": {
    "fluency_coherence": 6.5,
    "lexical_resource": 7.0,
    "grammatical_range": 6.5,
    "pronunciation": 6.5,
    "band": 6.5,
    "feedback": "2-3 sentences of specific examiner feedback on Part 3",
    "examiner_notes": "One specific observation about argumentation"
  },
  "overall_band": 6.5,
  "improvement_tips": [
    "Specific tip about the candidate's weakest criterion across all parts",
    "Specific tip about a vocabulary or grammar pattern seen in responses",
    "Specific tip about developing answers more fully in a specific part"
  ]
}"""


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
        max_tokens=1200,
        system=SYSTEM_PROMPT,
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