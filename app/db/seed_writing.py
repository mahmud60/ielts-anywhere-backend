"""
Creates a writing test and links it to the existing IeltsTest.

Run after seed.py:
    python -m app.db.seed_writing
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.writing import WritingTest, WritingTask, WritingTaskType
from app.models.ielts_test import IeltsTest


async def seed():
    async with AsyncSessionLocal() as db:

        wt = WritingTest(
            title="Academic Writing Test 1",
            test_type="academic",
            is_active=True,
            is_demo=True,
        )
        db.add(wt)
        await db.flush()

        # Task 1 — describe a graph
        task1 = WritingTask(
            test_id=wt.id,
            task_number=1,
            task_type=WritingTaskType.task1_academic,
            prompt=(
                "The graph below shows the percentage of households in "
                "different income brackets that owned at least one computer "
                "between 2000 and 2020. Summarise the information by selecting "
                "and reporting the main features, and make comparisons where relevant."
            ),
            stimulus=(
                "Bar chart data:\n"
                "Low income households:    2000: 12%  →  2010: 35%  →  2020: 58%\n"
                "Middle income households: 2000: 45%  →  2010: 72%  →  2020: 89%\n"
                "High income households:   2000: 78%  →  2010: 92%  →  2020: 97%\n"
                "\n"
                "All three income groups showed growth over the 20-year period. "
                "High income households consistently had the highest ownership rates "
                "while low income households showed the greatest relative increase."
            ),
            min_words=150,
        )
        db.add(task1)

        # Task 2 — discursive essay
        task2 = WritingTask(
            test_id=wt.id,
            task_number=2,
            task_type=WritingTaskType.task2,
            prompt=(
                "Some people believe that unpaid community service should be a "
                "compulsory part of high school programmes. To what extent do you "
                "agree or disagree?\n\n"
                "Give reasons for your answer and include any relevant examples "
                "from your own knowledge or experience."
            ),
            stimulus=None,
            min_words=250,
        )
        db.add(task2)
        await db.flush()

        # Link to existing IeltsTest
        ielts = (await db.execute(
            select(IeltsTest).where(IeltsTest.is_active == True).limit(1)
        )).scalar_one_or_none()

        if not ielts:
            print("No IeltsTest found — run seed.py first")
            await db.rollback()
            return

        ielts.writing_test_id = wt.id
        await db.commit()

        print(f"\nSeeded writing test: {wt.id}")
        print(f"  Task 1: Computer ownership graph (min 150 words)")
        print(f"  Task 2: Compulsory community service essay (min 250 words)")
        print(f"\nLinked to IeltsTest: {ielts.id}")


if __name__ == "__main__":
    asyncio.run(seed())