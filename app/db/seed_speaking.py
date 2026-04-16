"""
Creates a speaking test and links it to the existing IeltsTest.

Run after seed.py:
    python -m app.db.seed_speaking
"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.speaking import SpeakingTest, SpeakingPart, SpeakingPartType
from app.models.ielts_test import IeltsTest


async def seed():
    async with AsyncSessionLocal() as db:

        st = SpeakingTest(
            title="Academic Speaking Test 1",
            is_active=True,
            is_demo=True,
        )
        db.add(st)
        await db.flush()

        # ── Part 1: Interview (4-5 personal questions) ────────────────────
        p1 = SpeakingPart(
            test_id=st.id,
            part_number=1,
            part_type=SpeakingPartType.part1,
            instructions=(
                "In Part 1, the examiner will ask you questions about yourself "
                "and familiar topics. Answer naturally and try to extend your "
                "answers — aim for 2-3 sentences per response."
            ),
            questions=[
                "Can you tell me a little about where you grew up?",
                "What do you enjoy doing in your free time?",
                "Do you prefer spending time alone or with other people? Why?",
                "How important is it to you to stay in touch with family and friends?",
                "What kind of music do you enjoy listening to, and why?",
            ],
            prep_time_seconds=0,
            response_time_seconds=240,   # ~4 minutes total for Part 1
        )
        db.add(p1)

        # ── Part 2: Long turn (cue card + 2-minute monologue) ────────────
        p2 = SpeakingPart(
            test_id=st.id,
            part_number=2,
            part_type=SpeakingPartType.part2,
            instructions=(
                "In Part 2, you will be given a topic card. "
                "You have 1 minute to prepare, then you should speak for "
                "1-2 minutes on the topic. The examiner will then ask "
                "one or two follow-up questions."
            ),
            cue_card=(
                "Describe a book or film that had a significant impact on you.\n\n"
                "You should say:\n"
                "  • what the book or film was\n"
                "  • when you first encountered it\n"
                "  • what it was about\n\n"
                "and explain why it had such a significant impact on you."
            ),
            questions=[
                # The main prompt is the cue card — this question captures the monologue
                "Please speak about the topic on the card for 1-2 minutes.",
                # Follow-up questions after the monologue
                "Do you think reading books is more beneficial than watching films? Why?",
            ],
            prep_time_seconds=60,
            response_time_seconds=150,   # 2.5 minutes including follow-up
        )
        db.add(p2)

        # ── Part 3: Discussion (abstract questions linked to Part 2 topic) ─
        p3 = SpeakingPart(
            test_id=st.id,
            part_number=3,
            part_type=SpeakingPartType.part3,
            instructions=(
                "In Part 3, the examiner will ask more abstract questions "
                "related to the topic in Part 2. Try to develop your answers "
                "with reasons and examples. Aim for 4-6 sentences per response."
            ),
            questions=[
                "How has technology changed the way people read and consume information today?",
                "Do you think governments should invest more in public libraries? Why or why not?",
                "Some people argue that films and television have replaced books as the main form of storytelling. To what extent do you agree?",
                "How might reading habits change over the next 20 years?",
                "In what ways can literature or film help people understand different cultures?",
            ],
            prep_time_seconds=0,
            response_time_seconds=300,   # ~5 minutes for Part 3
        )
        db.add(p3)
        await db.flush()

        # Link to existing IeltsTest
        ielts = (await db.execute(
            select(IeltsTest).where(IeltsTest.is_active == True).limit(1)
        )).scalar_one_or_none()

        if not ielts:
            print("No IeltsTest found — run seed.py first")
            await db.rollback()
            return

        ielts.speaking_test_id = st.id
        await db.commit()

        print(f"\nSeeded speaking test: {st.id}")
        print(f"  Part 1: Interview — 5 questions (~4 min)")
        print(f"  Part 2: Long turn — cue card + 2 follow-ups (~2.5 min)")
        print(f"  Part 3: Discussion — 5 abstract questions (~5 min)")
        print(f"\nLinked to IeltsTest: {ielts.id}")


if __name__ == "__main__":
    asyncio.run(seed())