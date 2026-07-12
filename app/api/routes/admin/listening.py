from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.listening import (
    ListeningTest, ListeningSection, ListeningSubsection, ListeningQuestion,
)
from app.services.storage import upload_audio, delete_audio
from .deps import require_admin

router = APIRouter()


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
            "group_label": q.group_label,
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


@router.post("/listening/tests/{test_id}/generate-tips", status_code=202)
async def generate_listening_tips(
    test_id: str,
    overwrite: bool = False,
    _: User = Depends(require_admin),
):
    from app.tasks.grading import generate_question_tips_task
    generate_question_tips_task.delay(test_id, "listening", overwrite)
    return {"status": "queued", "test_id": test_id, "module": "listening"}


@router.post("/listening/translate-tips", status_code=202)
async def translate_listening_tips(
    overwrite: bool = False,
    _: User = Depends(require_admin),
):
    """Backfill Bengali translations for every existing listening wrong_answer_tip.
    Run once after deploy; per-test generate-tips also fills BN going forward."""
    from app.tasks.grading import translate_listening_tips_task
    translate_listening_tips_task.delay(overwrite)
    return {"status": "queued", "module": "listening", "overwrite": overwrite}
