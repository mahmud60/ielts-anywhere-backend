from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.reading import (
    ReadingTest, ReadingPassage,
    ReadingQuestionGroup, ReadingQuestion,
    ReadingQuestionType,
)
from .deps import require_admin

router = APIRouter()


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


@router.delete("/reading/groups/{group_id}")
async def delete_reading_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    group = (await db.execute(
        select(ReadingQuestionGroup)
        .where(ReadingQuestionGroup.id == group_id)
        .options(selectinload(ReadingQuestionGroup.questions))
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    for question in group.questions:
        await db.delete(question)
    await db.delete(group)
    await db.flush()
    return {"deleted": group_id}


@router.delete("/reading/passages/{passage_id}")
async def delete_reading_passage(
    passage_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    passage = (await db.execute(
        select(ReadingPassage)
        .where(ReadingPassage.id == passage_id)
        .options(
            selectinload(ReadingPassage.question_groups)
            .selectinload(ReadingQuestionGroup.questions)
        )
    )).scalar_one_or_none()
    if not passage:
        raise HTTPException(404, "Passage not found")
    for group in passage.question_groups:
        for question in group.questions:
            await db.delete(question)
        await db.delete(group)
    await db.delete(passage)
    await db.flush()
    return {"deleted": passage_id}


@router.delete("/reading/tests/{test_id}")
async def delete_reading_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    from app.models.ielts_test import IeltsTest
    test = (await db.execute(
        select(ReadingTest)
        .where(ReadingTest.id == test_id)
        .options(
            selectinload(ReadingTest.passages)
            .selectinload(ReadingPassage.question_groups)
            .selectinload(ReadingQuestionGroup.questions)
        )
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")
    # Null out any IELTS test references before deleting
    linked = (await db.execute(
        select(IeltsTest).where(IeltsTest.reading_test_id == test_id)
    )).scalars().all()
    for ielts in linked:
        ielts.reading_test_id = None
    await db.flush()
    for passage in test.passages:
        for group in passage.question_groups:
            for question in group.questions:
                await db.delete(question)
            await db.delete(group)
        await db.delete(passage)
    await db.delete(test)
    await db.flush()
    return {"deleted": test_id}


@router.patch("/reading/tests/{test_id}")
async def update_reading_test(
    test_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    test = (await db.execute(select(ReadingTest).where(ReadingTest.id == test_id))).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")
    for field in ["title", "test_type", "is_active", "is_demo"]:
        if field in body:
            setattr(test, field, body[field])
    await db.flush()
    return {"id": str(test.id), "title": test.title, "is_active": test.is_active}


@router.post("/reading/tests/{test_id}/generate-tips", status_code=202)
async def generate_reading_tips(
    test_id: str,
    overwrite: bool = False,
    _: User = Depends(require_admin),
):
    from app.tasks.grading import generate_question_tips_task
    generate_question_tips_task.delay(test_id, "reading", overwrite)
    return {"status": "queued", "test_id": test_id, "module": "reading"}
