from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Any
import uuid
from app.models.ielts_test import IeltsTest, TestSession

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.listening import (
    ListeningTest, ListeningSection, ListeningSubsection, ListeningQuestion,
)
from app.models.reading import (
    ReadingTest, ReadingPassage,
    ReadingQuestionGroup, ReadingQuestion,
    ReadingQuestionType,
)
from app.models.writing import WritingTest, WritingTask, WritingTaskType
from app.models.speaking import SpeakingTest, SpeakingPart, SpeakingPartType
from app.models.ielts_test import IeltsTest
from app.services.storage import upload_audio, delete_audio
from app.api.routes.auth import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Admin guard ───────────────────────────────────────────────────────────────

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that blocks non-admin users from all admin routes.
    Add this to every admin endpoint.
    """
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    return current_user


# ── Dashboard stats ───────────────────────────────────────────────────────────

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


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 50,
    search: str = "",
):
    """Returns paginated user list with optional email search."""
    query = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "subscription": u.subscription,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/subscription")
async def update_subscription(
    user_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Manually override a user's subscription tier.
    Useful for giving free access to testers or resolving payment issues.
    """
    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    tier = body.get("subscription")
    if tier not in ("free", "pro"):
        raise HTTPException(400, "Subscription must be 'free' or 'pro'")

    user.subscription = SubscriptionTier(tier)
    await db.flush()
    return {"id": str(user.id), "subscription": user.subscription}


@router.patch("/users/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Grant or revoke admin status. Admins cannot remove their own status."""
    if str(admin.id) == user_id:
        raise HTTPException(400, "Cannot modify your own admin status")

    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    user.is_admin = bool(body.get("is_admin", False))
    await db.flush()
    return {"id": str(user.id), "is_admin": user.is_admin}


# ── Listening test management ─────────────────────────────────────────────────

@router.get("/listening/tests")
async def list_listening_tests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(ListeningTest)
        .options(
            selectinload(ListeningTest.sections)
            .selectinload(ListeningSection.subsections)
            .selectinload(ListeningSubsection.questions)
        )
        .order_by(ListeningTest.created_at.desc())
    )
    tests = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "is_active": t.is_active,
            "sections": [
                {
                    "id": s.id,
                    "part": s.part,
                    "title": s.title,
                    "audio": s.audio,
                    "question_count": sum(len(sub.questions) for sub in s.subsections),
                }
                for s in t.sections
            ],
        }
        for t in tests
    ]


@router.post("/listening/tests")
async def create_listening_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = ListeningTest(
        title=body["title"],
        description=body.get("description"),
        task=body.get("task", "ielts_listening"),
        type=body.get("type", "text"),
        order=body.get("order", 1),
        is_active=body.get("is_active", False),
        is_recommended=body.get("is_recommended", False),
        mock_test_order=body.get("mock_test_order"),
    )
    db.add(test)
    await db.flush()
    return {"id": str(test.id), "title": test.title}


