from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.test import TestAttempt
from app.models.ielts_test import IeltsTest, TestSession, SessionStatus
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_VOCAB_KEYWORDS = ("vocab", "lexical", "word", "colloca", "phrasal", "idiom", "terminolog")
_MODULES = ("listening", "reading", "writing", "speaking")


def _session_overall(session: TestSession) -> float | None:
    bands = session.module_bands or {}
    done = [v for v in bands.values() if v is not None]
    return round(sum(done) / len(done) * 2) / 2 if done else None


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = (await db.execute(
        select(TestSession)
        .where(
            TestSession.user_id == current_user.id,
            TestSession.status == SessionStatus.completed,
        )
        .order_by(TestSession.completed_at.desc())
        .limit(20)
    )).scalars().all()

    overalls = [o for s in sessions if (o := _session_overall(s)) is not None]
    total_tests = len(sessions)
    best_overall = max(overalls) if overalls else None
    avg_overall = round(sum(overalls) / len(overalls) * 2) / 2 if overalls else None

    # Fetch test titles for recent sessions
    recent_sessions = []
    for s in sessions[:5]:
        ielts_test = (await db.execute(
            select(IeltsTest).where(IeltsTest.id == s.ielts_test_id)
        )).scalar_one_or_none()
        bands = s.module_bands or {}
        recent_sessions.append({
            "session_id": str(s.id),
            "test_title": ielts_test.title if ielts_test else "Unknown",
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "overall_band": _session_overall(s),
            "module_bands": bands,
        })

    data = {
        "is_pro": current_user.subscription == SubscriptionTier.pro,
        "total_tests": total_tests,
        "best_overall": best_overall,
        "avg_overall": avg_overall,
        "recent_sessions": recent_sessions,
    }

    if current_user.subscription != SubscriptionTier.pro:
        return data

    # --- Pro-only analytics ---

    # Per-module averages across all completed sessions
    module_avgs = {}
    for mod in _MODULES:
        scores = [
            s.module_bands[mod]
            for s in sessions
            if s.module_bands and s.module_bands.get(mod) is not None
        ]
        if scores:
            module_avgs[mod] = round(sum(scores) / len(scores) * 2) / 2

    # Modules ranked by score (weakest first)
    overall_avg = sum(module_avgs.values()) / len(module_avgs) if module_avgs else 0
    weak_modules = [
        {"module": mod, "avg_band": score}
        for mod, score in sorted(module_avgs.items(), key=lambda x: x[1])
        if score < overall_avg
    ]

    # Aggregate tips from the 3 most recent completed sessions
    tips_by_module: dict[str, list[str]] = {m: [] for m in _MODULES}
    vocab_tips: list[str] = []

    for s in sessions[:3]:
        for mod in _MODULES:
            attempt_id = getattr(s, f"{mod}_attempt_id")
            if not attempt_id:
                continue
            attempt = (await db.execute(
                select(TestAttempt).where(TestAttempt.id == attempt_id)
            )).scalar_one_or_none()
            if not attempt or not attempt.improvement_tips:
                continue
            for tip in attempt.improvement_tips:
                if tip not in tips_by_module[mod] and len(tips_by_module[mod]) < 4:
                    tips_by_module[mod].append(tip)
                if mod in ("writing", "speaking"):
                    lower = tip.lower()
                    if any(kw in lower for kw in _VOCAB_KEYWORDS) and tip not in vocab_tips:
                        vocab_tips.append(tip)

    data.update({
        "module_avgs": module_avgs,
        "weak_modules": weak_modules,
        "tips_by_module": tips_by_module,
        "vocab_tips": vocab_tips[:6],
    })

    return data
