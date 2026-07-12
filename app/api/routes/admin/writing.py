from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.writing import WritingTest, WritingTask, WritingTaskType
from .deps import require_admin

router = APIRouter()


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
