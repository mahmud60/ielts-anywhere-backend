"""
Learn routes — Pro only.
Generates personalised vocabulary and grammar exercises using Claude,
based on the user's recent writing/speaking subscores.
"""

import json
import re
import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.api.routes.auth import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/learn", tags=["learn"])

_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

_MODULES = ("listening", "reading", "writing", "speaking")


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


async def _get_weak_criteria(db: AsyncSession, user_id, modules: tuple) -> dict:
    """Average subscores for the given modules across recent completed attempts."""
    result = await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.module.in_([ModuleType(m) for m in modules]),
            TestAttempt.status == GradingStatus.complete,
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(10)
    )
    attempts = result.scalars().all()

    criteria: dict[str, list[float]] = {}
    for a in attempts:
        if not a.subscores:
            continue
        for part_data in a.subscores.values():
            if not isinstance(part_data, dict):
                continue
            for key, val in part_data.items():
                if isinstance(val, (int, float)) and key not in ("band", "word_count", "part_number"):
                    criteria.setdefault(key, []).append(float(val))

    return {k: round(sum(v) / len(v) * 2) / 2 for k, v in criteria.items() if v}


def _require_pro(user: User):
    if user.subscription != SubscriptionTier.pro:
        raise HTTPException(403, "Pro subscription required.")


@router.post("/vocabulary")
async def get_vocabulary_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate personalised IELTS vocabulary exercises.
    Uses the user's weak lexical_resource scores to tailor the content.
    Pro only — calls Claude Haiku synchronously (~3–5 s).
    """
    _require_pro(current_user)

    criteria = await _get_weak_criteria(db, current_user.id, ("writing", "speaking"))
    lex_score = criteria.get("lexical_resource", 6.0)

    level = "intermediate (B2)" if lex_score < 6.5 else "upper-intermediate (C1)" if lex_score < 7.5 else "advanced (C1+)"
    focus_hint = (
        "Focus on common academic words, topic-specific collocations for IELTS topics "
        "(environment, technology, education, health, globalisation)."
        if lex_score < 7.0
        else "Focus on sophisticated synonyms, idiomatic academic phrases, and precise collocations."
    )

    prompt = f"""IELTS vocab exercises for lexical_resource band {lex_score:.1f} ({level}). {focus_hint}
Reply ONLY valid JSON, no markdown. Generate 4 exercises and 3 phrases:
{{"focus_areas":["area1","area2"],"exercises":[{{"word":"...","part_of_speech":"...","definition":"...","ielts_topics":["..."],"example_sentence":"...","gap_fill":"sentence with _____","gap_fill_answer":"...","collocations":["..."],"usage_tip":"..."}}],"phrases":[{{"phrase":"...","meaning":"...","example":"...","register":"..."}}],"study_tip":"..."}}"""

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(_clean_json(response.content[0].text))


@router.post("/grammar")
async def get_grammar_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate personalised IELTS grammar exercises.
    Uses the user's weak grammatical_range scores to tailor the content.
    Pro only.
    """
    _require_pro(current_user)

    criteria = await _get_weak_criteria(db, current_user.id, ("writing", "speaking"))
    gram_score = criteria.get("grammatical_range", 6.0)

    level = "intermediate" if gram_score < 6.5 else "upper-intermediate" if gram_score < 7.5 else "advanced"
    focus_hint = (
        "Focus on complex sentence structures: conditionals, relative clauses, passive voice, "
        "and cohesive devices — common weak points at band 5–6."
        if gram_score < 7.0
        else "Focus on advanced structures: inversion, cleft sentences, nominalization, "
             "and sophisticated use of modal verbs."
    )

    prompt = f"""IELTS grammar exercises for grammatical_range band {gram_score:.1f} ({level}). {focus_hint}
Reply ONLY valid JSON, no markdown. Generate 4 exercises and 2 patterns:
{{"focus_areas":["area1","area2"],"exercises":[{{"structure":"...","explanation":"...","example":"...","transform_task":"...","model_answer":"...","common_error":"...","ielts_tip":"..."}}],"patterns":[{{"name":"...","when_to_use":"...","active_example":"...","passive_example":"...","ielts_tip":"..."}}],"study_tip":"..."}}"""

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(_clean_json(response.content[0].text))
