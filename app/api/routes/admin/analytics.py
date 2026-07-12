from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.ielts_test import IeltsTest, TestSession
from app.models.listening import ListeningTest
from app.models.reading import ReadingTest
from app.models.writing import WritingTest
from app.models.speaking import SpeakingTest
from .deps import require_admin

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Quick stats for the admin dashboard home screen."""
    total_users = (await db.execute(
        select(func.count(User.id))
    )).scalar()

    pro_users = (await db.execute(
        select(func.count(User.id)).where(User.subscription == SubscriptionTier.pro)
    )).scalar()

    total_tests = (await db.execute(
        select(func.count(IeltsTest.id))
    )).scalar()

    return {
        "total_users": total_users,
        "pro_users": pro_users,
        "free_users": total_users - pro_users,
        "total_ielts_tests": total_tests,
    }


@router.get("/ai-usage")
async def get_ai_usage(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """AI token usage + estimated cost, for the admin AI-usage view."""
    from app.models.ai_usage import AIUsage

    totals = (await db.execute(select(
        func.coalesce(func.sum(AIUsage.cost_usd), 0),
        func.coalesce(func.sum(AIUsage.input_tokens), 0),
        func.coalesce(func.sum(AIUsage.output_tokens), 0),
        func.count(AIUsage.id),
    ))).one()

    by_model = (await db.execute(
        select(AIUsage.model, func.sum(AIUsage.cost_usd), func.count(AIUsage.id))
        .group_by(AIUsage.model).order_by(func.sum(AIUsage.cost_usd).desc())
    )).all()

    by_module = (await db.execute(
        select(AIUsage.module, func.sum(AIUsage.cost_usd), func.count(AIUsage.id))
        .group_by(AIUsage.module).order_by(func.sum(AIUsage.cost_usd).desc())
    )).all()

    day = func.date_trunc("day", AIUsage.created_at)
    by_day = (await db.execute(
        select(day, func.sum(AIUsage.cost_usd), func.count(AIUsage.id))
        .group_by(day).order_by(day.desc()).limit(30)
    )).all()

    top_users = (await db.execute(
        select(User.email, func.sum(AIUsage.cost_usd), func.count(AIUsage.id))
        .join(User, User.id == AIUsage.user_id)
        .group_by(User.email).order_by(func.sum(AIUsage.cost_usd).desc()).limit(10)
    )).all()

    return {
        "total_cost_usd": round(float(totals[0]), 4),
        "total_input_tokens": int(totals[1]),
        "total_output_tokens": int(totals[2]),
        "total_calls": int(totals[3]),
        "by_model": [{"model": m, "cost_usd": round(float(c), 4), "calls": int(n)} for m, c, n in by_model],
        "by_module": [{"module": m, "cost_usd": round(float(c), 4), "calls": int(n)} for m, c, n in by_module],
        "by_day": [{"day": d.date().isoformat() if d else None, "cost_usd": round(float(c), 4), "calls": int(n)} for d, c, n in by_day],
        "top_users": [{"email": e, "cost_usd": round(float(c), 4), "calls": int(n)} for e, c, n in top_users],
    }


@router.get("/test-analytics")
async def get_test_analytics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Test activity: volume by module, most popular tests, most active users."""
    import uuid as _uuid
    from collections import defaultdict
    from app.models.test import TestAttempt, ModuleType
    from app.models.speaking_attempt import SpeakingAttempt
    from app.models.ielts_test import SessionStatus

    total_attempts = (await db.execute(select(func.count(TestAttempt.id)))).scalar() or 0
    speaking_sessions = (await db.execute(select(func.count(SpeakingAttempt.id)))).scalar() or 0
    completed_mocks = (await db.execute(
        select(func.count(TestSession.id)).where(TestSession.status == SessionStatus.completed)
    )).scalar() or 0

    by_module = (await db.execute(
        select(TestAttempt.module, func.count(TestAttempt.id), func.avg(TestAttempt.overall_band))
        .group_by(TestAttempt.module).order_by(func.count(TestAttempt.id).desc())
    )).all()

    day = func.date_trunc("day", TestAttempt.created_at)
    by_day = (await db.execute(
        select(day, func.count(TestAttempt.id)).group_by(day).order_by(day.desc()).limit(30)
    )).all()

    popular = (await db.execute(
        select(TestAttempt.module, TestAttempt.test_id, func.count(TestAttempt.id))
        .where(TestAttempt.test_id.isnot(None))
        .group_by(TestAttempt.module, TestAttempt.test_id)
        .order_by(func.count(TestAttempt.id).desc()).limit(15)
    )).all()

    # Resolve each popular test_id to its title (test_id is stored as a string).
    model_by_module = {
        ModuleType.listening: ListeningTest,
        ModuleType.reading: ReadingTest,
        ModuleType.writing: WritingTest,
        ModuleType.speaking: SpeakingTest,
    }
    ids_by_module = defaultdict(list)
    for mod, tid, _cnt in popular:
        ids_by_module[mod].append(tid)
    title_map = {}
    for mod, ids in ids_by_module.items():
        model = model_by_module.get(mod)
        if model is None:
            continue
        valid = []
        for t in ids:
            try:
                valid.append(_uuid.UUID(str(t)))
            except (ValueError, TypeError):
                pass
        if not valid:
            continue
        rows = (await db.execute(select(model.id, model.title).where(model.id.in_(valid)))).all()
        for tid, title in rows:
            title_map[(mod, str(tid))] = title

    active_users = (await db.execute(
        select(User.email, func.count(TestAttempt.id))
        .join(User, User.id == TestAttempt.user_id)
        .group_by(User.email).order_by(func.count(TestAttempt.id).desc()).limit(15)
    )).all()

    recent = (await db.execute(
        select(TestAttempt.module, TestAttempt.overall_band, TestAttempt.created_at,
               TestAttempt.subscores, User.email)
        .join(User, User.id == TestAttempt.user_id)
        .order_by(TestAttempt.created_at.desc()).limit(15)
    )).all()

    def _mod(m):
        return m.value if hasattr(m, "value") else str(m)

    return {
        "total_attempts": int(total_attempts),
        "speaking_sessions": int(speaking_sessions),
        "completed_full_mocks": int(completed_mocks),
        "by_module": [
            {"module": _mod(m), "count": int(c), "avg_band": round(float(b), 1) if b is not None else None}
            for m, c, b in by_module
        ],
        "by_day": [{"day": d.date().isoformat() if d else None, "count": int(c)} for d, c in by_day],
        "popular_tests": [
            {"module": _mod(m), "title": title_map.get((m, str(t))) or "—", "count": int(c)}
            for m, t, c in popular
        ],
        "active_users": [{"email": e, "attempts": int(c)} for e, c in active_users],
        "recent_tests": [
            {
                "module": _mod(m),
                "title": (sub or {}).get("test_title") or "—",
                "band": float(b) if b is not None else None,
                "email": e,
                "at": ca.isoformat() if ca else None,
            }
            for m, b, ca, sub, e in recent
        ],
    }


