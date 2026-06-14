"""
Seed vocabulary_words table with ~950 IELTS words via Claude Haiku.

Run from the project root:
    python scripts/seed_vocab.py

Skips words that already exist (ON CONFLICT DO NOTHING).
Prints progress after each batch. Safe to re-run.
"""
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.session import AsyncSessionLocal
import app.models  # noqa: F401 — registers all ORM relationships
from app.models.vocabulary import VocabularyWord

_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

BATCHES = [
    # --- Listening (180 words) ---
    {"module": "Listening", "topic": "Places",          "band": "6+",   "count": 25},
    {"module": "Listening", "topic": "Bookings",        "band": "6+",   "count": 20},
    {"module": "Listening", "topic": "Numbers & Data",  "band": "6+",   "count": 20},
    {"module": "Listening", "topic": "Work & Study",    "band": "6.5+", "count": 25},
    {"module": "Listening", "topic": "Transport",       "band": "6+",   "count": 20},
    {"module": "Listening", "topic": "Health & Medical","band": "6.5+", "count": 25},
    {"module": "Listening", "topic": "Campus Life",     "band": "6.5+", "count": 25},
    {"module": "Listening", "topic": "Recreation",      "band": "6+",   "count": 20},
    # --- Reading (250 words) ---
    {"module": "Reading",   "topic": "Science & Research",   "band": "7+",   "count": 30},
    {"module": "Reading",   "topic": "Environment",           "band": "7+",   "count": 25},
    {"module": "Reading",   "topic": "Society & Sociology",   "band": "6.5+", "count": 30},
    {"module": "Reading",   "topic": "Business & Economics",  "band": "7+",   "count": 25},
    {"module": "Reading",   "topic": "History & Culture",     "band": "6.5+", "count": 20},
    {"module": "Reading",   "topic": "Question Skills",       "band": "6.5+", "count": 25},
    {"module": "Reading",   "topic": "Health & Medicine",     "band": "6.5+", "count": 20},
    {"module": "Reading",   "topic": "Psychology",            "band": "7+",   "count": 20},
    {"module": "Reading",   "topic": "Technology",            "band": "7+",   "count": 25},
    {"module": "Reading",   "topic": "Law & Ethics",          "band": "7+",   "count": 15},
    # --- Writing (280 words) ---
    {"module": "Writing",   "topic": "Task 1 Trends",          "band": "6.5+", "count": 35},
    {"module": "Writing",   "topic": "Cause & Effect",         "band": "6.5+", "count": 25},
    {"module": "Writing",   "topic": "Opinion & Argument",     "band": "7+",   "count": 30},
    {"module": "Writing",   "topic": "Contrast & Comparison",  "band": "6.5+", "count": 20},
    {"module": "Writing",   "topic": "Solutions",              "band": "7+",   "count": 25},
    {"module": "Writing",   "topic": "Environment",            "band": "7+",   "count": 30},
    {"module": "Writing",   "topic": "Education",              "band": "7+",   "count": 25},
    {"module": "Writing",   "topic": "Technology",             "band": "7+",   "count": 25},
    {"module": "Writing",   "topic": "Health",                 "band": "6.5+", "count": 25},
    {"module": "Writing",   "topic": "Globalisation",          "band": "7+",   "count": 25},
    {"module": "Writing",   "topic": "Cohesive Devices",       "band": "6.5+", "count": 15},
    # --- Speaking (220 words) ---
    {"module": "Speaking",  "topic": "Society & Culture",       "band": "7+",   "count": 25},
    {"module": "Speaking",  "topic": "Health & Wellbeing",      "band": "6.5+", "count": 25},
    {"module": "Speaking",  "topic": "Technology & Media",      "band": "7+",   "count": 25},
    {"module": "Speaking",  "topic": "People & Relationships",  "band": "7+",   "count": 25},
    {"module": "Speaking",  "topic": "Travel & Places",         "band": "6.5+", "count": 20},
    {"module": "Speaking",  "topic": "Planning & Ambition",     "band": "7+",   "count": 20},
    {"module": "Speaking",  "topic": "Education & Work",        "band": "6.5+", "count": 20},
    {"module": "Speaking",  "topic": "Fluency",                 "band": "7+",   "count": 20},
    {"module": "Speaking",  "topic": "Environment",             "band": "7+",   "count": 20},
    {"module": "Speaking",  "topic": "Arts & Entertainment",    "band": "6.5+", "count": 20},
]


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


async def _generate_batch(module: str, topic: str, band: str, count: int, existing: set) -> list[dict]:
    existing_sample = ", ".join(list(existing)[:80]) if existing else "none"
    prompt = f"""Generate exactly {count} IELTS vocabulary words for:
Module: {module}
Topic: {topic}
Band level: {band}

Return ONLY a JSON array — no markdown, no explanation. Each element:
{{"word":"single word","part_of_speech":"noun/verb/adjective/adverb/conjunction","definition":"clear definition in 12-20 words","example":"one IELTS exam sentence under 18 words","mnemonic":"memory trick under 15 words","collocations":["phrase 1","phrase 2","phrase 3"]}}

Rules:
- {count} distinct words, all genuinely useful for IELTS {module} / {topic}
- Do NOT include: {existing_sample}
- Return exactly {count} objects in a flat JSON array"""

    resp = await _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text
    try:
        data = json.loads(_clean_json(raw))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError as exc:
        print(f"    JSON parse error: {exc} — raw: {raw[:300]}")
        return []


async def _insert_batch(session, items: list[dict], module: str, topic: str, band: str) -> int:
    if not items:
        return 0
    rows = []
    for item in items:
        word = str(item.get("word", "")).strip().lower()
        if not word or len(word) > 100:
            continue
        rows.append({
            "word": word,
            "module": module,
            "topic": topic,
            "band": band,
            "part_of_speech": str(item.get("part_of_speech", ""))[:30],
            "definition": str(item.get("definition", "")),
            "example": str(item.get("example", "")),
            "mnemonic": str(item.get("mnemonic", "")),
            "collocations": item.get("collocations", []),
        })
    if not rows:
        return 0
    stmt = pg_insert(VocabularyWord).values(rows).on_conflict_do_nothing(index_elements=["word"])
    result = await session.execute(stmt)
    return result.rowcount


async def main():
    print("=== IELTS Vocabulary Seeder ===")
    all_words: set[str] = set()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VocabularyWord.word))
        all_words.update(result.scalars().all())
    print(f"Existing words in DB: {len(all_words)}\n")

    total_inserted = 0

    for idx, batch in enumerate(BATCHES, 1):
        module = batch["module"]
        topic  = batch["topic"]
        band   = batch["band"]
        count  = batch["count"]

        print(f"[{idx:02d}/{len(BATCHES)}] {module} / {topic} ({band}) — requesting {count} words...")
        try:
            words = await _generate_batch(module, topic, band, count, all_words)
            print(f"    Claude returned {len(words)} words")

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    n = await _insert_batch(session, words, module, topic, band)
            total_inserted += n
            all_words.update(str(w.get("word", "")).strip().lower() for w in words)
            print(f"    Inserted {n} new words  (total so far: {total_inserted})")
        except Exception as exc:
            print(f"    ERROR: {exc}")

    print(f"\nDone. Total inserted: {total_inserted} | DB unique words tracked: {len(all_words)}")


if __name__ == "__main__":
    asyncio.run(main())
