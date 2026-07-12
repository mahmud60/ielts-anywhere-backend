from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.speaking import SpeakingTest, SpeakingPart, SpeakingPartType
from .deps import require_admin

router = APIRouter()


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
