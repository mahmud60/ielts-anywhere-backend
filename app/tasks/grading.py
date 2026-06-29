import logging
import platform
from celery import Celery
from app.core.config import settings
from app.core.sentry import init_sentry
import ssl

celery_app = Celery(
    "ielts_grader",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

_use_ssl = settings.REDIS_URL.startswith("rediss://")
# Validate the broker's TLS certificate against the public CA bundle (Upstash
# uses a valid cert) — CERT_REQUIRED, not CERT_NONE, so the connection isn't
# exposed to a man-in-the-middle.
_ssl_opts = {"ssl_cert_reqs": ssl.CERT_REQUIRED} if _use_ssl else {}

celery_app.conf.update(
    worker_pool="solo" if platform.system() == "Windows" else "prefork",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_use_ssl=_ssl_opts,
    redis_backend_use_ssl=_ssl_opts,
    # Ride out a broker (Redis) outage instead of exiting: keep retrying the
    # connection forever, at startup and while running. Paired with the systemd
    # unit's Restart=always, a Redis blip can never silently kill the worker —
    # it reconnects on its own the moment the broker comes back.
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=None,
)

# Capture failed tasks (CeleryIntegration auto-enables). No-op without SENTRY_DSN.
init_sentry()

logger = logging.getLogger(__name__)


def _get_db_session():
    """
    Celery workers are synchronous. We use psycopg2 here instead of
    the asyncpg driver used in FastAPI routes.
    asyncpg uses ?ssl=require; psycopg2 uses sslmode=require.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_url = (
        settings.DATABASE_URL
        .replace("postgresql+asyncpg", "postgresql+psycopg2")
        .replace("?ssl=require", "?sslmode=require")
        .replace("&ssl=require", "&sslmode=require")
    )
    engine = create_engine(sync_url, pool_pre_ping=True)
    return sessionmaker(engine)()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def grade_writing_task(self, attempt_id: str, task_data: dict):
    """
    Grades a writing attempt with Claude Haiku.

    task_data structure:
    {
      "task1_prompt": str,
      "task1_response": str,
      "task1_type": str,
      "task2_prompt": str,
      "task2_response": str,
    }

    Flow:
    1. Mark attempt as "grading"
    2. Call Claude Haiku via grade_writing()
    3. Parse result and save band scores, feedback, tips
    4. Mark attempt as "complete"
    If anything fails, retry up to 3 times then mark as "failed"
    """
    from app.models.test import TestAttempt, GradingStatus
    from app.models.user import User
    from app.services.writing_grader import grade_writing, _count_words
    from app.services import analytics

    db = _get_db_session()
    try:
        # Step 1: Mark as grading so frontend knows work is in progress
        attempt = db.get(TestAttempt, attempt_id)
        if not attempt:
            return
        attempt.status = GradingStatus.grading
        attempt_user_id = attempt.user_id
        db.commit()

        # Step 2: Call Claude Haiku
        result = grade_writing(
            task1_prompt=task_data["task1_prompt"],
            task1_response=task_data["task1_response"],
            task2_prompt=task_data["task2_prompt"],
            task2_response=task_data["task2_response"],
            task1_type=task_data.get("task1_type", "task1_academic"),
        )

        # Log token usage for the admin AI-usage view (stripped from result so it
        # isn't persisted). add_usage stages a row on the task's session.
        from app.services.ai_usage import add_usage
        _in, _out = result.pop("_usage", (0, 0))
        add_usage(db, module="writing", model="claude-haiku-4-5-20251001",
                  input_tokens=_in, output_tokens=_out, user_id=attempt_user_id)

        # Step 3: Build subscores structure for storage
        t1 = result["task1"]
        t2 = result["task2"]
        subscores = {
            "task1": {
                "task_achievement": t1["task_achievement"],
                "coherence_cohesion": t1["coherence_cohesion"],
                "lexical_resource": t1["lexical_resource"],
                "grammatical_range": t1["grammatical_range"],
                "band": t1["band"],
                "feedback": t1["feedback"],
                "word_count": _count_words(task_data["task1_response"]),
                "task_prompt": task_data["task1_prompt"],
                "task_type": task_data.get("task1_type", "task1_academic"),
                "raw_text": task_data["task1_response"],
                "errors": t1.get("errors", {}),
            },
            "task2": {
                "task_achievement": t2["task_achievement"],
                "coherence_cohesion": t2["coherence_cohesion"],
                "lexical_resource": t2["lexical_resource"],
                "grammatical_range": t2["grammatical_range"],
                "band": t2["band"],
                "feedback": t2["feedback"],
                "word_count": _count_words(task_data["task2_response"]),
                "task_prompt": task_data["task2_prompt"],
                "task_type": "task2",
                "raw_text": task_data["task2_response"],
                "errors": t2.get("errors", {}),
            },
        }

        # Step 4: Save and mark complete
        attempt = db.get(TestAttempt, attempt_id)
        attempt.status = GradingStatus.complete
        attempt.overall_band = result["overall_band"]
        attempt.subscores = subscores
        attempt.ai_feedback = f"Task 1: {t1['feedback']} Task 2: {t2['feedback']}"
        attempt.improvement_tips = result["improvement_tips"]
        _record_feedback_state(db, str(attempt.user_id), "writing", result["overall_band"], attempt_id)
        db.commit()

        try:
            user = db.get(User, attempt.user_id)
            if user:
                analytics.capture(user.firebase_uid, "test_completed", {
                    "module": "writing",
                    "test_id": attempt.test_id,
                    "band": result["overall_band"],
                })
        except Exception:
            pass  # telemetry must never fail or retry an already-completed grading

        _notify_module_graded(attempt_id)

    except Exception as exc:
        try:
            attempt = db.get(TestAttempt, attempt_id)
            if attempt:
                attempt.status = GradingStatus.failed
                db.commit()
        except Exception:
            pass
        db.close()
        raise self.retry(exc=exc)
    finally:
        db.close()

def _record_feedback_state(db, user_id: str, module: str, band: float, attempt_id: str) -> None:
    """
    Persist the band and attempt ID into user.feedback_state so the gating
    logic can compare on the next submit.
    Called inside existing Celery tasks — no extra commit needed.
    """
    from app.models.user import User
    from sqlalchemy import func, select
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.test import TestAttempt

    user = db.get(User, user_id)
    if not user:
        return

    count = db.execute(
        select(func.count()).where(
            TestAttempt.user_id == user_id,
            TestAttempt.module == module,
        )
    ).scalar() or 0

    state = dict(user.feedback_state or {})
    state[module] = {
        "last_band": band,
        "last_attempt_id": attempt_id,
        "last_attempt_number": count,
    }
    user.feedback_state = state
    flag_modified(user, "feedback_state")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def generate_feedback_task(self, attempt_id: str, module: str, feedback_data: dict):
    """
    Generates LLM-powered improvement tips for a listening or reading attempt.
    Only queued when the feedback gate passes (first attempt, band delta >= 0.5,
    or 5+ attempts since last LLM feedback).

    On success: overwrites attempt.improvement_tips with Haiku-generated tips
    and records the new feedback_state on the user.
    On failure: silently retries twice — the rule-based tips already on the
    attempt remain visible to the user.
    """
    from app.models.test import TestAttempt
    from app.models.user import User
    from app.services.feedback_generator import generate_feedback
    from sqlalchemy import func, select
    from sqlalchemy.orm.attributes import flag_modified

    db = _get_db_session()
    try:
        attempt = db.get(TestAttempt, attempt_id)
        if not attempt:
            return

        tips = generate_feedback(module, feedback_data)
        if not tips:
            return  # keep existing rule-based tips

        attempt.improvement_tips = tips

        count = db.execute(
            select(func.count()).where(
                TestAttempt.user_id == attempt.user_id,
                TestAttempt.module == module,
            )
        ).scalar() or 0

        user = db.get(User, attempt.user_id)
        if user:
            state = dict(user.feedback_state or {})
            state[module] = {
                "last_band": feedback_data.get("band"),
                "last_attempt_id": attempt_id,
                "last_attempt_number": count,
            }
            user.feedback_state = state
            flag_modified(user, "feedback_state")

        db.commit()

    except Exception as exc:
        db.close()
        raise self.retry(exc=exc)
    finally:
        db.close()


def _notify_module_graded(attempt_id: str) -> None:
    """
    After an async module finishes grading, check if its parent session
    is now fully complete and send a results email if so.
    Uses a fresh DB session so it cannot affect the caller's session state.
    """
    db = _get_db_session()
    try:
        from app.models.user import User
        from app.models.test import TestAttempt
        from app.models.ielts_test import TestSession, SessionStatus
        from app.services.email import send_email_sync, build_test_complete_email
        from sqlalchemy import text

        session = db.execute(
            text(
                "SELECT * FROM test_sessions WHERE "
                "(listening_attempt_id = :aid OR reading_attempt_id = :aid OR "
                " writing_attempt_id = :aid OR speaking_attempt_id = :aid) LIMIT 1"
            ),
            {"aid": attempt_id},
        ).mappings().first()

        if not session or session["status"] != "completed":
            return

        user = db.get(User, session["user_id"])
        if not user or not user.email:
            return

        bands = session["module_bands"] or {}
        done = [v for v in bands.values() if v is not None]
        overall = round(sum(done) / len(done) * 2) / 2 if done else None

        subject, html = build_test_complete_email(
            user_name=user.full_name or "",
            overall_band=overall,
            module_bands=bands,
            session_id=str(session["id"]),
        )
        send_email_sync(user.email, subject, html)
    except Exception:
        pass
    finally:
        db.close()

def _translate_listening_tips(db, questions, overwrite: bool = False) -> int:
    """Fill wrong_answer_tip_bn for listening questions that already have an
    English wrong_answer_tip. Best-effort and chunk-committed, so a partial
    failure keeps prior progress and never disturbs the English tips."""
    from app.services.question_tips_generator import translate_tips_to_bengali

    pending = [
        q for q in questions
        if q.wrong_answer_tip and (overwrite or not q.wrong_answer_tip_bn)
    ]
    if not pending:
        return 0

    translated = 0
    CHUNK = 40
    for i in range(0, len(pending), CHUNK):
        group = pending[i:i + CHUNK]
        bn = translate_tips_to_bengali([q.wrong_answer_tip for q in group])
        for q, t in zip(group, bn):
            if t:
                q.wrong_answer_tip_bn = t
                translated += 1
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Commit failed during Bengali tip backfill", exc_info=True)
    return translated


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def generate_question_tips_task(self, test_id: str, module: str, overwrite: bool = False):
    """
    Pre-generate wrong_answer_tip for every question in a listening or reading test.
    Called once by admin after uploading a test.  Each question costs ~120 Haiku tokens.
    Questions that already have a tip are skipped unless overwrite=True.
    """
    from app.services.question_tips_generator import (
        generate_listening_question_tip,
        generate_reading_question_tip,
    )

    db = _get_db_session()
    try:
        if module == "listening":
            from app.models.listening import ListeningTest, ListeningSection, ListeningSubsection, ListeningQuestion
            from sqlalchemy.orm import joinedload

            test = db.get(ListeningTest, test_id)
            if not test:
                return

            # Load full tree
            from sqlalchemy import select
            sections = db.execute(
                select(ListeningSection).where(ListeningSection.test_id == test_id)
            ).scalars().all()
            section_ids = [s.id for s in sections]

            subsections = db.execute(
                select(ListeningSubsection).where(ListeningSubsection.section_id.in_(section_ids))
            ).scalars().all()
            sub_ids = [s.id for s in subsections]

            questions = db.execute(
                select(ListeningQuestion).where(ListeningQuestion.subsection_id.in_(sub_ids))
            ).scalars().all()

            updated = 0
            for q in questions:
                if q.wrong_answer_tip and not overwrite:
                    continue
                tip = generate_listening_question_tip(
                    q.question_type, q.stem or "", q.answer_key
                )
                if tip:
                    q.wrong_answer_tip = tip
                    updated += 1

            db.commit()

            # Pre-translate the (new or pre-existing) English tips to Bengali so
            # the listening report's EN/BN toggle is served straight from the DB.
            _translate_listening_tips(db, questions, overwrite)

        elif module == "reading":
            from app.models.reading import ReadingTest, ReadingPassage, ReadingQuestionGroup, ReadingQuestion
            from sqlalchemy import select

            passages = db.execute(
                select(ReadingPassage).where(ReadingPassage.test_id == test_id)
            ).scalars().all()
            passage_ids = [p.id for p in passages]

            groups = db.execute(
                select(ReadingQuestionGroup).where(ReadingQuestionGroup.passage_id.in_(passage_ids))
            ).scalars().all()
            group_map = {str(g.id): g for g in groups}
            group_ids = [g.id for g in groups]

            questions = db.execute(
                select(ReadingQuestion).where(ReadingQuestion.group_id.in_(group_ids))
            ).scalars().all()

            updated = 0
            for q in questions:
                if q.wrong_answer_tip and not overwrite:
                    continue
                group = group_map.get(str(q.group_id))
                tip = generate_reading_question_tip(
                    question_type=group.question_type.value if group else "mcq",
                    question_text=q.question_text or "",
                    answer_key=q.answer_key,
                    instruction=(group.instruction or "") if group else "",
                )
                if tip:
                    q.wrong_answer_tip = tip
                    updated += 1

            db.commit()

    except Exception as exc:
        db.close()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def translate_listening_tips_task(self, overwrite: bool = False):
    """Backfill wrong_answer_tip_bn across ALL listening questions that already
    have an English tip — a one-time translation of the pre-generated tips so the
    report's EN/BN toggle has Bengali to show without any read-time LLM call."""
    from app.models.listening import ListeningQuestion
    from sqlalchemy import select

    db = _get_db_session()
    try:
        questions = db.execute(select(ListeningQuestion)).scalars().all()
        translated = _translate_listening_tips(db, questions, overwrite)
        return {"translated": translated, "total": len(questions)}
    finally:
        db.close()