@router.get("/user-analytics")
async def get_user_analytics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """User growth + behaviour: signups over time, activation, engagement
    segments, active users, Pro conversion, and recent signups with their
    activity. 'Attempts' = listening/reading/writing/diagnostic (TestAttempt);
    speaking is stored separately and not counted here."""
    from datetime import datetime, timezone, timedelta
    from app.models.test import TestAttempt

    now = datetime.now(timezone.utc)
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    pro_users = (await db.execute(
        select(func.count(User.id)).where(User.subscription == SubscriptionTier.pro)
    )).scalar() or 0
    new_7d = (await db.execute(select(func.count(User.id)).where(User.created_at >= d7))).scalar() or 0
    new_30d = (await db.execute(select(func.count(User.id)).where(User.created_at >= d30))).scalar() or 0

    # New signups per day (last 30 days), chronological
    day = func.date_trunc("day", User.created_at)
    signups = (await db.execute(
        select(day, func.count(User.id)).where(User.created_at >= d30)
        .group_by(day).order_by(day)
    )).all()

    # Per-user attempt aggregate (count + last active)
    per_user = (
        select(
            TestAttempt.user_id.label("uid"),
            func.count(TestAttempt.id).label("n"),
            func.max(TestAttempt.created_at).label("last"),
        )
        .group_by(TestAttempt.user_id)
    ).subquery()

    # Engagement segments + activation (users with >= 1 attempt)
    seg = (await db.execute(
        select(
            func.count().filter(per_user.c.n.between(1, 2)),
            func.count().filter(per_user.c.n.between(3, 5)),
            func.count().filter(per_user.c.n >= 6),
            func.count(per_user.c.uid),
        ).select_from(per_user)
    )).one()
    low, medium, high, activated = int(seg[0]), int(seg[1]), int(seg[2]), int(seg[3])

    active_7d = (await db.execute(
        select(func.count(func.distinct(TestAttempt.user_id))).where(TestAttempt.created_at >= d7)
    )).scalar() or 0
    active_30d = (await db.execute(
        select(func.count(func.distinct(TestAttempt.user_id))).where(TestAttempt.created_at >= d30)
    )).scalar() or 0

    # Recent signups with their activity
    recent = (await db.execute(
        select(
            User.email, User.full_name, User.subscription, User.created_at,
            func.coalesce(per_user.c.n, 0), per_user.c.last,
        )
        .outerjoin(per_user, per_user.c.uid == User.id)
        .order_by(User.created_at.desc()).limit(15)
    )).all()

    # Signup-cohort conversion: of users who joined each month, how many are Pro now.
    # (We don't store a conversion timestamp, so this cohort view is the honest way
    # to see whether newer signups convert better than older ones.)
    month = func.date_trunc("month", User.created_at)
    cohorts = (await db.execute(
        select(
            month,
            func.count(User.id),
            func.count(User.id).filter(User.subscription == SubscriptionTier.pro),
        ).group_by(month).order_by(month)
    )).all()
    engaged = medium + high  # 3+ tests

    # Per-module engagement: reach (distinct users) + attempts per module
    mod_reach = (await db.execute(
        select(TestAttempt.module, func.count(func.distinct(TestAttempt.user_id)), func.count(TestAttempt.id))
        .group_by(TestAttempt.module)
        .order_by(func.count(func.distinct(TestAttempt.user_id)).desc())
    )).all()

    # Which module each user tried FIRST — the entry point (DISTINCT ON earliest)
    firsts = (
        select(TestAttempt.user_id, TestAttempt.module)
        .order_by(TestAttempt.user_id, TestAttempt.created_at.asc())
        .distinct(TestAttempt.user_id)
    ).subquery()
    first_mod = (await db.execute(
        select(firsts.c.module, func.count()).group_by(firsts.c.module).order_by(func.count().desc())
    )).all()

    # Retention: of activated users, how many came back (active on 2+ distinct days)
    days_active = (
        select(
            TestAttempt.user_id.label("uid"),
            func.count(func.distinct(func.date_trunc("day", TestAttempt.created_at))).label("d"),
        ).group_by(TestAttempt.user_id)
    ).subquery()
    ret = (await db.execute(
        select(
            func.count().filter(days_active.c.d == 1),
            func.count().filter(days_active.c.d >= 2),
        ).select_from(days_active)
    )).one()
    one_and_done, returned = int(ret[0]), int(ret[1])

    def _mod(m):
        return m.value if hasattr(m, "value") else m

    return {
        "total_users": total_users,
        "pro_users": pro_users,
        "free_users": total_users - pro_users,
        "new_7d": new_7d,
        "new_30d": new_30d,
        "pro_conversion_pct": round(100 * pro_users / total_users, 1) if total_users else 0.0,
        "active_7d": active_7d,
        "active_30d": active_30d,
        "activation_pct": round(100 * activated / total_users, 1) if total_users else 0.0,
        "signups_by_day": [{"day": d.date().isoformat() if d else None, "count": int(n)} for d, n in signups],
        "engagement": {
            "none": total_users - activated,   # signed up, 0 attempts
            "low": low,                        # 1-2 attempts
            "medium": medium,                  # 3-5 attempts
            "high": high,                      # 6+ attempts
        },
        "recent_signups": [
            {
                "email": em,
                "full_name": fn,
                "subscription": sub,
                "created_at": ca.isoformat() if ca else None,
                "attempts": int(n or 0),
                "last_active": la.isoformat() if la else None,
            }
            for em, fn, sub, ca, n, la in recent
        ],
        "funnel": [
            {"stage": "Signed up", "count": total_users},
            {"stage": "Activated · took a test", "count": activated},
            {"stage": "Engaged · 3+ tests", "count": engaged},
            {"stage": "Converted to Pro", "count": pro_users},
        ],
        "cohorts": [
            {
                "month": m.date().isoformat() if m else None,
                "signups": int(tot),
                "pro": int(p),
                "conversion_pct": round(100 * int(p) / int(tot), 1) if tot else 0.0,
            }
            for m, tot, p in cohorts
        ],
        "module_reach": [
            {"module": _mod(m), "users": int(u), "attempts": int(a)}
            for m, u, a in mod_reach
        ],
        "first_module": [
            {"module": _mod(m), "count": int(n)}
            for m, n in first_mod
        ],
        "retention": {
            "returned": returned,
            "one_and_done": one_and_done,
            "return_rate_pct": round(100 * returned / activated, 1) if activated else 0.0,
        },
    }
