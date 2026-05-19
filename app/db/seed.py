"""
Creates one complete IeltsTest with a linked listening test.
Run once after migrations.

    python -m app.db.seed
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.listening import ListeningTest, ListeningSection, ListeningSubsection, ListeningQuestion
from app.models.ielts_test import IeltsTest


def opts(*labels):
    return [{"order": i, "option": lbl} for i, lbl in enumerate(labels)]


async def seed():
    async with AsyncSessionLocal() as db:

        # ── Listening test ────────────────────────────────────────────────
        lt = ListeningTest(title="Academic Listening Test 1", is_active=True)
        db.add(lt)
        await db.flush()

        # Section 1 — Hotel booking
        s1 = ListeningSection(test_id=lt.id, part=1, title="Hotel Booking")
        db.add(s1)
        await db.flush()

        sub1 = ListeningSubsection(section_id=s1.id, order=1, subsection_type="regular",
            text="Questions 1–4. Choose the correct letter, A, B, C or D.")
        db.add(sub1)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub1.id, order=1,
                question_type="multiple_choices",
                text="What is the main purpose of the caller's enquiry?",
                options=opts("To cancel a booking", "To make a new reservation",
                             "To complain", "To ask about prices"),
                answer_key="1",
                wrong_answer_tip="Listen to the caller's opening sentence — purpose is stated directly."),
            ListeningQuestion(subsection_id=sub1.id, order=2,
                question_type="fill_in_the_blank",
                text="The guest's last name is ___________.",
                answer_key="thompson",
                wrong_answer_tip="Proper nouns are usually spelled out. Listen for T-H-O-M-P-S-O-N."),
            ListeningQuestion(subsection_id=sub1.id, order=3,
                question_type="fill_in_the_blank",
                text="The check-in date is ___________ 14th.",
                answer_key="march",
                wrong_answer_tip="Dates are spoken as ordinals. 'The fourteenth of March' means March 14th."),
            ListeningQuestion(subsection_id=sub1.id, order=4,
                question_type="multiple_choices",
                text="How many nights does the guest plan to stay?",
                options=opts("Two nights", "Three nights", "Four nights", "Five nights"),
                answer_key="1",
                wrong_answer_tip=None),
        ]:
            db.add(q)

        # Section 2 — Community centre
        s2 = ListeningSection(test_id=lt.id, part=2, title="Community Centre")
        db.add(s2)
        await db.flush()

        sub2 = ListeningSubsection(section_id=s2.id, order=1, subsection_type="regular",
            text="Questions 5–7. Do the following statements agree with the information? Write TRUE, FALSE or NOT GIVEN.")
        db.add(sub2)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub2.id, order=1,
                question_type="multiple_choices",
                text="The community centre has been recently renovated.",
                options=opts("True", "False", "Not Given"),
                answer_key="0",
                wrong_answer_tip="Listen for 'newly refurbished' or 'recently updated'."),
            ListeningQuestion(subsection_id=sub2.id, order=2,
                question_type="multiple_choices",
                text="Fitness classes are available every day of the week.",
                options=opts("True", "False", "Not Given"),
                answer_key="1",
                wrong_answer_tip="Listen for days mentioned — 'Monday to Saturday' excludes Sunday."),
            ListeningQuestion(subsection_id=sub2.id, order=3,
                question_type="multiple_choices",
                text="The centre offers discounts for senior citizens.",
                options=opts("True", "False", "Not Given"),
                answer_key="2",
                wrong_answer_tip="Not Given — the recording never mentions senior discounts at all."),
        ]:
            db.add(q)

        # Section 3 — Research discussion
        s3 = ListeningSection(test_id=lt.id, part=3, title="Research Discussion")
        db.add(s3)
        await db.flush()

        sub3 = ListeningSubsection(section_id=s3.id, order=1, subsection_type="form",
            text="Questions 8–9. Complete the form below.")
        db.add(sub3)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub3.id, order=1,
                question_type="dropdown",
                text="Research method suggested by Student A",
                options=opts("Conducting surveys", "Reviewing existing literature", "Running lab experiments"),
                answer_key="0",
                wrong_answer_tip="Speakers use synonyms — 'questionnaire' means survey."),
            ListeningQuestion(subsection_id=sub3.id, order=2,
                question_type="multiple_choices",
                text="What does the supervisor recommend as the next step?",
                options=opts("Submit the proposal immediately", "Narrow down the research question",
                             "Collect data first", "Present to the department"),
                answer_key="1",
                wrong_answer_tip=None),
        ]:
            db.add(q)

        # Section 4 — Academic lecture
        s4 = ListeningSection(test_id=lt.id, part=4, title="Urban Heat Islands")
        db.add(s4)
        await db.flush()

        sub4 = ListeningSubsection(section_id=s4.id, order=1, subsection_type="regular",
            text="Questions 10–12. Complete the notes below.")
        db.add(sub4)
        await db.flush()
        for q in [
            ListeningQuestion(subsection_id=sub4.id, order=1,
                question_type="fill_in_the_blank",
                text="Urban areas can be up to ___________ degrees warmer than rural regions.",
                answer_key="10",
                wrong_answer_tip="Numbers in lectures are emphasised. Listen for 'up to' or 'as much as'."),
            ListeningQuestion(subsection_id=sub4.id, order=2,
                question_type="multiple_choices",
                text="Which factor does the lecturer identify as the PRIMARY cause?",
                options=opts("Vehicle emissions", "Reduced green spaces",
                             "Heat absorption by built surfaces", "Waste heat from air conditioning"),
                answer_key="2",
                wrong_answer_tip="Listen for 'primarily', 'mainly', or 'the most significant factor'."),
            ListeningQuestion(subsection_id=sub4.id, order=3,
                question_type="fill_in_the_blank",
                text="Increasing tree canopy by 10% reduces temperatures by ___________ degrees Celsius.",
                answer_key="2.3",
                wrong_answer_tip="Decimals are easy to mishear. '2.3' is 'two point three'."),
        ]:
            db.add(q)

        # ── IeltsTest — links listening (and future modules) together ─────
        ielts = IeltsTest(
            title="Academic Full Test 1",
            test_type="academic",
            is_active=True,
            listening_test_id=lt.id,
        )
        db.add(ielts)
        await db.commit()

        print(f"\nSeeded successfully!")
        print(f"  IeltsTest:     {ielts.id}")
        print(f"  ListeningTest: {lt.id}")
        print(f"  Sections: 4   Subsections: 4   Questions: 12")
        print(f"\nCopy the IeltsTest ID — you'll need it for testing.")


if __name__ == "__main__":
    asyncio.run(seed())