@router.delete("/listening/tests/{test_id}", status_code=204)
async def delete_listening_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = (await db.execute(
        select(ListeningTest).where(ListeningTest.id == test_id)
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")
    await db.delete(test)
    await db.flush()


@router.patch("/listening/tests/{test_id}")
async def update_listening_test(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = (await db.execute(
        select(ListeningTest).where(ListeningTest.id == test_id)
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    for field in ["title", "description", "task", "type", "order",
                  "is_active", "is_recommended", "mock_test_order"]:
        if field in body:
            setattr(test, field, body[field])

    await db.flush()
    return {"id": str(test.id), "title": test.title, "is_active": test.is_active}


# ── Section management ───────────────────────────────────────────────────────

@router.post("/listening/tests/{test_id}/sections")
async def create_listening_section(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = (await db.execute(
        select(ListeningTest).where(ListeningTest.id == test_id)
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    section = ListeningSection(
        test_id=test_id,
        part=body.get("part", 1),
        title=body.get("title", ""),
        audio=body.get("audio"),
    )
    db.add(section)
    await db.flush()
    return {"id": section.id, "part": section.part, "title": section.title, "audio": section.audio}


@router.patch("/listening/sections/{section_id}")
async def update_listening_section(
    section_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    section = (await db.execute(
        select(ListeningSection).where(ListeningSection.id == section_id)
    )).scalar_one_or_none()
    if not section:
        raise HTTPException(404, "Section not found")

    for field in ["part", "title", "audio"]:
        if field in body:
            setattr(section, field, body[field])

    await db.flush()
    return {"id": section.id, "part": section.part, "title": section.title}


# ── Audio upload ──────────────────────────────────────────────────────────────

@router.post("/listening/sections/{section_id}/audio")
async def upload_section_audio(
    section_id: int,
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    allowed = {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", "audio/x-m4a"}
    if audio.content_type not in allowed:
        raise HTTPException(400, f"Unsupported audio type: {audio.content_type}")

    section = (await db.execute(
        select(ListeningSection).where(ListeningSection.id == section_id)
    )).scalar_one_or_none()
    if not section:
        raise HTTPException(404, "Section not found")

    if section.audio:
        delete_audio(section.audio)

    file_bytes = await audio.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(400, "Audio file too large (max 50MB)")

    url = upload_audio(file_bytes, audio.filename)
    section.audio = url
    await db.flush()

    return {"section_id": section_id, "audio_url": url}


# ── Subsection management ─────────────────────────────────────────────────────

@router.get("/listening/sections/{section_id}/subsections")
async def list_subsections(
    section_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(ListeningSubsection)
        .where(ListeningSubsection.section_id == section_id)
        .order_by(ListeningSubsection.order)
    )
    return [
        {
            "id": sub.id,
            "order": sub.order,
            "title": sub.title,
            "subsection_type": sub.subsection_type,
            "instruction": sub.instruction,
            "visual": sub.visual,
            "grid_headers": sub.grid_headers,
            "grid_cells": sub.grid_cells,
        }
        for sub in result.scalars().all()
    ]


@router.post("/listening/sections/{section_id}/subsections")
async def create_subsection(
    section_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    section = (await db.execute(
        select(ListeningSection).where(ListeningSection.id == section_id)
    )).scalar_one_or_none()
    if not section:
        raise HTTPException(404, "Section not found")

    max_order = (await db.execute(
        select(func.max(ListeningSubsection.order))
        .where(ListeningSubsection.section_id == section_id)
    )).scalar() or 0

    sub = ListeningSubsection(
        section_id=section_id,
        order=body.get("order", max_order + 1),
        title=body.get("title"),
        subsection_type=body.get("subsection_type", "regular"),
        instruction=body.get("instruction"),
        visual=body.get("visual"),
        grid_headers=body.get("grid_headers"),
        grid_cells=body.get("grid_cells"),
    )
    db.add(sub)
    await db.flush()
    return {"id": sub.id, "order": sub.order, "subsection_type": sub.subsection_type}


@router.patch("/listening/subsections/{subsection_id}")
async def update_subsection(
    subsection_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    sub = (await db.execute(
        select(ListeningSubsection).where(ListeningSubsection.id == subsection_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subsection not found")

    for field in ["order", "title", "subsection_type", "instruction", "visual", "grid_headers", "grid_cells"]:
        if field in body:
            setattr(sub, field, body[field])

    await db.flush()
    return {"id": sub.id}


@router.delete("/listening/subsections/{subsection_id}", status_code=204)
async def delete_subsection(
    subsection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    sub = (await db.execute(
        select(ListeningSubsection).where(ListeningSubsection.id == subsection_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subsection not found")
    await db.delete(sub)
    await db.flush()


# ── Question management ───────────────────────────────────────────────────────

@router.get("/listening/subsections/{subsection_id}/questions")
async def list_questions(
    subsection_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(ListeningQuestion)
        .where(ListeningQuestion.subsection_id == subsection_id)
        .order_by(ListeningQuestion.order)
    )
    return [
        {
            "id": q.id,
            "order": q.order,
            "title": q.title,
            "question_type": q.question_type,
            "ielts_question_type": q.ielts_question_type,
            "stem": q.stem,
            "max_selected_options": q.max_selected_options,
            "options": q.options,
            "answer_key": q.answer_key,
            "wrong_answer_tip": q.wrong_answer_tip,
        }
        for q in result.scalars().all()
    ]


@router.post("/listening/subsections/{subsection_id}/questions")
async def create_question(
    subsection_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    sub = (await db.execute(
        select(ListeningSubsection).where(ListeningSubsection.id == subsection_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "Subsection not found")

    max_order = (await db.execute(
        select(func.max(ListeningQuestion.order))
        .where(ListeningQuestion.subsection_id == subsection_id)
    )).scalar() or 0

    question = ListeningQuestion(
        subsection_id=subsection_id,
        order=body.get("order", max_order + 1),
        title=body.get("title"),
        question_type=body["question_type"],
        ielts_question_type=body.get("ielts_question_type"),
        stem=body["stem"],
        max_selected_options=body.get("max_selected_options"),
        options=body.get("options", []),
        answer_key=body.get("answer_key"),
        wrong_answer_tip=body.get("wrong_answer_tip"),
    )
    db.add(question)
    await db.flush()
    return {"id": question.id, "order": question.order}


@router.patch("/listening/questions/{question_id}")
async def update_question(
    question_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = (await db.execute(
        select(ListeningQuestion).where(ListeningQuestion.id == question_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    for field in ["order", "title", "question_type", "ielts_question_type",
                  "stem", "max_selected_options", "options", "answer_key", "wrong_answer_tip"]:
        if field in body:
            setattr(question, field, body[field])

    await db.flush()
    return {"id": question.id}


@router.delete("/listening/questions/{question_id}")
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = (await db.execute(
        select(ListeningQuestion).where(ListeningQuestion.id == question_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    await db.delete(question)
    await db.flush()
    return {"deleted": question_id}

# ── Reading management ────────────────────────────────────────────────────────

from app.models.reading import (
    ReadingTest, ReadingPassage,
    ReadingQuestionGroup, ReadingQuestion,
    ReadingQuestionType,
)

@router.get("/reading/tests")
async def list_reading_tests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(ReadingTest)
        .options(
            selectinload(ReadingTest.passages)
            .selectinload(ReadingPassage.question_groups)
            .selectinload(ReadingQuestionGroup.questions)
        )
        .order_by(ReadingTest.created_at.desc())
    )
    tests = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "test_type": t.test_type,
            "is_active": t.is_active,
            "passages": [
                {
                    "id": str(p.id),
                    "passage_number": p.passage_number,
                    "title": p.title,
                    "body": p.body,
                    "question_groups": [
                        {
                            "id": str(g.id),
                            "order_index": g.order_index,
                            "question_type": g.question_type,
                            "instruction": g.instruction,
                            "word_limit": g.word_limit,
                            "heading_options": g.heading_options,
                            "paragraph_labels": g.paragraph_labels,
                            "question_count": len(g.questions),
                        }
                        for g in p.question_groups
                    ],
                }
                for p in t.passages
            ],
        }
        for t in tests
    ]


@router.post("/reading/tests")
async def create_reading_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = ReadingTest(
        title=body["title"],
        test_type=body.get("test_type", "academic"),
        is_active=body.get("is_active", False),
        is_demo=body.get("is_demo", False),
    )
    db.add(test)
    await db.flush()
    return {"id": str(test.id), "title": test.title}


@router.post("/reading/tests/{test_id}/passages")
async def create_reading_passage(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    passage = ReadingPassage(
        test_id=test_id,
        passage_number=body["passage_number"],
        title=body["title"],
        body=body.get("body", ""),
        paragraphs=body.get("paragraphs"),
    )
    db.add(passage)
    await db.flush()
    return {"id": str(passage.id), "title": passage.title}


@router.patch("/reading/passages/{passage_id}")
async def update_reading_passage(
    passage_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    passage = (await db.execute(
        select(ReadingPassage).where(ReadingPassage.id == passage_id)
    )).scalar_one_or_none()
    if not passage:
        raise HTTPException(404, "Passage not found")

    for field in ["title", "body", "paragraphs", "passage_number"]:
        if field in body:
            setattr(passage, field, body[field])
    await db.flush()
    return {"id": str(passage.id)}


@router.post("/reading/passages/{passage_id}/groups")
async def create_question_group(
    passage_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    max_order = (await db.execute(
        select(func.max(ReadingQuestionGroup.order_index))
        .where(ReadingQuestionGroup.passage_id == passage_id)
    )).scalar() or 0

    group = ReadingQuestionGroup(
        passage_id=passage_id,
        order_index=body.get("order_index", max_order + 1),
        question_type=ReadingQuestionType(body["question_type"]),
        instruction=body["instruction"],
        heading_options=body.get("heading_options"),
        paragraph_labels=body.get("paragraph_labels"),
        word_limit=body.get("word_limit"),
    )
    db.add(group)
    await db.flush()
    return {"id": str(group.id), "order_index": group.order_index}


@router.patch("/reading/groups/{group_id}")
async def update_question_group(
    group_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    group = (await db.execute(
        select(ReadingQuestionGroup).where(ReadingQuestionGroup.id == group_id)
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")

    for field in ["instruction", "heading_options", "paragraph_labels", "word_limit"]:
        if field in body:
            setattr(group, field, body[field])
    await db.flush()
    return {"id": str(group.id)}


@router.get("/reading/groups/{group_id}/questions")
async def list_reading_questions(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(ReadingQuestion)
        .where(ReadingQuestion.group_id == group_id)
        .order_by(ReadingQuestion.order_index)
    )
    questions = result.scalars().all()
    return [
        {
            "id": str(q.id),
            "order_index": q.order_index,
            "question_text": q.question_text,
            "options": q.options,
            "answer_key": q.answer_key,
            "wrong_answer_tip": q.wrong_answer_tip,
        }
        for q in questions
    ]


@router.post("/reading/groups/{group_id}/questions")
async def create_reading_question(
    group_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    max_order = (await db.execute(
        select(func.max(ReadingQuestion.order_index))
        .where(ReadingQuestion.group_id == group_id)
    )).scalar() or 0

    question = ReadingQuestion(
        group_id=group_id,
        order_index=body.get("order_index", max_order + 1),
        question_text=body["question_text"],
        options=body.get("options"),
        answer_key=body["answer_key"],
        wrong_answer_tip=body.get("wrong_answer_tip"),
    )
    db.add(question)
    await db.flush()
    return {"id": str(question.id)}


@router.patch("/reading/questions/{question_id}")
async def update_reading_question(
    question_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = (await db.execute(
        select(ReadingQuestion).where(ReadingQuestion.id == question_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    for field in ["question_text", "options", "answer_key", "wrong_answer_tip", "order_index"]:
        if field in body:
            setattr(question, field, body[field])
    await db.flush()
    return {"id": str(question.id)}


@router.delete("/reading/questions/{question_id}")
async def delete_reading_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = (await db.execute(
        select(ReadingQuestion).where(ReadingQuestion.id == question_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")
    await db.delete(question)
    await db.flush()
    return {"deleted": question_id}

#---Writing Management---------------------------------------------------------------------------

@router.get("/writing/tests")
async def list_writing_tests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(WritingTest)
        .options(selectinload(WritingTest.tasks))
        .order_by(WritingTest.created_at.desc())
    )
    tests = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "test_type": t.test_type,
            "is_active": t.is_active,
            "tasks": [
                {
                    "id": str(task.id),
                    "task_number": task.task_number,
                    "task_type": task.task_type,
                    "prompt": task.prompt,
                    "stimulus": task.stimulus,
                    "min_words": task.min_words,
                }
                for task in sorted(t.tasks, key=lambda x: x.task_number)
            ],
        }
        for t in tests
    ]


@router.post("/writing/tests")
async def create_writing_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = WritingTest(
        title=body["title"],
        test_type=body.get("test_type", "academic"),
        is_active=body.get("is_active", False),
        is_demo=body.get("is_demo", False),
    )
    db.add(test)
    await db.flush()
    return {"id": str(test.id), "title": test.title}


@router.post("/writing/tests/{test_id}/tasks")
async def create_writing_task(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    task = WritingTask(
        test_id=test_id,
        task_number=body["task_number"],
        task_type=WritingTaskType(body["task_type"]),
        prompt=body["prompt"],
        stimulus=body.get("stimulus"),
        min_words=body.get("min_words", 150 if body["task_number"] == 1 else 250),
    )
    db.add(task)
    await db.flush()
    return {"id": str(task.id)}


@router.patch("/writing/tasks/{task_id}")
async def update_writing_task(
    task_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    task = (await db.execute(
        select(WritingTask).where(WritingTask.id == task_id)
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")

    for field in ["prompt", "stimulus", "min_words", "task_type"]:
        if field in body:
            setattr(task, field, body[field])
    await db.flush()
    return {"id": str(task.id)}

#-----------Speaking Management--------------------------------------------------
@router.get("/speaking/tests")
async def list_speaking_tests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(SpeakingTest)
        .options(selectinload(SpeakingTest.parts))
        .order_by(SpeakingTest.created_at.desc())
    )
    tests = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "is_active": t.is_active,
            "parts": [
                {
                    "id": str(p.id),
                    "part_number": p.part_number,
                    "part_type": p.part_type,
                    "instructions": p.instructions,
                    "questions": p.questions,
                    "cue_card": p.cue_card,
                    "prep_time_seconds": p.prep_time_seconds,
                }
                for p in sorted(t.parts, key=lambda x: x.part_number)
            ],
        }
        for t in tests
    ]


@router.post("/speaking/tests")
async def create_speaking_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = SpeakingTest(
        title=body["title"],
        is_active=body.get("is_active", False),
        is_demo=body.get("is_demo", False),
    )
    db.add(test)
    await db.flush()
    return {"id": str(test.id), "title": test.title}


@router.post("/speaking/tests/{test_id}/parts")
async def create_speaking_part(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    part = SpeakingPart(
        test_id=test_id,
        part_number=body["part_number"],
        part_type=SpeakingPartType(body["part_type"]),
        instructions=body["instructions"],
        questions=body.get("questions", []),
        cue_card=body.get("cue_card"),
        prep_time_seconds=body.get("prep_time_seconds", 0),
        response_time_seconds=body.get("response_time_seconds"),
    )
    db.add(part)
    await db.flush()
    return {"id": str(part.id)}


@router.patch("/speaking/parts/{part_id}")
async def update_speaking_part(
    part_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    part = (await db.execute(
        select(SpeakingPart).where(SpeakingPart.id == part_id)
    )).scalar_one_or_none()
    if not part:
        raise HTTPException(404, "Part not found")

    for field in ["instructions", "questions", "cue_card", "prep_time_seconds"]:
        if field in body:
            setattr(part, field, body[field])
    await db.flush()
    return {"id": str(part.id)}

# ── IeltsTest management ──────────────────────────────────────────────────────

@router.get("/ielts-tests")
async def list_ielts_tests(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Returns all IeltsTests with their currently linked module tests.
    This is what the admin sees on the Tests tab.
    """
    result = await db.execute(
        select(IeltsTest)
        .options(
            selectinload(IeltsTest.listening_test),
            selectinload(IeltsTest.reading_test),
            selectinload(IeltsTest.writing_test),
            selectinload(IeltsTest.speaking_test),
        )
        .order_by(IeltsTest.created_at.desc())
    )
    tests = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "title": t.title,
            "test_type": t.test_type,
            "is_active": t.is_active,
            "is_demo": t.is_demo,
            "listening_test_id": str(t.listening_test_id) if t.listening_test_id else None,
            "reading_test_id": str(t.reading_test_id) if t.reading_test_id else None,
            "writing_test_id": str(t.writing_test_id) if t.writing_test_id else None,
            "speaking_test_id": str(t.speaking_test_id) if t.speaking_test_id else None,
            "listening_test_title": t.listening_test.title if t.listening_test else None,
            "reading_test_title": t.reading_test.title if t.reading_test else None,
            "writing_test_title": t.writing_test.title if t.writing_test else None,
            "speaking_test_title": t.speaking_test.title if t.speaking_test else None,
        }
        for t in tests
    ]


@router.post("/ielts-tests")
async def create_ielts_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Creates a new IeltsTest shell — link module tests separately."""
    test = IeltsTest(
        title=body["title"],
        test_type=body.get("test_type", "academic"),
        is_active=body.get("is_active", False),
        is_demo=body.get("is_demo", False),
    )
    db.add(test)
    await db.flush()
    return {"id": str(test.id), "title": test.title}


@router.patch("/ielts-tests/{test_id}")
async def update_ielts_test(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Updates an IeltsTest — including linking/unlinking module tests.
    Pass null for a module FK to unlink it.
    """
    test = (await db.execute(
        select(IeltsTest).where(IeltsTest.id == test_id)
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    # Metadata
    for field in ["title", "test_type", "is_active", "is_demo"]:
        if field in body:
            setattr(test, field, body[field])

    # Module FK linking — each can be set to a UUID string or null to unlink
    if "listening_test_id" in body:
        test.listening_test_id = body["listening_test_id"] or None
    if "reading_test_id" in body:
        test.reading_test_id = body["reading_test_id"] or None
    if "writing_test_id" in body:
        test.writing_test_id = body["writing_test_id"] or None
    if "speaking_test_id" in body:
        test.speaking_test_id = body["speaking_test_id"] or None

    await db.flush()
    return {"id": str(test.id), "title": test.title}


@router.delete("/ielts-tests/{test_id}")
async def delete_ielts_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Deletes an IeltsTest shell only — does NOT delete the linked module tests.
    Module tests are reusable and can be linked to other IeltsTests.
    """
    test = (await db.execute(
        select(IeltsTest).where(IeltsTest.id == test_id)
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    # Check no active sessions reference this test
    from app.models.ielts_test import TestSession, SessionStatus
    active = (await db.execute(
        select(TestSession).where(
            TestSession.ielts_test_id == test_id,
            TestSession.status == SessionStatus.in_progress,
        ).limit(1)
    )).scalar_one_or_none()
    if active:
        raise HTTPException(
            409,
            "Cannot delete — students have active sessions on this test. "
            "Deactivate it instead."
        )

    await db.delete(test)
    await db.flush()
    return {"deleted": test_id}

# ── Pricing / subscription config ─────────────────────────────────────────────

@router.get("/pricing")
async def get_pricing(
    _: User = Depends(require_admin),
):
    """
    Returns current pricing config from environment.
    In a real system this would be stored in DB for live editing.
    """
    return {
        "pro_variant_id": settings.LEMONSQUEEZY_PRO_VARIANT_ID,
        "currency": "USD",
        "plans": [
            {
                "name": "Free",
                "tier": "free",
                "price": 0,
                "features": [
                    "1 demo test",
                    "Listening + Reading only",
                    "No AI grading",
                ],
            },
            {
                "name": "Pro",
                "tier": "pro",
                "price": 19,
                "billing": "monthly",
                "features": [
                    "Unlimited full tests",
                    "All 4 modules",
                    "AI writing + speaking grading",
                    "Progress tracking",
                    "Improvement tips",
                ],
                "lemonsqueezy_variant_id": settings.LEMONSQUEEZY_PRO_VARIANT_ID,
            },
        ],
    }


@router.get("/time-limits")
async def get_time_limits(_: User = Depends(require_admin)):
    """Returns current time limits for each module."""
    return {
        "listening": settings.LISTENING_TIME_LIMIT,
        "reading": settings.READING_TIME_LIMIT,
        "writing": settings.WRITING_TIME_LIMIT,
        "speaking": settings.SPEAKING_TIME_LIMIT,
    }