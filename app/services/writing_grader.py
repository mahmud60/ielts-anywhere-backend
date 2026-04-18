import json
import re
import anthropic
from app.core.config import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _count_words(text: str) -> int:
    """Counts words the same way IELTS examiners do — split on whitespace."""
    return len(text.strip().split()) if text.strip() else 0


def _clean_json(raw: str) -> str:
    """
    Strips markdown code fences that Claude sometimes wraps around JSON.
    e.g. ```json { ... } ``` → { ... }
    """
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _round_band(score: float) -> float:
    """IELTS bands are in 0.5 increments from 1.0 to 9.0."""
    rounded = round(score * 2) / 2
    return max(1.0, min(9.0, rounded))


SYSTEM_PROMPT = """IELTS writing examiner. Score each task on 4 criteria (1.0-9.0, 0.5 steps). Most candidates: 5.0-7.0. Task 2 = double weight.
Criteria: task_achievement, coherence_cohesion, lexical_resource, grammatical_range.
Reply ONLY valid JSON, no markdown:
{"task1":{"task_achievement":6.0,"coherence_cohesion":6.0,"lexical_resource":6.0,"grammatical_range":6.0,"band":6.0,"feedback":"1-2 sentences"},"task2":{"task_achievement":6.0,"coherence_cohesion":6.0,"lexical_resource":6.0,"grammatical_range":6.0,"band":6.0,"feedback":"1-2 sentences"},"overall_band":6.0,"improvement_tips":["tip1","tip2","tip3"]}"""


def grade_writing(
    task1_prompt: str,
    task1_response: str,
    task2_prompt: str,
    task2_response: str,
    task1_type: str = "task1_academic",
) -> dict:
    """
    Calls Claude Haiku to grade both writing tasks.
    Returns a parsed dict matching the JSON structure above.

    Raises an exception if the API call fails or JSON is unparseable.
    This is called from the Celery task — exceptions trigger retries.
    """
    task1_label = "Task 1 (Academic — graph/chart description)" \
        if task1_type == "task1_academic" \
        else "Task 1 (General — letter writing)"

    user_message = f"""{task1_label}
Prompt: {task1_prompt}
Student response ({_count_words(task1_response)} words):
{task1_response}

---

Task 2 (Discursive Essay)
Prompt: {task2_prompt}
Student response ({_count_words(task2_response)} words):
{task2_response}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    cleaned = _clean_json(raw)
    result = json.loads(cleaned)

    # Validate and round all band scores
    for task_key in ["task1", "task2"]:
        t = result[task_key]
        t["task_achievement"] = _round_band(t["task_achievement"])
        t["coherence_cohesion"] = _round_band(t["coherence_cohesion"])
        t["lexical_resource"] = _round_band(t["lexical_resource"])
        t["grammatical_range"] = _round_band(t["grammatical_range"])
        t["band"] = _round_band(t["band"])

    result["overall_band"] = _round_band(result["overall_band"])
    return result