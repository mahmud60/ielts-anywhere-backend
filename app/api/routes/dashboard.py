from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.ielts_test import IeltsTest, TestSession, SessionStatus
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_VOCAB_KEYWORDS = ("vocab", "lexical", "word", "colloca", "phrasal", "idiom", "terminolog")
_MODULES = ("listening", "reading", "writing", "speaking")

_CRITERIA_LABELS = {
    "task_achievement": "Task Achievement",
    "coherence_cohesion": "Coherence & Cohesion",
    "lexical_resource": "Lexical Resource",
    "grammatical_range": "Grammatical Range",
    "fluency_coherence": "Fluency & Coherence",
    "pronunciation": "Pronunciation",
}


def _session_overall(session: TestSession) -> float | None:
    bands = session.module_bands or {}
    done = [v for v in bands.values() if v is not None]
    return round(sum(done) / len(done) * 2) / 2 if done else None


def _agg_subscores(attempts: list[TestAttempt]) -> dict:
    """
    Aggregate criteria scores across all attempts that have subscores.
    Returns { criterion_key: avg_score }.
    """
    buckets: dict[str, list[float]] = {}
    for a in attempts:
        if not a.subscores:
            continue
        for part_data in a.subscores.values():
            if not isinstance(part_data, dict):
                continue
            for key, val in part_data.items():
                if isinstance(val, (int, float)) and key not in ("band", "word_count", "part_number"):
                    buckets.setdefault(key, []).append(float(val))
    return {k: round(sum(v) / len(v) * 2) / 2 for k, v in buckets.items() if v}


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # All completed sessions, newest first (cap at 20 for history chart)
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

    # Enrich recent 5 sessions with test title
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

    # Lightweight history for the progress chart (all 20)
    score_history = [
        {
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "overall_band": _session_overall(s),
            "module_bands": s.module_bands or {},
        }
        for s in reversed(sessions)   # oldest → newest for chart rendering
        if _session_overall(s) is not None
    ]

    data = {
        "is_pro": current_user.subscription == SubscriptionTier.pro,
        "total_tests": total_tests,
        "best_overall": best_overall,
        "avg_overall": avg_overall,
        "recent_sessions": recent_sessions,
        "score_history": score_history,
    }

    if current_user.subscription != SubscriptionTier.pro:
        return data

    # ── Pro-only analytics ────────────────────────────────────────────────────

    # Module-level averages from session history
    module_avgs = {}
    for mod in _MODULES:
        scores = [
            s.module_bands[mod]
            for s in sessions
            if s.module_bands and s.module_bands.get(mod) is not None
        ]
        if scores:
            module_avgs[mod] = round(sum(scores) / len(scores) * 2) / 2

    overall_avg = sum(module_avgs.values()) / len(module_avgs) if module_avgs else 0
    weak_modules = [
        {"module": mod, "avg_band": score}
        for mod, score in sorted(module_avgs.items(), key=lambda x: x[1])
        if score < overall_avg
    ]

    # ── Criterion-level weakness detection ───────────────────────────────────
    # Pull all completed writing + speaking attempts (richer subscores than L/R)
    all_attempts = (await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module.in_([ModuleType.writing, ModuleType.speaking]),
            TestAttempt.status == GradingStatus.complete,
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(20)
    )).scalars().all()

    # Per-module criterion averages
    weakness_by_module: dict[str, dict] = {}
    for mod in ("writing", "speaking"):
        mod_attempts = [a for a in all_attempts if a.module.value == mod]
        if not mod_attempts:
            continue
        agg = _agg_subscores(mod_attempts)
        if not agg:
            continue
        sorted_criteria = sorted(agg.items(), key=lambda x: x[1])
        weakness_by_module[mod] = {
            "criteria_avgs": {
                k: {"score": v, "label": _CRITERIA_LABELS.get(k, k)}
                for k, v in agg.items()
            },
            "weakest_criterion": sorted_criteria[0][0] if sorted_criteria else None,
            "weakest_label": _CRITERIA_LABELS.get(sorted_criteria[0][0], sorted_criteria[0][0]) if sorted_criteria else None,
            "weakest_score": sorted_criteria[0][1] if sorted_criteria else None,
        }

    # Improvement tips from recent 3 sessions
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
        "weakness_by_module": weakness_by_module,
        "tips_by_module": tips_by_module,
        "vocab_tips": vocab_tips[:6],
    })

    return data
