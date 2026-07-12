from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.ielts_test import IeltsTest
from .deps import require_admin

router = APIRouter()


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
