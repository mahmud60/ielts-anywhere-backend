import json
import logging
import re
import anthropic
from app.core.config import settings

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SYSTEM = (
    "You are an IELTS coach. Analyse the student's test performance data "
    "and write exactly 3 specific, actionable improvement tips. "
    "Return ONLY a JSON array of 3 strings — no markdown, no preamble."
)


def _listening_prompt(data: dict) -> str:
    band = data.get("band", 0)
    wrong = data.get("total_wrong", 0)
    total = data.get("total_questions", 0)
    by_type = data.get("wrong_by_type", {})
    sections = data.get("section_scores", {})

    # Find weakest section by band score
    weakest_label = ""
    if sections:
        weakest_key = min(sections, key=lambda k: sections[k].get("band", 9))
        weakest_label = f"Part {weakest_key} (band {sections[weakest_key].get('band')})"

    samples = data.get("sample_wrong", [])[:4]
    sample_lines = "\n".join(
        f"  [{s.get('type')}] {s.get('stem', '')[:80]} → correct: {s.get('correct', '')[:50]}"
        for s in samples
    )

    return (
        f"Module: IELTS Listening\n"
        f"Band: {band}/9 | Wrong: {wrong}/{total}\n"
        f"Errors by question type: {json.dumps(by_type)}\n"
        f"Weakest section: {weakest_label or 'n/a'}\n"
        f"Sample wrong questions:\n{sample_lines or '  (none)'}\n\n"
        "Write 3 tips that directly address the patterns above."
    )


def _reading_prompt(data: dict) -> str:
    band = data.get("band", 0)
    wrong = data.get("total_wrong", 0)
    total = data.get("total_questions", 0)
    by_type = data.get("wrong_by_type", {})
    passages = data.get("passage_scores", [])

    weakest_label = ""
    if passages:
        wp = min(passages, key=lambda p: p.get("band", 9))
        weakest_label = f"Passage {wp.get('number')} (band {wp.get('band')})"

    samples = data.get("sample_wrong", [])[:4]
    sample_lines = "\n".join(
        f"  [{s.get('type')}] {s.get('text', '')[:80]} → correct: {s.get('correct', '')[:50]}"
        for s in samples
    )

    return (
        f"Module: IELTS Reading\n"
        f"Band: {band}/9 | Wrong: {wrong}/{total}\n"
        f"Errors by question type: {json.dumps(by_type)}\n"
        f"Weakest passage: {weakest_label or 'n/a'}\n"
        f"Sample wrong questions:\n{sample_lines or '  (none)'}\n\n"
        "Write 3 tips that directly address the patterns above."
    )


def generate_feedback(module: str, data: dict) -> list[str]:
    """
    Call Claude Haiku to produce 3 targeted improvement tips.
    Returns empty list on any error (caller keeps existing rule-based tips).
    """
    try:
        prompt = _listening_prompt(data) if module == "listening" else _reading_prompt(data)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        tips = json.loads(raw)

        if isinstance(tips, list) and tips:
            return [str(t) for t in tips[:5]]
    except Exception:
        logger.warning("LLM feedback generation failed; falling back to rule-based tips", exc_info=True)

    return []