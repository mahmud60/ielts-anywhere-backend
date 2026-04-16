"""
Creates one complete IeltsTest with a linked listening test.
Run once after migrations.

    python -m app.db.seed
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.listening import ListeningTest, ListeningSection, ListeningQuestion, QuestionType
from app.models.ielts_test import IeltsTest
from app.models.user import User as UserModel

async def seed():
    async with AsyncSessionLocal() as db:

        # ── Listening test ────────────────────────────────────────────────
        lt = ListeningTest(title="Academic Listening Test 1", is_active=True, is_demo=True)
        db.add(lt)
        await db.flush()

        # Section 1 — Hotel booking (MCQ + fill)
        s1 = ListeningSection(test_id=lt.id, section_number=1, title="Hotel Booking",
            context="A conversation between a hotel receptionist and a guest.",
            audio_duration_seconds=120)
        db.add(s1)
        await db.flush()
        for q in [
            ListeningQuestion(section_id=s1.id, order_index=1,
                question_type=QuestionType.mcq,
                question_text="What is the main purpose of the caller's enquiry?",
                options=["To cancel a booking","To make a new reservation","To complain","To ask about prices"],
                answer_key=1,
                wrong_answer_tip="Listen to the caller's opening sentence — purpose is stated directly."),
            ListeningQuestion(section_id=s1.id, order_index=2,
                question_type=QuestionType.fill,
                question_text="The guest's last name is ___________.",
                answer_key="thompson",
                wrong_answer_tip="Proper nouns are usually spelled out. Listen for T-H-O-M-P-S-O-N."),
            ListeningQuestion(section_id=s1.id, order_index=3,
                question_type=QuestionType.fill,
                question_text="The check-in date is ___________ 14th.",
                answer_key="march",
                wrong_answer_tip="Dates are spoken as ordinals. 'The fourteenth of March' means March 14th."),
            ListeningQuestion(section_id=s1.id, order_index=4,
                question_type=QuestionType.mcq,
                question_text="How many nights does the guest plan to stay?",
                options=["Two nights","Three nights","Four nights","Five nights"],
                answer_key=1,
                wrong_answer_tip=None),
        ]: db.add(q)

        # Section 2 — Community centre (True/False/Not Given)
        s2 = ListeningSection(test_id=lt.id, section_number=2, title="Community Centre",
            context="An announcement about a local community centre and upcoming events.",
            audio_duration_seconds=150)
        db.add(s2)
        await db.flush()
        for q in [
            ListeningQuestion(section_id=s2.id, order_index=1,
                question_type=QuestionType.tfng,
                question_text="The community centre has been recently renovated.",
                options=["True","False","Not Given"], answer_key=0,
                wrong_answer_tip="Listen for 'newly refurbished' or 'recently updated'."),
            ListeningQuestion(section_id=s2.id, order_index=2,
                question_type=QuestionType.tfng,
                question_text="Fitness classes are available every day of the week.",
                options=["True","False","Not Given"], answer_key=1,
                wrong_answer_tip="Listen for days mentioned — 'Monday to Saturday' excludes Sunday."),
            ListeningQuestion(section_id=s2.id, order_index=3,
                question_type=QuestionType.tfng,
                question_text="The centre offers discounts for senior citizens.",
                options=["True","False","Not Given"], answer_key=2,
                wrong_answer_tip="Not Given — the recording never mentions senior discounts at all."),
        ]: db.add(q)

        # Section 3 — Research discussion (matching)
        s3 = ListeningSection(test_id=lt.id, section_number=3, title="Research Discussion",
            context="Two students discussing their project with a supervisor.",
            audio_duration_seconds=180)
        db.add(s3)
        await db.flush()
        for q in [
            ListeningQuestion(section_id=s3.id, order_index=1,
                question_type=QuestionType.matching,
                question_text="Match each research method with the person who suggested it.",
                options=["Conducting surveys","Reviewing existing literature","Running lab experiments"],
                matching_pool=["Student A","Student B","Supervisor"],
                answer_key={"0":"Student A","1":"Supervisor","2":"Student B"},
                wrong_answer_tip="Speakers use synonyms — 'questionnaire' means survey."),
            ListeningQuestion(section_id=s3.id, order_index=2,
                question_type=QuestionType.mcq,
                question_text="What does the supervisor recommend as the next step?",
                options=["Submit the proposal immediately","Narrow down the research question",
                         "Collect data first","Present to the department"],
                answer_key=1, wrong_answer_tip=None),
        ]: db.add(q)

        # Section 4 — Academic lecture (MCQ + fill)
        s4 = ListeningSection(test_id=lt.id, section_number=4, title="Urban Heat Islands",
            context="A university lecture on urban heat islands and environmental impact.",
            audio_duration_seconds=210)
        db.add(s4)
        await db.flush()
        for q in [
            ListeningQuestion(section_id=s4.id, order_index=1,
                question_type=QuestionType.fill,
                question_text="Urban areas can be up to ___________ degrees warmer than rural regions.",
                answer_key="10",
                wrong_answer_tip="Numbers in lectures are emphasised. Listen for 'up to' or 'as much as'."),
            ListeningQuestion(section_id=s4.id, order_index=2,
                question_type=QuestionType.mcq,
                question_text="Which factor does the lecturer identify as the PRIMARY cause?",
                options=["Vehicle emissions","Reduced green spaces",
                         "Heat absorption by built surfaces","Waste heat from air conditioning"],
                answer_key=2,
                wrong_answer_tip="Listen for 'primarily', 'mainly', or 'the most significant factor'."),
            ListeningQuestion(section_id=s4.id, order_index=3,
                question_type=QuestionType.fill,
                question_text="Increasing tree canopy by 10% reduces temperatures by ___________ degrees Celsius.",
                answer_key="2.3",
                wrong_answer_tip="Decimals are easy to mishear. '2.3' is 'two point three'."),
        ]: db.add(q)

        # ── IeltsTest — links listening (and future modules) together ─────
        ielts = IeltsTest(
            title="Academic Full Test 1",
            test_type="academic",
            is_active=True,
            is_demo=True,
            listening_test_id=lt.id,   # the link that makes it all work
        )
        db.add(ielts)
        await db.commit()

        print(f"\nSeeded successfully!")
        print(f"  IeltsTest:     {ielts.id}")
        print(f"  ListeningTest: {lt.id}")
        print(f"  Sections: 4   Questions: 12")
        print(f"\nCopy the IeltsTest ID — you'll need it for testing.")

if __name__ == "__main__":
    asyncio.run(seed())