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


SYSTEM_PROMPT = """You are a highly experienced IELTS writing examiner with 15 years of experience.
You must evaluate IELTS writing responses strictly according to the official band descriptors.

For EACH task you receive, score it on the four official criteria:
- Task Achievement (Task 1) / Task Response (Task 2): how fully and accurately the task is addressed
- Coherence and Cohesion: logical organisation, paragraphing, and use of linking devices
- Lexical Resource: range, accuracy, and appropriacy of vocabulary
- Grammatical Range and Accuracy: range and accuracy of grammatical structures

Scoring rules:
- All scores must be between 1.0 and 9.0 in 0.5 increments
- Be strict and realistic — most test-takers score between 5.0 and 7.0
- The overall task band is the mean of the four criteria, rounded to the nearest 0.5
- Task 2 carries twice the weight of Task 1 in the final overall band

Respond ONLY with valid JSON matching this exact structure — no markdown, no extra text:
{
  "task1": {
    "task_achievement": 6.0,
    "coherence_cohesion": 6.5,
    "lexical_resource": 6.0,
    "grammatical_range": 5.5,
    "band": 6.0,
    "feedback": "2-3 sentences of specific, actionable examiner feedback"
  },
  "task2": {
    "task_achievement": 6.5,
    "coherence_cohesion": 7.0,
    "lexical_resource": 6.5,
    "grammatical_range": 6.0,
    "band": 6.5,
    "feedback": "2-3 sentences of specific, actionable examiner feedback"
  },
  "overall_band": 6.5,
  "improvement_tips": [
    "Specific tip targeting the student's weakest criterion",
    "Specific tip about vocabulary or grammar patterns seen in the responses",
    "Specific tip about task achievement or coherence"
  ]
}"""


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
        max_tokens=1000,
        system=SYSTEM_PROMPT,
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