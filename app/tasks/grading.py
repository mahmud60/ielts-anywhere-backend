from celery import Celery
from app.core.config import settings
import ssl

celery_app = Celery(
    "ielts_grader",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Windows requires solo pool — critical for Windows development
celery_app.conf.update(
    worker_pool="solo",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,          # only ack after task completes
    task_reject_on_worker_lost=True,  # requeue if worker crashes
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},        # ✅ add this
    redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE}, # ✅ add this
)


def _get_db_session():
    """
    Celery workers are synchronous. We use psycopg2 here instead of
    the asyncpg driver used in FastAPI routes.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg", "postgresql+psycopg2"
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
    from app.services.writing_grader import grade_writing, _count_words

    db = _get_db_session()
    try:
        # Step 1: Mark as grading so frontend knows work is in progress
        attempt = db.get(TestAttempt, attempt_id)
        if not attempt:
            return
        attempt.status = GradingStatus.grading
        db.commit()

        # Step 2: Call Claude Haiku
        result = grade_writing(
            task1_prompt=task_data["task1_prompt"],
            task1_response=task_data["task1_response"],
            task2_prompt=task_data["task2_prompt"],
            task2_response=task_data["task2_response"],
            task1_type=task_data.get("task1_type", "task1_academic"),
        )

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
            },
            "task2": {
                "task_achievement": t2["task_achievement"],
                "coherence_cohesion": t2["coherence_cohesion"],
                "lexical_resource": t2["lexical_resource"],
                "grammatical_range": t2["grammatical_range"],
                "band": t2["band"],
                "feedback": t2["feedback"],
                "word_count": _count_words(task_data["task2_response"]),
            },
        }

        # Step 4: Save and mark complete
        attempt = db.get(TestAttempt, attempt_id)
        attempt.status = GradingStatus.complete
        attempt.overall_band = result["overall_band"]
        attempt.subscores = subscores
        attempt.ai_feedback = f"Task 1: {t1['feedback']} Task 2: {t2['feedback']}"
        attempt.improvement_tips = result["improvement_tips"]
        db.commit()

    except Exception as exc:
        # Mark as failed then retry
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

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def grade_speaking_task(self, attempt_id: str, part_responses: list):
    """
    Grades a speaking attempt with Claude Haiku.

    part_responses: list of dicts with part_number and exchanges.
    Same async pattern as writing — submit returns pending,
    this task updates the attempt when done.
    """
    from app.models.test import TestAttempt, GradingStatus
    from app.services.speaking_grader import grade_speaking

    db = _get_db_session()
    try:
        attempt = db.get(TestAttempt, attempt_id)
        if not attempt:
            return
        attempt.status = GradingStatus.grading
        db.commit()

        result = grade_speaking(part_responses)

        # Build subscores structure
        subscores = {}
        for part_key, part_num, part_type in [
            ("part1", 1, "part1"),
            ("part2", 2, "part2"),
            ("part3", 3, "part3"),
        ]:
            p = result[part_key]
            subscores[part_key] = {
                "part_number": part_num,
                "part_type": part_type,
                "fluency_coherence": p["fluency_coherence"],
                "lexical_resource": p["lexical_resource"],
                "grammatical_range": p["grammatical_range"],
                "pronunciation": p["pronunciation"],
                "band": p["band"],
                "feedback": p["feedback"],
                "examiner_notes": p.get("examiner_notes"),
            }

        attempt = db.get(TestAttempt, attempt_id)
        attempt.status = GradingStatus.complete
        attempt.overall_band = result["overall_band"]
        attempt.subscores = subscores
        attempt.ai_feedback = " | ".join([
            f"Part {i+1}: {result[k]['feedback']}"
            for i, k in enumerate(["part1", "part2", "part3"])
        ])
        attempt.improvement_tips = result["improvement_tips"]
        db.commit()

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