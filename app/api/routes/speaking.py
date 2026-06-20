import json
import re
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import httpx
from anthropic import AsyncAnthropic
from livekit.api import AccessToken, VideoGrants

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.speaking import SpeakingTest
from app.models.speaking_attempt import SpeakingAttempt
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.speaking import (
    SpeakingTestOut, SubmitSpeakingRequest,
    SpeakingResultOut, PartScore,
)
from app.api.routes.auth import get_current_user
from app.tasks.grading import grade_speaking_task
from app.services import analytics
from app.core.config import settings

router = APIRouter(prefix="/speaking", tags=["speaking"])


# ─── Existing session-linked routes ────────────────────────────────────────


@router.get("/for-session/{session_id}", response_model=SpeakingTestOut)
async def get_test_for_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    ielts = (await db.execute(
        select(IeltsTest).where(IeltsTest.id == session.ielts_test_id)
    )).scalar_one_or_none()
    if not ielts or not ielts.speaking_test_id:
        raise HTTPException(404, "No speaking test linked to this IELTS test")

    test = (await db.execute(
        select(SpeakingTest)
        .where(SpeakingTest.id == ielts.speaking_test_id)
        .options(selectinload(SpeakingTest.parts))
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Speaking test not found")
    return test



@router.get("/attempts/{attempt_id}", response_model=SpeakingResultOut)
async def get_attempt(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = (await db.execute(
        select(TestAttempt).where(
            TestAttempt.id == attempt_id,
            TestAttempt.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Attempt not found")

    if attempt.status != GradingStatus.complete or not attempt.subscores:
        transcript = None
        if attempt.raw_answers:
            transcript = []
            for part_key in ["part1", "part2", "part3"]:
                part_data = attempt.raw_answers.get(part_key)
                if part_data:
                    for ex in part_data.get("exchanges", []):
                        transcript.append({
                            "part": part_data["part_number"],
                            "question": ex["question"],
                            "answer": ex["answer"],
                        })
        return SpeakingResultOut(
            attempt_id=attempt.id,
            status=attempt.status,
            transcript=transcript,
        )

    s = attempt.subscores
    part_scores = []
    for part_key, part_num, part_type in [
        ("part1", 1, "part1"),
        ("part2", 2, "part2"),
        ("part3", 3, "part3"),
    ]:
        if part_key in s:
            p = s[part_key]
            part_scores.append(PartScore(
                part_number=part_num,
                part_type=part_type,
                fluency_coherence=p["fluency_coherence"],
                lexical_resource=p["lexical_resource"],
                grammatical_range=p["grammatical_range"],
                pronunciation=p["pronunciation"],
                band=p["band"],
                feedback=p["feedback"],
                examiner_notes=p.get("examiner_notes"),
            ))

    transcript = []
    if attempt.raw_answers:
        for part_key in ["part1", "part2", "part3"]:
            part_data = attempt.raw_answers.get(part_key)
            if part_data:
                for ex in part_data.get("exchanges", []):
                    transcript.append({
                        "part": part_data["part_number"],
                        "question": ex["question"],
                        "answer": ex["answer"],
                    })

    return SpeakingResultOut(
        attempt_id=attempt.id,
        status=attempt.status,
        overall_band=attempt.overall_band,
        part_scores=part_scores,
        improvement_tips=attempt.improvement_tips,
        transcript=transcript,
    )


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not settings.OPENAI_API_KEY:
        return {"transcript": ""}

    content = await audio.read()
    filename = audio.filename or "recording.webm"
    mime = audio.content_type or "audio/webm"

    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            files={"file": (filename, content, mime)},
            data={"model": "whisper-1"},
        )

    if not res.is_success:
        raise HTTPException(502, f"Whisper error: {res.text}")

    return {"transcript": res.json().get("text", "")}


@router.get("/attempts")
async def get_attempts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.speaking,
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(20)
    )
    return [
        {
            "id": str(a.id),
            "status": a.status,
            "overall_band": a.overall_band,
            "improvement_tips": a.improvement_tips,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.scalars().all()
    ]


# ─── LiveKit standalone speaking routes ────────────────────────────────────


@router.post("/lk-token")
async def get_livekit_token(
    current_user: User = Depends(get_current_user),
):
    """Return a LiveKit room token so the browser can join a speaking room.
    The LiveKit agent worker picks up the room and starts the IELTS pipeline."""
    if current_user.subscription != SubscriptionTier.pro:
        raise HTTPException(403, "Pro subscription required")
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET or not settings.LIVEKIT_URL:
        raise HTTPException(503, "LiveKit is not configured on this server")

    room_name = f"speaking-{current_user.id}-{int(time.time())}"
    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(str(current_user.id))
        .with_name(getattr(current_user, "display_name", None) or "Candidate")
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    return {"token": token, "room_name": room_name, "ws_url": settings.LIVEKIT_URL}


class _SpeakingMessage(BaseModel):
    role: str       # 'agent' | 'user'
    text: str
    timestamp: float


class _SubmitBody(BaseModel):
    transcript: list[_SpeakingMessage]
    room_name: Optional[str] = None
    test_session_id: Optional[str] = None


def _parse_claude_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\n?", "", text).strip()
    if not text:
        raise ValueError("AI returned an empty response — cannot parse scores")
    # Extract first JSON object in case there is surrounding prose
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in AI response: {text[:200]}")
    return json.loads(match.group())


def _to_float(v):
    return float(v) if v is not None else None


_SCORE_SYSTEM = (
    "You are an expert IELTS examiner. Score this speaking test transcript on all 4 criteria.\n"
    "Return ONLY valid JSON with no markdown fences or explanation:\n"
    "{\n"
    '  "overall_band": <number, 0.5 increments, 1-9>,\n'
    '  "fluency_coherence": {"band": <number>, "feedback": "<2-3 sentences>", "errors": [{"label": "short label", "originalText": "exact phrase from transcript", "correctedText": "improved version", "note": "1 sentence explanation"}]},\n'
    '  "lexical_resource": {"band": <number>, "feedback": "<2-3 sentences>", "errors": [...]},\n'
    '  "grammatical_range": {"band": <number>, "feedback": "<2-3 sentences>", "errors": [...]},\n'
    '  "pronunciation": {"band": <number>, "feedback": "<2-3 sentences>", "errors": [{"label": "short label", "originalText": "word or phrase spoken", "correctedText": "correct pronunciation guide", "note": "pronunciation note"}]},\n'
    '  "examiner_summary": "<2-3 sentence overall summary>"\n'
    "}\n"
    "Rules for errors:\n"
    "- For fluency_coherence, lexical_resource, grammatical_range: originalText must be copied EXACTLY from the candidate's transcript lines\n"
    "- For pronunciation: originalText is the word/phrase; correctedText shows the correct form or stress pattern\n"
    "- Include 1-3 errors per criterion (most impactful only); empty [] is fine\n"
    "- overall_band = average of the 4 criteria bands, rounded to nearest 0.5"
)


@router.post("/submit")
async def submit_speaking(
    body: _SubmitBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a completed speaking session and store the result."""
    transcript_text = "\n".join(
        f"{'Examiner' if m.role == 'agent' else 'Candidate'}: {m.text}"
        for m in body.transcript
    )

    if not transcript_text.strip():
        raise HTTPException(400, "Transcript is empty — nothing to score")

    candidate_lines = [m for m in body.transcript if m.role == "user"]
    if not candidate_lines:
        raise HTTPException(400, "No candidate speech recorded — session may have ended too early")

    attempt = SpeakingAttempt(
        user_id=str(current_user.id),
        status="in_progress",
    )
    db.add(attempt)
    await db.flush()

    try:
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=_SCORE_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Score this IELTS speaking transcript:\n\n{transcript_text}",
            }],
        )
        result = _parse_claude_json(msg.content[0].text)
    except Exception as exc:
        attempt.status = "failed"
        await db.commit()
        raise HTTPException(500, f"Scoring failed: {exc}")

    attempt.status = "completed"
    attempt.transcript = [m.model_dump() for m in body.transcript]
    attempt.overall_band = result["overall_band"]
    attempt.fluency_coherence_band = result["fluency_coherence"]["band"]
    attempt.fluency_coherence_feedback = result["fluency_coherence"]["feedback"]
    attempt.lexical_resource_band = result["lexical_resource"]["band"]
    attempt.lexical_resource_feedback = result["lexical_resource"]["feedback"]
    attempt.grammatical_range_band = result["grammatical_range"]["band"]
    attempt.grammatical_range_feedback = result["grammatical_range"]["feedback"]
    attempt.pronunciation_band = result["pronunciation"]["band"]
    attempt.pronunciation_feedback = result["pronunciation"]["feedback"]
    attempt.examiner_summary = result.get("examiner_summary")
    attempt.errors = {
        "fluency_coherence": result["fluency_coherence"].get("errors", []),
        "lexical_resource": result["lexical_resource"].get("errors", []),
        "grammatical_range": result["grammatical_range"].get("errors", []),
        "pronunciation": result["pronunciation"].get("errors", []),
    }
    attempt.completed_at = datetime.now(timezone.utc)

    analytics.capture(current_user.firebase_uid, "test_completed", {
        "module": "speaking",
        "band": result["overall_band"],
        "fluency_coherence": result["fluency_coherence"]["band"],
        "lexical_resource": result["lexical_resource"]["band"],
        "grammatical_range": result["grammatical_range"]["band"],
        "pronunciation": result["pronunciation"]["band"],
    })

    # Link to test session if provided
    if body.test_session_id:
        test_session = (await db.execute(
            select(TestSession).where(
                TestSession.id == body.test_session_id,
                TestSession.user_id == str(current_user.id),
            )
        )).scalar_one_or_none()
        if test_session:
            test_session.speaking_attempt_id = attempt.id
            bands = dict(test_session.module_bands or {})
            bands["speaking"] = result["overall_band"]
            test_session.module_bands = bands
            if all(test_session.__dict__.get(f"{m}_attempt_id") for m in ["listening", "reading", "writing"]):
                from app.models.ielts_test import SessionStatus
                test_session.status = SessionStatus.completed
                test_session.completed_at = datetime.now(timezone.utc)

    return {"session_id": str(attempt.id), "result": result}


@router.get("/results/{attempt_id}")
async def get_el_speaking_results(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = (await db.execute(
        select(SpeakingAttempt).where(
            SpeakingAttempt.id == PyUUID(attempt_id),
            SpeakingAttempt.user_id == str(current_user.id),
        )
    )).scalar_one_or_none()

    if not attempt:
        raise HTTPException(404, "Result not found")

    errors = attempt.errors or {}
    return {
        "session_id": str(attempt.id),
        "status": attempt.status,
        "overall_band": _to_float(attempt.overall_band),
        "fluency_coherence": {
            "band": _to_float(attempt.fluency_coherence_band),
            "feedback": attempt.fluency_coherence_feedback,
            "errors": errors.get("fluency_coherence", []),
        },
        "lexical_resource": {
            "band": _to_float(attempt.lexical_resource_band),
            "feedback": attempt.lexical_resource_feedback,
            "errors": errors.get("lexical_resource", []),
        },
        "grammatical_range": {
            "band": _to_float(attempt.grammatical_range_band),
            "feedback": attempt.grammatical_range_feedback,
            "errors": errors.get("grammatical_range", []),
        },
        "pronunciation": {
            "band": _to_float(attempt.pronunciation_band),
            "feedback": attempt.pronunciation_feedback,
            "errors": errors.get("pronunciation", []),
        },
        "examiner_summary": attempt.examiner_summary,
        "transcript": attempt.transcript or [],
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
    }


@router.get("/history")
async def get_el_speaking_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(SpeakingAttempt)
        .where(
            SpeakingAttempt.user_id == str(current_user.id),
            SpeakingAttempt.status == "completed",
        )
        .order_by(SpeakingAttempt.created_at.desc())
        .limit(10)
    )).scalars().all()

    return [
        {
            "id": str(a.id),
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "overall_band": _to_float(a.overall_band),
            "examiner_summary": a.examiner_summary,
        }
        for a in rows
    ]